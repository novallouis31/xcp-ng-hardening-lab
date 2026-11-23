# Déploiement XCP-ng 8.3 LTS par PXE / iPXE (bare-metal)

Lab validé sur VirtualBox, mais la méthode s'applique telle quelle à un serveur
physique. Le cycle de hardening (`baseline → apply → verify → deharden`) est
identique une fois l'hôte installé.

Sources officielles : <https://docs.xcp-ng.org/installation/install-xcp-ng/>.

## 1. Principe

```
Client (PXE BIOS ou UEFI)
   |  DHCP + TFTP
   v
mboot.c32 / grubx64.efi  --->  xen.gz + vmlinuz + install.img
                                  |  answerfile=http://…/answerfile.xml install
                                  v
                          installation non interactive
                                  v
                          reboot ---> cycle de hardening du lab
```

Trois variantes sont supportées :

| Variante | Fichiers | Usage |
| --- | --- | --- |
| BIOS (PXELINUX) | `pxelinux.0`, `mboot.c32`, `pxelinux.cfg/default` | serveurs legacy |
| UEFI (GRUB sur TFTP) | `EFI/xcp-ng/grubx64.efi`, `grub.cfg` | serveurs UEFI (recommandé) |
| iPXE over HTTP | `ipxe.efi` + script iPXE | HTTP seul, pas de TFTP à maintenir |

> ⚠️ Le boot PXE **ne supporte pas les VLAN taggés** : utiliser un port untagged.

## 2. Arborescence TFTP attendue

```
/srv/tftp/
├── pxelinux.0
├── mboot.c32                 # BIOS uniquement
├── pxelinux.cfg/
│   └── default               #voir pxe/pxelinux.cfg/default
└── EFI/
    ├── xcp-ng/
    │   ├── grubx64.efi
    │   ├── xen.gz
    │   ├── vmlinuz
    │   └── install.img
    └── xenserver/
        └── grub.cfg          # voir pxe/grub.cfg
```

Copie depuis l'ISO (ex. `xcp-ng-8.3.0-20260806.iso`) :

```bash
mkdir -p /srv/tftp/xcp-ng /srv/tftp/EFI/xcp-ng /srv/tftp/EFI/xenserver
mount -o loop xcp-ng-8.3.0.iso /mnt/iso
cp /mnt/iso/pxelinux.0 /mnt/iso/boot/mboot.c32 /srv/tftp/
cp /mnt/iso/install.img /srv/tftp/xcp-ng/
cp /mnt/iso/boot/vmlinuz /mnt/iso/boot/xen.gz /srv/tftp/xcp-ng/
cp /mnt/iso/EFI/xenserver/grubx64.efi /srv/tftp/EFI/xcp-ng/
cp /mnt/iso/install.img /srv/tftp/EFI/xcp-ng/
cp /mnt/iso/boot/vmlinuz /mnt/iso/boot/xen.gz /srv/tftp/EFI/xcp-ng/
```

Le **contenu complet de l'ISO** (y compris le fichier `.treeinfo`, souvent bloqué
par IIS) doit être servi en HTTP/NFS/FTP : c'est la source des paquets RPM.

## 3. Answer file (`pxe/answerfile.xml`)

```xml
<?xml version="1.0"?>
<installation srtype="ext" mode="fresh">
  <primary-disk>sda</primary-disk>
  <keymap>fr</keymap>
  <root-password><MOT_DE_PASSE_LAB></root-password>
  <source type="url">http://10.0.0.10/xcp-ng/</source>
  <admin-interface name="eth0" proto="dhcp" />
  <timezone>Europe/Paris</timezone>
  <script stage="filesystem-grown" type="url">
    http://10.0.0.10/xcp-ng/grow.sh
  </script>
</installation>
```

Le mot de passe root **n'est jamais versionné** : remplacer la valeur par un
secret injecté par le serveur HTTP (ou utiliser `post-install-script` pour le
changer ensuite). Pour une installation sur 2 disques en RAID logiciel, voir le
commentaire dans `pxe/answerfile.xml`.

