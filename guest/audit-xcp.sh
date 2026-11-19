#!/bin/bash
# XCP-ng 8.3 LTS read-only audit collector.
# Output contract: "@@CHECK <ID> <PASS|FAIL|NA|INFO> <text>" on stdout and TSV rows.
set -u
OUT="${1:-/tmp/xcp-audit}"
mkdir -p "$OUT"
: > "$OUT/checks.tsv"
LOG="$OUT/audit.txt"
: > "$LOG"

chk() {
  local id="$1" st="$2" txt="$3"
  printf '@@CHECK %s %s %s\n' "$id" "$st" "$txt" | tee -a "$LOG"
  printf '%s\t%s\t%s\n' "$id" "$st" "$txt" >> "$OUT/checks.tsv"
}
cmd() { printf '$ %s\n' "$1" | tee -a "$LOG"; shift; "$@" 2>&1 | tee -a "$LOG"; }
note() { printf '## %s\n' "$1" | tee -a "$LOG"; }

UUID="$(xe host-list params=uuid --minimal 2>/dev/null | awk -F, '{print $1}')"
note "HOST"
cmd "xe host-list" xe host-list params=name-label,uuid --minimal
[ -n "$UUID" ] && chk XCP.00 PASS "host uuid $UUID" || chk XCP.00 FAIL "no host uuid"

note "VERSION AND UPDATES"
VER="$(cat /etc/xensource-inventory 2>/dev/null | grep -o "PRODUCT_VERSION='[^']*'" | cut -d"'" -f2)"
KERNEL="$(uname -r)"
case "$VER" in
  8.3*) chk XCP.01 PASS "XCP-ng $VER kernel $KERNEL" ;;
  *) chk XCP.01 FAIL "XCP-ng version=$VER (expected 8.3 LTS) kernel $KERNEL" ;;
esac
YUM="$(yum check-update -q 2>/dev/null | wc -l)"
chk XCP.02 INFO "pending updates (yum check-update lines)=$YUM"

note "HTTPS ONLY / PORT 80"
if [ -n "$UUID" ]; then
  HO="$(xe host-param-get uuid="$UUID" param-name=https-only 2>/dev/null)"
  [ "$HO" = "true" ] && chk XCP.03 PASS "https-only=true" || chk XCP.03 FAIL "https-only=$HO"
else
  chk XCP.03 FAIL "cannot query https-only (no uuid)"
fi
FW80="$(iptables -S INPUT 2>/dev/null | grep -c -- '--dport 80 -j DROP')"
P80="$(ss -lnt 2>/dev/null | grep -E '\*:80 |0.0.0.0:80 ' | wc -l)"
if [ "$FW80" -gt 0 ]; then chk XCP.04 PASS "port 80 traffic dropped by firewall (listener=$P80)"
elif [ "$P80" -eq 0 ]; then chk XCP.04 PASS "port 80 not listening"
else chk XCP.04 FAIL "port 80 reachable (listener=$P80, no DROP rule)"; fi

note "SSH"
SSHD_CONF=/etc/ssh/sshd_config.d/00-xcp-hardening.conf
if grep -q '^PasswordAuthentication no' "$SSHD_CONF" 2>/dev/null; then chk XCP.05 PASS "PasswordAuthentication no"; else chk XCP.05 FAIL "password auth still allowed"; fi
if grep -q '^PermitRootLogin prohibit-password' "$SSHD_CONF" 2>/dev/null; then chk XCP.06 PASS "root key-only"; else chk XCP.06 FAIL "root login unrestricted"; fi
if grep -q '^Ciphers ' "$SSHD_CONF" 2>/dev/null; then chk XCP.07 PASS "strong ciphers configured"; else chk XCP.07 FAIL "no explicit cipher list"; fi
if sshd -t >/dev/null 2>&1; then chk XCP.08 PASS "sshd config valid"; else chk XCP.08 FAIL "sshd -t failed"; fi
if [ -s /root/.ssh/authorized_keys ]; then chk XCP.09 PASS "root authorized_keys present ($(wc -l < /root/.ssh/authorized_keys) keys)"; else chk XCP.09 FAIL "no root SSH key"; fi
SSHD_ACTIVE="$(systemctl is-active sshd 2>/dev/null)"
chk XCP.10 INFO "sshd active=$SSHD_ACTIVE"

