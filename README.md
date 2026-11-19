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
docs/      guide Vates (PDF + texte), recherche, plan de test
artifacts/ mesures horodatées (non commité)
reports/   rapports Markdown
```

## Sécurité

Lab uniquement : la VM est isolée en NAT. Les identifiants et clés sont dans `.local/` et `.keys/` (ignorés par git). Le dé-hardening restaure les fichiers, permissions, paramètres XAPI et réactive les services ; il ne supprime que la clé installée par le lab et jamais les paquets déjà présents.
