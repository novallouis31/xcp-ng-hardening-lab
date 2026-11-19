#!/bin/bash
# Reversible hardening for XCP-ng 8.3 LTS dom0 (lab use only).
# Usage: LEVEL=1|2|3 DRY_RUN=1 bash apply-xcp.sh
# Based on the Vates VMS Hardening Guide v0.4 (see docs/RESEARCH.md).
set -u
LEVEL="${LEVEL:-1}"
DRY_RUN="${DRY_RUN:-0}"
TS="$(date +%Y%m%d-%H%M%S)"
if [ "$DRY_RUN" = "1" ]; then
  BACKUP_DIR="/tmp/xcp-dryrun-$TS"
else
  BACKUP_DIR="/root/xcp-hardening-backups/$TS"
fi
LOG="/tmp/xcp-hardening-$TS.log"
CREATED="$BACKUP_DIR/created.list"
MODIFIED="$BACKUP_DIR/modified.list"
mkdir -p "$BACKUP_DIR"
: > "$CREATED"; : > "$MODIFIED"

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }
run() { log "CMD: $*"; [ "$DRY_RUN" = "1" ] || "$@" >>"$LOG" 2>&1; }
backup() {
  local f="$1"
  [ -e "$f" ] || return 0
  if [ "$DRY_RUN" = "1" ]; then log "DRY backup $f"; return 0; fi
  mkdir -p "$BACKUP_DIR$(dirname "$f")"
  cp -a "$f" "$BACKUP_DIR$f.$TS"
  echo "$f" >> "$MODIFIED"
}
write_file() {
  local path="$1" mode="$2"; shift 2
  local content="$*"
  if [ -f "$path" ] && [ "$(cat "$path" 2>/dev/null)" = "$content" ]; then log "IDEMPOTENT $path"; return 0; fi
  backup "$path"
  [ -e "$path" ] || echo "$path" >> "$CREATED"
  if [ "$DRY_RUN" = "1" ]; then log "DRY write $path ($mode)"; return 0; fi
  mkdir -p "$(dirname "$path")"
  printf '%s\n' "$content" > "$path.tmp"
  chmod "$mode" "$path.tmp"
  mv "$path.tmp" "$path"
  log "WROTE $path ($mode)"
}

log "=== XCP-ng hardening LEVEL=$LEVEL DRY_RUN=$DRY_RUN ==="
rpm -q xcp-ng-release >/dev/null 2>&1 || { log "ERROR: not an XCP-ng host"; exit 2; }
UUID="$(xe host-list params=uuid --minimal 2>/dev/null | awk -F, '{print $1}')"
[ -n "$UUID" ] || { log "ERROR: no host uuid"; exit 3; }

# Block 1 (L1): install lab pubkey BEFORE restricting SSH.
KEY=/root/xcp-lab-key.pub
if [ -f "$KEY" ]; then
  mkdir -p /root/.ssh
  touch /root/.ssh/authorized_keys
  chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys
  if ! grep -qF "$(cat "$KEY")" /root/.ssh/authorized_keys; then
    log "Installing lab SSH key"
    [ "$DRY_RUN" = "1" ] || cat "$KEY" >> /root/.ssh/authorized_keys
  else log "Lab SSH key already installed"; fi
else
  log "WARNING: $KEY missing; SSH restriction will be skipped"
  NOKEY=1
fi

# Block 2 (L1): HTTPS only (Vates 4.4.4). Record old value for de-hardening.
CUR="$(xe host-param-get uuid="$UUID" param-name=https-only 2>/dev/null)"
echo "$CUR" > "$BACKUP_DIR/https-only.before"
if [ "$CUR" != "true" ]; then
  log "Setting https-only=true"
  run xe host-param-set uuid="$UUID" https-only=true
else log "https-only already true"; fi

# Block 2b (L1): xapi keeps a local port 80 listener even with https-only=true;
# drop the traffic at the firewall level (XCP-ng 8.3 behaviour observed in lab).
if iptables -S INPUT 2>/dev/null | grep -q -- '--dport 80 -j DROP'; then
  log "port 80 already dropped"
else
  if [ "$DRY_RUN" = "1" ]; then log "DRY iptables DROP port 80"; else
    iptables-save > "$BACKUP_DIR/iptables.before"
    echo "iptables" > "$BACKUP_DIR/iptables-restored.flag"
    iptables -I INPUT -p tcp --dport 80 -j DROP
  fi
  log "DROPPED inbound port 80"
