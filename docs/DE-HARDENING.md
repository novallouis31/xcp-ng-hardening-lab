# Dé-hardening — XCP-ng 8.3 LTS

Le dé-hardening est la **dernière étape obligatoire** du cycle : il prouve que
chaque modification peut être reversée proprement, sans réinstallation.

```text
baseline  ->  apply (L1/L2/L3)  ->  verify  ->  deharden (--dry-run puis réel)  ->  audit final
```

## 1. Ce que fait `guest/deharden-xcp.sh`

Le script lit les snapshots créés par `guest/apply-xcp.sh` dans
`/root/xcp-hardening-backups/<horodatage>/` :

| Fichier de snapshot | Action au dé-hardening |
| --- | --- |
| `modified.list` + `<chemin>.<stamp>` | restauration du fichier d'origine (`cp -a`) |
| `created.list` | suppression des fichiers créés par le hardening |
| `https-only.before` | `xe host-param-set https-only=<valeur initiale>` |
| `syslog.before` | restauration/suppression de `logging:syslog_destination` + `xe host-syslog-reconfigure` |
| `disabled-services.*` | `systemctl unmask/enable --now` des services désactivés |
| `/root/xcp-lab-key.pub` | retrait **uniquement** de la clé installée par le lab dans `authorized_keys` |
| firewall | restauration des règles sauvegardées pendant la session |

Une archive de sécurité `etat-avant.tar.gz` est créée dans
`/root/deharden-safety-<horodatage>/` avant toute modification réelle.

**Idempotence** : les listes sont dédupliquées et seul le snapshot **le plus
ancien** est conservé par chemin (`sort -u | awk '!seen[$1]++'`). Rejouer le
dé-hardening ne supprime donc pas les fichiers légitimes apparus depuis.

## 2. Commandes

Toujours commencer par le dry-run :

```bash
# côté hôte Windows
python scripts/xcp.py deharden --dry-run
python scripts/xcp.py deharden

# ou directement dans dom0
bash guest/deharden-xcp.sh --dry-run --report /tmp/xcp-deharden-dry.md
bash guest/deharden-xcp.sh --report /tmp/xcp-deharden.md
```

Le dry-run affiche toutes les actions `RESTORE / REMOVE / XAPI / REENABLE`
sans rien écrire. Vérifier qu'aucune ligne inattendue n'apparaît avant
l'application réelle.

## 3. Vérification après dé-hardening

```bash
python scripts/xcp.py run --phase baseline        # nouvel audit
python scripts/xcp.py run --phase verify --no-func # optionally
bash guest/func-test-xcp.sh                        # tests de non-régression
python scripts/xcp.py snapshot list
```

Attendu : les contrôles durcis repassent à leur état initial (par ex.
`PasswordAuthentication` d'origine, `https-only=false`, port 80 réouvert),
les services réactivés, et la clé SSH du lab absente de `authorized_keys`.

## 4. Limitations connues

- Le changement de certaines valeurs XAPI est asynchrone : laisser quelques
  secondes avant l'audit de vérification.
- Le firmware UEFI/BIOS choisi à l'installation **ne doit jamais être changé**
  (risque GRUB) — voir `docs/DEPLOIEMENT-PXE.md`.
- Le dé-hardening ne désinstalle aucun paquet préexistant : il ne touche qu'aux
  fichiers et paramètres créés ou modifiés par `apply-xcp.sh`.
