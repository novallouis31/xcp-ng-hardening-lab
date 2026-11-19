#!/bin/bash
# De-hardening engine for XCP-ng lab. Restores the pre-hardening state.
# Usage: bash deharden-xcp.sh [--dry-run] [--report FILE]
set -u
DRY=0; REPORT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --report) REPORT="${2:-/tmp/xcp-deharden.md}"; shift ;;
    --force) FORCE=1 ;;
  esac
  shift
done
ROOT=/root/xcp-hardening-backups
TS="$(date +%Y%m%d-%H%M%S)"
SAFE="/root/deharden-safety-$TS"
mkdir -p "$SAFE"
[ "$DRY" = "1" ] || tar czf "$SAFE/etat-avant.tar.gz" /etc/ssh /etc/chrony.conf /etc/profile.d /etc/issue.net /root/.ssh 2>/dev/null || true

REST=(); DEL=(); SKIP=()
if [ -d "$ROOT" ]; then
  for d in "$ROOT"/*; do
    [ -f "$d/modified.list" ] || continue
    stamp="$(basename "$d")"
    while read -r f; do
      [ -f "$d$f.$stamp" ] && REST+=("$f|$d$f.$stamp") || DEL+=("$f")
    done < "$d/modified.list"
    while read -r f; do DEL+=("$f"); done < "$d/created.list"
  done
else
  echo "ERROR: no backup directory $ROOT (was this host hardened?)"
  [ "${FORCE:-0}" = "1" ] || exit 3
fi

# De-duplicate, keep the oldest snapshot per path (idempotency rule).
mapfile -t REST < <(printf '%s\n' "${REST[@]}" | sort -u | awk -F'|' '!seen[$1]++')
mapfile -t DEL < <(printf '%s\n' "${DEL[@]}" | sort -u)

log() { printf '%s\n' "$*" | tee -a "$SAFE/log.txt"; }
log "=== XCP-ng de-hardening DRY=$DRY ==="
log "safety archive: $SAFE/etat-avant.tar.gz"
for entry in "${REST[@]}"; do
  f="${entry%%|*}"; src="${entry#*|}"
  log "RESTORE $f <- $src"
  [ "$DRY" = "1" ] || { mkdir -p "$(dirname "$f")"; cp -a "$src" "$f"; }
done
for f in "${DEL[@]}"; do
  case "$f" in /etc/ssh/sshd_config.d/*|/etc/profile.d/*) ;; *) SKIP+=("$f"); continue ;; esac
  log "REMOVE $f"
  [ "$DRY" = "1" ] || rm -f "$f"
done

# Revert XAPI parameters.
UUID="$(xe host-list params=uuid --minimal 2>/dev/null | awk -F, '{print $1}')"
for d in "$ROOT"/*; do
  [ -f "$d/https-only.before" ] || continue
  OLD="$(cat "$d/https-only.before")"
  log "XAPI https-only -> $OLD"
  [ "$DRY" = "1" ] || xe host-param-set uuid="$UUID" "https-only=${OLD:-false}"
done
for d in "$ROOT"/*; do
  [ -f "$d/syslog.before" ] || continue
  OLD="$(cat "$d/syslog.before")"
  log "XAPI syslog -> ${OLD:-<unset>}"
  if [ "$DRY" != "1" ]; then
    if [ -z "$OLD" ] || [ "$OLD" = "<not set>" ]; then xe host-param-remove uuid="$UUID" param-name=logging param-key=syslog_destination 2>/dev/null || true
    else xe host-param-set uuid="$UUID" "logging:syslog_destination=$OLD"; fi
    xe host-syslog-reconfigure host-uuid="$UUID" 2>/dev/null || true
  fi
done

# Remove only the lab key that hardening installed.
if [ -f /root/xcp-lab-key.pub ] && [ -f /root/.ssh/authorized_keys ]; then
  KEY="$(cat /root/xcp-lab-key.pub)"
  log "REMOVE lab key from authorized_keys"
  if [ "$DRY" != "1" ]; then
    grep -vF "$KEY" /root/.ssh/authorized_keys > /root/.ssh/authorized_keys.new
    mv /root/.ssh/authorized_keys.new /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
  fi
fi

# Re-enable services disabled by hardening.
for d in "$ROOT"/*; do
  for f in "$d"/disabled-services.*; do
    [ -f "$f" ] || continue
    while read -r svc; do
      log "REENABLE $svc"
      [ "$DRY" = "1" ] || { systemctl unmask "$svc" 2>/dev/null || true; systemctl enable --now "$svc" 2>/dev/null || true; }
    done < "$f"
  done
done

# Firewall rules restored from the hardening session.
for d in "$ROOT"/*; do
  [ -f "$d/iptables.before" ] || continue
  log "RESTORE iptables from $d/iptables.before"
  [ "$DRY" = "1" ] || iptables-restore < "$d/iptables.before"
done

# Runtime state.
log "sysctl --system"
[ "$DRY" = "1" ] || sysctl --system >/dev/null 2>&1 || true
log "chronyd restart"
[ "$DRY" = "1" ] || systemctl restart chronyd 2>/dev/null || true
log "sshd config check"
if sshd -t >/dev/null 2>&1; then
  [ "$DRY" = "1" ] || systemctl reload sshd 2>/dev/null || true
else log "sshd -t failed: leaving SSH untouched"; fi

if [ -n "$REPORT" ]; then
  {
    echo "# XCP-ng de-hardening report"
    echo
    echo "- date: $(date -u +%FT%TZ)"
    echo "- host: $(hostname)"
    echo "- mode: $([ "$DRY" = "1" ] && echo dry-run || echo applied)"
    echo "- safety: $SAFE/etat-avant.tar.gz"
    echo "- restored files: ${#REST[@]}"
    echo "- removed files: ${#DEL[@]}"
    echo "- skipped (not managed by lab): ${#SKIP[@]}"
  } > "$REPORT"
  log "report: $REPORT"
fi
log "=== END ==="