## 4. Lignes de boot

**BIOS** (`pxe/pxelinux.cfg/default`) :

```
default xcp-ng-auto
label xcp-ng-auto
    kernel mboot.c32
    append xcp-ng/xen.gz dom0_max_vcpus=2 dom0_mem=2048M,max:2048M \
      com1=115200,8n1 console=com1,vga --- xcp-ng/vmlinuz \
      xencons=hvc console=hvc0 console=tty0 \
      answerfile=http://10.0.0.10/xcp-ng/answerfile.xml install --- xcp-ng/install.img
```

**UEFI** (`pxe/grub.cfg`) :

```
menuentry "XCP-ng Install (serial)" {
    multiboot2 /EFI/xcp-ng/xen.gz dom0_mem=2048M,max:2048M watchdog dom0_max_vcpus=4 com1=115200,8n1 console=com1,vga
    module2 /EFI/xcp-ng/vmlinuz console=hvc0 console=tty0 answerfile_device=eth0 answerfile=http://10.0.0.10/xcp-ng/answerfile.xml install
    module2 /EFI/xcp-ng/install.img
}
```

Paramètres utiles ajoutés à la ligne `vmlinuz` :
`network_device=eth0`, `map_netdev=eth0:s:<MAC>`, `atexit=reboot|poweroff|shell`,
`sshpassword=…` (installateur SSH interactif), `device_mapper_multipath=enabled`.

## 5. DHCP / TFTP (extrait `pxe/dnsmasq.conf`)

```
dhcp-range=10.0.0.100,10.0.0.200,12h
dhcp-option=option:router,10.0.0.1
dhcp-match=set:ipxe-uefi,option:client-arch,7
dhcp-boot=tag:ipxe-uefi,EFI/xcp-ng/grubx64.efi,,10.0.0.10
dhcp-boot=tag:!ipxe-uefi,pxelinux.0,,10.0.0.10
enable-tftp
tftp-root=/srv/tftp
```

## 6. iPXE over HTTP (alternative sans TFTP)

Servir tout le contenu de l'ISO en HTTP, puis depuis le prompt iPXE (`Ctrl-B`) :

```
chain http://10.0.0.10/xcp-ng/EFI/xenserver/grubx64.efi
set root=(http,10.0.0.10)
configfile /EFI/xenserver/grub.cfg
```

Un script iPXE prêt à l'emploi est fourni dans `pxe/ipxe-menu.ipxe`.

## 7. Test sur VirtualBox

- Créer un réseau interne `VBoxManage natnetwork add --netname pxelab …` ou
  `intnet`, y connecter le serveur DHCP/TFTP et la VM (`--nic1 intnet`).
- Firmware **UEFI** pour coller au déploiement bare-metal cible ; démarrer la VM
  avec `VBoxManage startvm <vm> --type headless` et observer le menu PXE via
  `screenshotpng` ou la console série.
- Le disque de test doit être >= 46 Go (XCP-ng 8.3) ; utiliser un VDI vierge.

## 8. Après installation

```bash
python scripts/xcp.py info
python scripts/xcp.py snapshot take pristine
python scripts/xcp.py run --phase all --level 3
python scripts/xcp.py report --title "XCP-ng L3" --dirs artifacts/<baseline> artifacts/<verify> --pdf
```

## Fichiers fournis

| Fichier | Rôle |
| --- | --- |
| `pxe/answerfile.xml` | réponse d'installation non interactive |
| `pxe/pxelinux.cfg/default` | configuration BIOS (PXELINUX) |
| `pxe/grub.cfg` | configuration UEFI (GRUB) |
| `pxe/dnsmasq.conf` | extrait DHCP + TFTP |
| `pxe/ipxe-menu.ipxe` | amorçage iPXE over HTTP |
