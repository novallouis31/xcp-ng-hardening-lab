# Research — XCP-ng hardening sources (November 2026)

## 1. Vates VMS Hardening Guide (official, primary source)

PDF: `docs/vates-vms-hardening-guide.pdf` (v0.4, 2026-10-26, 76 pages).
Landing page: https://vates.tech/en/hardening-guide/
Direct PDF: https://vates.tech/assets/pdf/vates-vms-hardening-guide-2026-11-10.pdf
Text extraction: `docs/vates-guide.txt`.

Scope: XCP-ng **8.3 LTS only** (8.2 LTS EOL 2025-09-16), Xen Orchestra 6, VSA process.
Key host-side recommendations retained for this lab (section 4 "XCP-ng Protection"):

| ID | Control | Command / setting | Guide section |
| --- | --- | --- | --- |
| XCP.01 | Current LTS version | XCP-ng 8.3 LTS, fully updated before any hardening | 4.1-4.2 |
| XCP.02 | HTTPS only | `xe host-param-set https-only=true uuid=<uuid>` | 4.4.4 |
| XCP.03 | No clear-text HTTP on 80 | consequence of XCP.02 | 4.4.4 |
| XCP.04 | SSH keys, no passwords | `PasswordAuthentication no`, ED25519 | 4.4.5 |
| XCP.05 | Restrict root SSH | `PermitRootLogin prohibit-password` | 4.4.5 |
| XCP.06 | Modern SSH crypto | strong Ciphers/MACs/Kex in `/etc/ssh/sshd_config.d/` | 4.4.5 |
| XCP.07 | Disable SSH entirely when XOA used | `xsconsole` -> Remote Service Configuration | 4.4.5 |
| XCP.08 | NTP synchronisation | install / `xe host-param-set` / `xsconsole` | 4.4.2 |
| XCP.09 | Remote syslog | `xe host-param-set logging:syslog_destination=<addr>` + `xe host-syslog-reconfigure` | 4.4.3 |
| XCP.10 | Minimal dom0 | no extra services or local users in dom0 | 4.4 |
| XCP.11 | Pool certificates in sync | `xe pool-certificate-sync` (never weaken TLS) | 4.3 |
| XCP.12 | No AD join / XAPI roles | manage users in Xen Orchestra | 4.3 |
| XCP.13 | XOA audit log | hash-chain audit of XO actions | 4.4.6 |
| XCP.14 | Management network isolated, never on Internet | VPN/ZTNA, dedicated admin network | 3.2.1, 5.1 |
| XCP.15 | Storage/backup networks isolated | dedicated NICs/subnets | 3.2.2-3.2.3 |
| XCP.16 | VM network untrusted, port locking, traffic rules | network `default-locking-mode`, SDN controller | 3.2.4 |
| XCP.17 | IPMI/BMC never on Internet | VPN/ZTNA, dedicated NIC | 4.5.3 |
| XCP.18 | Updates via RPU, master first | `xe` / Xen Orchestra Rolling Pool Update | 4.2 |
| XCP.19 | Trusted certificates, DNS-01 | no self-signed in production | 5.3 |

The guide explicitly warns **not** to modify dom0 beyond documented settings: XCP-ng is an appliance and unnecessary changes reduce supportability and increase attack surface. Our lab therefore only applies a small, reversible set of controls and audits the rest.

## 2. Community / Citizen tools

| Project | Usefulness | Adopted? |
| --- | --- | --- |
| `RasterSec/hostile-wiki`, `sausagenoods/hostile` | auditing hosting infrastructure (network-level), not host config | documented only |
| `0xWheatyz/XenTool` | generic Xen hardening toolkit, unrelated to XCP-ng dom0 | no |
| `8labs.id/guides/xcp-ng/` | nested XCP-ng + OPNsense/VPN hardening guides | design reference only |
| XCP-ng forum topic 10487 | community discussion: "XCP-ng should not be hardened by hand, but by developers through patching" | philosophical guardrail |

## 3. CIS / DISA references (adaptation base)

- **CIS Citrix Hypervisor Benchmark v1.0.0** (formerly XenServer): prescriptive guidance for installation, authentication, network, storage, VM management, logging. Not directly applicable to 8.3 dom0, but control families map to our `XCP.*` IDs.
  https://cis.blacklabs.team/citrix-hypervisor.html
- **CIS Benchmarks download portal**: https://portal.cisecurity.org/benchmarks
- **DISA STIG library**: https://public.cyber.mil/stigs/downloads/
- **Citrix DISA STIG tech zone**: https://community.citrix.com/tech-zone/build/tech-papers/citrix-disa-stigs
- **NIST checklist for Xen**: https://ncp.nist.gov/checklist/203 (historical, Xen 3.2)

No OpenSCAP content specific to XCP-ng dom0 was found; CIS/DISA PDFs are guidance sources, not runnable scripts.

## 4. Decision

Primary source = Vates guide. Controls that require a Xen Orchestra appliance or physical network changes (XOA audit log, VPN/ZTNA, IPMI, storage isolation, port locking) are **audited as N/A** in a single-host NAT lab and reported honestly, not faked.

The automatable host controls are: HTTPS-only, SSH hardening via drop-in, NTP, remote syslog, rpcbind minimisation, dom0 minimalism, password policy and service state. These are implemented in `guest/apply-xcp.sh` and reverted in `guest/deharden-xcp.sh`.