fi

# Block 3 (L1): SSH drop-in (Vates 4.4.5).
if [ "${NOKEY:-0}" != "1" ]; then
  write_file /etc/ssh/sshd_config.d/00-xcp-hardening.conf 600 \
"# XCP-ng lab hardening (Vates guide 4.4.5)
PasswordAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
HostKeyAlgorithms ssh-ed25519,rsa-sha2-512,rsa-sha2-256
KexAlgorithms curve25519-sha256,diffie-hellman-group-exchange-sha256
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2"
  if [ "$DRY_RUN" != "1" ] && ! sshd -t >/dev/null 2>&1; then
    log "ERROR: sshd -t failed, removing drop-in to avoid lockout"
    rm -f /etc/ssh/sshd_config.d/00-xcp-hardening.conf
    cp -a "$BACKUP_DIR/etc/ssh/sshd_config.d/00-xcp-hardening.conf.$TS" /etc/ssh/sshd_config.d/00-xcp-hardening.conf 2>/dev/null || true
    exit 4
  fi
  run systemctl reload sshd
fi

# Block 4 (L1): NTP (Vates 4.4.2). Lab source configurable.
NTP_SERVER="${NTP_SERVER:-10.0.2.3}"
if [ -f /etc/chrony.conf ]; then
  backup /etc/chrony.conf
  if [ "$DRY_RUN" = "1" ]; then log "DRY chrony source $NTP_SERVER"; else
    grep -q "server $NTP_SERVER" /etc/chrony.conf || printf '\nserver %s iburst\n' "$NTP_SERVER" >> /etc/chrony.conf
  fi
  run systemctl restart chronyd
fi

# Block 5 (L2): remote syslog (Vates 4.4.3) when provided.
if [ "$LEVEL" -ge 2 ] && [ -n "${SYSLOG_SERVER:-}" ]; then
  OLD="$(xe host-param-get uuid="$UUID" param-name=logging:syslog_destination 2>/dev/null)"
  echo "$OLD" > "$BACKUP_DIR/syslog.before"
  run xe host-param-set uuid="$UUID" "logging:syslog_destination=$SYSLOG_SERVER"
  run xe host-syslog-reconfigure host-uuid="$UUID"
fi

# Block 6 (L2): minimise dom0 network services.
if [ "$LEVEL" -ge 2 ]; then
  for svc in rpcbind; do
    if systemctl is-active "$svc" >/dev/null 2>&1; then
      echo "$svc" > "$BACKUP_DIR/disabled-services.$TS"
      run systemctl disable --now "$svc"
    fi
  done
fi

# Block 7 (L3): login policy and banner (defense in depth, Vates 4.4.1).
if [ "$LEVEL" -ge 3 ]; then
  write_file /etc/profile.d/99-xcp-umask.sh 644 'umask 027'
  write_file /etc/issue.net 644 'Authorized access only - XCP-ng lab host'
fi

# Generate rollback script (real runs only).
if [ "$DRY_RUN" = "1" ]; then
  log "DRY: no rollback script generated"
  log "=== END (dry-run) ==="
  exit 0
fi
RB=/root/rollback-xcp-hardening.sh
cat > "$RB" <<EOF
#!/bin/bash
# Generated by apply-xcp.sh on $TS. Restores files backed up in $BACKUP_DIR.
set -u
B="$BACKUP_DIR"
[ -d "\$B" ] || { echo "backup dir missing"; exit 1; }
while read -r f; do
  snap="\$B\$f.$TS"
  [ -f "\$snap" ] && cp -a "\$snap" "\$f" || rm -f "\$f"
done < "\$B/modified.list"
while read -r f; do rm -f "\$f"; done < "\$B/created.list"
if [ -s "\$B/https-only.before" ]; then
  U="\$(xe host-list params=uuid --minimal | awk -F, '{print \$1}')"
  xe host-param-set uuid="\$U" "https-only=\$(cat "\$B/https-only.before")"
fi
systemctl restart chronyd 2>/dev/null || true
sshd -t && systemctl reload sshd || true
echo "rollback done"
EOF
chmod 700 "$RB"
log "Rollback script: $RB"
log "=== END (files modified=$(wc -l < "$MODIFIED"), created=$(wc -l < "$CREATED")) ==="
