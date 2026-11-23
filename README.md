# XCP-ng Hardening Lab

Lab de hardening **XCP-ng 8.3 LTS** sur VM VirtualBox, inspiré de la méthode `pve9-hardening-lab` (Proxmox) : mesures avant/après, script de hardening réversible, script de dé-hardening, tests de non-régression, snapshots et montée de version.

**Le jeu de contrôles vient du guide officiel Vates** (`docs/vates-vms-hardening-guide.pdf`, v0.4, 2026-10-26) : voir `docs/RESEARCH.md`. Les outils communautaires et CIS/Citrix sont documentés dans le même fichier ; aucun n'est exécutable directement sur dom0, ils servent de référence.

## VM

- Nom VirtualBox : `xcp-ng`, XCP-ng 8.3.0, noyau 4.19, 4 vCPU / 8,5 Go.
- Accès : NAT `127.0.0.1:2223` -> invité `:22` (rule ajoutée au lab).
- Identifiants dans `.local/credentials.txt` (non commité). Clé SSH de test dans `.keys/`.
- Snapshot `pristine` créé avant toute modification. **Ne jamais utiliser de clone de disque** (UUID -> GRUB cassé) : uniquement des snapshots, VM arrêtée.

## Commandes (hôte Windows, Python 3 + paramiko)

```bash
python scripts/xcp.py info
python scripts/xcp.py snapshot list
python scripts/xcp.py snapshot take pre-hardening

# cycle complet : baseline -> apply -> verify
python scripts/xcp.py run --phase all --level 1

# étapes séparées
python scripts/xcp.py run --phase baseline
python scripts/xcp.py harden --level 1 --dry-run
python scripts/xcp.py harden --level 1
python scripts/xcp.py deharden --dry-run
python scripts/xcp.py deharden
python scripts/xcp.py report --title "XCP-ng L1" --dirs artifacts/<baseline> artifacts/<verify>
```

## Déploiement bare-metal (PXE / iPXE)

Le lab est testé sur VirtualBox, mais le déploiement cible est un serveur
physique. La procédure complète est dans `docs/DEPLOIEMENT-PXE.md` (sources
officielles Vates). Trois variantes sont fournies dans `pxe/` :

- **BIOS** : `pxelinux.0` + `mboot.c32` + `pxe/pxelinux.cfg/default` ;
- **UEFI** (recommandé) : `grubx64.efi` + `pxe/grub.cfg` ;
- **iPXE over HTTP** : `pxe/ipxe-menu.ipxe`.

L'installation non interactive passe par `pxe/answerfile.xml` :

```
answerfile=http://10.0.0.10/xcp-ng/answerfile.xml install
```

Le fichier de réponse ne contient **aucun mot de passe réel** (placeholder
`<MOT_DE_PASSE_LAB>` à injecter côté serveur). Le DHCP doit servir
`EFI/xcp-ng/grubx64.efi` en UEFI et `pxelinux.0` en BIOS. Le contenu complet de
l'ISO (y compris `.treeinfo`) doit être servi en HTTP pour les paquets RPM.

## Documentation et rapports PDF

Les rapports et documents sont générés en PDF avec le même moteur que
`pve9-hardening-lab` (Chrome/Edge headless, aucun paquet Python tiers) :

```bash
python scripts/xcp.py pdf --all            # tous les reports/*.md
python scripts/xcp.py pdf --all --docs     # reports/ + docs/
python scripts/xcp.py pdf --md docs/DE-HARDENING.md
python scripts/xcp.py report --title "XCP-ng L3" --dirs artifacts/<baseline> artifacts/<verify> --pdf
# equivalent : python scripts/pdf.py --all --docs
```

| Document | PDF |
| --- | --- |
| `docs/PLAN-DE-TEST.md` | `docs/PLAN-DE-TEST.pdf` |
| `docs/DE-HARDENING.md` | `docs/DE-HARDENING.pdf` |
| `docs/RESULTS.md` | `docs/RESULTS.pdf` |
| `docs/DEPLOIEMENT-PXE.md` | `docs/DEPLOIEMENT-PXE.pdf` |
| `reports/report-final-xcp-ng-l3.md` | `reports/report-final-xcp-ng-l3.pdf` |

## Ce qui est durci (dom0)

| Niveau | Contrôles |
| --- | --- |
| L1 | clé SSH installée, `PasswordAuthentication no`, `PermitRootLogin prohibit-password`, ciphers/MACs/Kex modernes, `https-only=true` (port 80 fermé), NTP via chrony |
| L2 | syslog distant (`SYSLOG_SERVER=`), désactivation de `rpcbind` |
| L3 | `umask 027`, bannière `/etc/issue.net` |

Tout le reste du guide Vates (réseaux séparés, VPN/ZTNA, XOA audit log, IPMI, port locking, certificats) est **audité mais marqué N/A** dans ce lab mono-hôte NAT — voir `guest/audit-xcp.sh`.

## Structure

```
guest/     scripts bash exécutés sur l'hôte XCP-ng (audit, apply, deharden, func-test)
scripts/   orchestrateur Python (SSH, VBoxManage, cycles, rapports)
docs/      guide Vates (PDF + texte), recherche, plan de test, PXE, de-hardening
pxe/       exemples PXE/iPXE (answerfile.xml, grub.cfg, pxelinux.cfg, dnsmasq)
scripts/pdf.py  moteur Markdown -> HTML -> PDF (Chrome headless)
artifacts/ mesures horodatées (non commité)
reports/   rapports Markdown + HTML + PDF
```

## Sécurité

Lab uniquement : la VM est isolée en NAT. Les identifiants et clés sont dans `.local/` et `.keys/` (ignorés par git). Le dé-hardening restaure les fichiers, permissions, paramètres XAPI et réactive les services ; il ne supprime que la clé installée par le lab et jamais les paquets déjà présents.
