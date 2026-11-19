# Plan de test — XCP-ng 8.3 LTS

## Contexte

- VM VirtualBox `xcp-ng`, 4 vCPU / 8,5 Go, BIOS, NIC NAT, snapshot `pristine`.
- XCP-ng 8.3.0 (xenenterprise), noyau 4.19.0+1, hôte `xcp-ng-idircaez`.
- Hôte : i9-11950H / 64 Go / Windows 11, VirtualBox 7.2.12, Python 3.13 + paramiko.
- Accès SSH NAT `127.0.0.1:2223`, identifiants locaux non commités.

## Étapes

| # | Action | Commande | Résultat attendu |
| --- | --- | --- | --- |
| 1 | Snapshot initial | `VBoxManage snapshot xcp-ng take pristine` | point de restauration |
| 2 | Baseline | `xcp.py run --phase baseline` | état non durci mesuré |
| 3 | Dry-run | `xcp.py harden --level 1 --dry-run` | aucune écriture, plan lisible |
| 4 | Snapshot pré-durcissement | `VBoxManage snapshot xcp-ng take pre-hardening` | point de restauration |
| 5 | Hardening L1 | `xcp.py harden --level 1` | SSH par clé, https-only, port 80 bloqué, NTP |
| 6 | Vérification | `xcp.py run --phase verify` | contrôles PASS, 0 régression fonctionnelle |
| 7 | Dé-hardening dry-run | `xcp.py deharden --dry-run` | liste des restaurations |
| 8 | Dé-hardening réel | `xcp.py deharden` | retour au baseline |
| 9 | Vérification retour | `xcp.py run --phase verify` | statuts identiques au baseline |
| 10 | Upgrade 8.3 LTS | `yum update -y` puis redémarrage à froid | version/noyau mis à jour |
| 11 | Re-durcissement | étapes 5-6 | mêmes contrôles PASS après upgrade |

## Résultats obtains (19 novembre 2026)

- Baseline : `https-only=false`, port 80 accessible, authentification SSH par mot de passe, `rpcbind` actif, pas de syslog distant.
- Après L1 : `https-only=true`, trafic port 80 DROP par iptables, `PasswordAuthentication no`, `PermitRootLogin prohibit-password`, ciphers/MACs/Kex explicites, clé ED25519 installée, source chrony ajoutée.
- Tests fonctionnels : **23/23 PASS** à chaque étape (aucune régression).
- Après dé-hardening : tous les contrôles durcis reviennent à leur statut baseline ; 23/23 tests fonctionnels PASS.
- Limite observée : `xe host-param-set https-only=true` ne ferme pas le *listener* XAPI sur le port 80 dans cette version ; une règle iptables est nécessaire et est restaurée par le dé-hardening.

## Hors périmètre (déclaré N/A, pas masqué)

Réseaux physique séparés, VPN/ZTNA, XOA audit log, IPMI/BMC, port locking, certificats publics, accès physique, chaîne d'approvisionnement : non testables sur un hôte NAT mono-VM sans Xen Orchestra.
