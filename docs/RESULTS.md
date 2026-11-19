# Resultats du lab XCP-ng

| Etape | PASS | FAIL | NA | INFO | Tests PASS | Tests FAIL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline initial | 17 | 8 | 6 | 6 | 23 | 0 |
| hardened L1 | 23 | 2 | 6 | 6 | 23 | 0 |
| deharden verify | 17 | 8 | 6 | 6 | 23 | 0 |
| baseline post-upgrade | 18 | 7 | 6 | 6 | 23 | 0 |
| rehardened post-upgrade | 23 | 2 | 6 | 6 | 23 | 0 |
| **final L3 (etat livré)** | **26** | **0** | **6** | **5** | **23** | **0** |

## Montée de version

- Avant : xcp-ng-release 8.3.0 (avant mise à jour), xen-hypervisor et xapi à leur niveau initial.
- Apres : `yum update -y` (144 paquets mis à jour, 8 installés), `xcp-ng-release-8.3.0-38`, `xen-hypervisor-4.17.7-4.2.xcpng8.3`, `xapi-core-26.1.21-1.4.xcpng8.3`, noyau 4.19.0+1.
- `yum check-update` : 0 mise à jour en attente après redémarrage à froid.
- Incidents : premier `yum update` impossible (redirect 302 non suivi) ; correction en forçant les baseurl HTTPS du dépôt.
- Re-durcissement après upgrade : tous les contrôles PASS, 23/23 tests fonctionnels.

## État final livré (19 novembre 2026)

- VM redémarrée puis durcie jusqu'au **niveau 3** : 26 contrôles PASS, 0 FAIL, 5 INFO, 6 NA (hors périmètre), 23/23 tests fonctionnels.
- Le syslog distant est configuré vers `10.0.2.2` (passerelle NAT du lab) : la destination XAPI est bien enregistrée, mais aucun collecteur syslog n'est déployé dans le lab — la valeur est fonctionnelle côté hôte seulement.
- `rpcbind` désactivé, `umask 027` et bannière `/etc/issue.net` appliqués, HTTPS-only et règle iptables port 80 actifs, authentification SSH par clé ED25519 uniquement.
- Rapport de diff complet : `reports/report-final-xcp-ng-l3.md`.