note "NTP"
if systemctl is-active chronyd >/dev/null 2>&1; then chk XCP.11 PASS "chronyd active"; else chk XCP.11 FAIL "chronyd inactive"; fi
NTPS="$(grep -Ec '^(server|pool) ' /etc/chrony.conf 2>/dev/null)"
[ "$NTPS" -gt 0 ] && chk XCP.12 PASS "chrony sources=$NTPS" || chk XCP.12 FAIL "no chrony source"
OFF="$(chronyc tracking 2>/dev/null | grep 'System time' | awk '{print $4}')"
chk XCP.13 INFO "chrony system time offset=$OFF"

note "LOGGING"
if [ -n "$UUID" ]; then
  SYSLOG="$(xe host-param-get uuid="$UUID" param-name=logging:syslog_destination 2>/dev/null)"
  case "$SYSLOG" in
    ''|'<not set>'|'none') chk XCP.14 FAIL "no remote syslog destination" ;;
    *) chk XCP.14 PASS "remote syslog=$SYSLOG" ;;
  esac
else chk XCP.14 FAIL "cannot query syslog"; fi
JOURNAL="$(systemctl is-active systemd-journald 2>/dev/null)"
chk XCP.15 PASS "journald active=$JOURNAL"

note "DOM0 MINIMALISM"
USERS="$(awk -F: '$3>=1000 && $1!="nobody" && $1!="nfsnobody" && $1!="qemu_base" && $1!="swtpm_base" && $1!="vncterm_base" {print $1}' /etc/passwd | tr '\n' ' ')"
[ -z "$USERS" ] && chk XCP.16 PASS "no extra local users beyond XCP-ng system accounts" || chk XCP.16 FAIL "extra users: $USERS"
for svc in rpcbind avahi-daemon cups bluetooth; do
  ST="$(systemctl is-active "$svc" 2>/dev/null)"
  [ "$ST" = "active" ] && chk "XCP.17.$svc" FAIL "$svc active" || chk "XCP.17.$svc" PASS "$svc inactive/absent"
done
for pkg in unattended-upgrades fail2ban aide rkhunter; do
  rpm -q "$pkg" >/dev/null 2>&1 && chk "XCP.18.$pkg" FAIL "$pkg installed in dom0" || chk "XCP.18.$pkg" PASS "$pkg not installed"
done
UM="$(grep -h '^umask' /etc/profile.d/*.sh 2>/dev/null | tail -1)"
[ -n "$UM" ] && chk XCP.19 PASS "umask policy: $UM" || chk XCP.19 INFO "no umask policy"

note "XAPI AND POOL"
XAPI="$(systemctl is-active xapi 2>/dev/null)"
chk XCP.20 PASS "xapi active=$XAPI"
STUNNEL="$(ss -lnt 2>/dev/null | grep -E ':443 ' | wc -l)"
[ "$STUNNEL" -gt 0 ] && chk XCP.21 PASS "TLS 443 listening" || chk XCP.21 FAIL "no TLS listener"
POOL="$(xe pool-list params=uuid --minimal 2>/dev/null)"
chk XCP.22 INFO "pool uuid=$POOL"
CERT="$(ls /etc/xensource/xapi-ssl.pem 2>/dev/null | wc -l)"
[ "$CERT" -gt 0 ] && chk XCP.23 PASS "host certificate present" || chk XCP.23 INFO "no host certificate file"
CERT_SYNC="$(xe pool-certificate-sync 2>&1 | head -1)"
chk XCP.24 INFO "xe pool-certificate-sync: $CERT_SYNC"

note "NETWORK (lab scope)"
chk XCP.25 NA "management network isolation: single NAT VM, not testable here"
chk XCP.26 NA "storage/backup network isolation: single NIC lab"
chk XCP.27 NA "VM port locking / traffic rules: no guest VM in lab"
chk XCP.28 NA "BMC/IPMI: no BMC in VirtualBox"
chk XCP.29 NA "Xen Orchestra audit log: no XOA deployed"
chk XCP.30 NA "physical access/supply chain: out of lab scope"
