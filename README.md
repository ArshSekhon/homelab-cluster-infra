# homelab-cluster-infra

Reproducible 3-node HA Kubernetes platform built on k3s with embedded etcd, managed entirely through GitOps.

## Architecture

Three `node-{0,1,2}` machines on VLAN 110 (`10.0.110.0/24`), each with an Intel i5-10600T, 16 GiB RAM, and NVMe storage. The platform bootstraps in three layers:

1. **cloud-init** — first-boot OS baseline (hostname, users, kernel modules, sysctls, swap, packages)
2. **Ansible** — OS hardening, k3s installation, HA cluster formation, SOPS secret bootstrap
3. **Flux CD** — all in-cluster resources delivered via GitOps with dependency ordering and health gates

```
API VIP (kube-vip):  10.0.110.200
MetalLB pool:        10.0.110.201–219
Domain:              *.cluster.arpa
```

## Repository Structure

```
bootstrap/
├── cloud-init/              # Per-node first-boot configs (node-0, node-1, node-2)
└── ansible/
    ├── ansible.cfg
    ├── inventory/
    │   ├── hosts.yaml
    │   └── group_vars/
    │       ├── k3s_servers.yaml
    │       └── vault.yaml       # SOPS-encrypted secrets
    ├── roles/
    │   ├── base_hardening/      # Idempotent OS hardening
    │   ├── k3s_server_init/     # First server + kube-vip + etcd snapshots
    │   ├── k3s_server_join/     # Join additional servers
    │   ├── kubeconfig_export/   # Retrieve and rewrite kubeconfig
    │   ├── cluster_smoke_tests/ # Validate cluster health
    │   ├── sops_bootstrap/      # Create sops-age secret for Flux
    │   └── node_cleanup/        # Safe/full node reset
    ├── site.yaml                # Main bootstrap playbook
    ├── validate.yaml            # Smoke test playbook
    └── cleanup.yaml             # Node cleanup playbook

gitops/
├── clusters/homelab-k3s/    # Flux Kustomizations (dependency DAG)
├── infrastructure/
│   ├── metallb/             # L2 load balancer
│   ├── ingress-nginx/       # Ingress controller
│   ├── cert-manager/        # Internal CA + wildcard cert
│   ├── network-policies/    # Baseline deny + allow rules
│   ├── longhorn/            # Distributed block storage
│   ├── observability/       # Prometheus, Grafana, Alertmanager, Loki
│   └── crds/                # CRD prerequisites
├── data-services/
│   ├── cloudnative-pg/      # 3-instance HA PostgreSQL
│   ├── redis/               # Sentinel-mode Redis
│   └── minio/               # Optional S3-compatible storage
└── apps/
    ├── agentic/             # Agentic AI workload namespace + profiles
    ├── custom/              # Custom app namespace + profiles
    └── shared-templates/    # Ingress and certificate templates

tests/                       # Property-based + unit tests (hypothesis + pytest)
docs/                        # Runbooks and reference docs
```

## Prerequisites

- 3 Ubuntu 24.04 nodes with cloud-init support
- Operator workstation with Ansible, kubectl, flux CLI, age, sops
- OPNsense (or equivalent) providing DHCP reservations and DNS for `*.cluster.arpa`
- (Optional) Off-cluster NAS/S3 endpoint for backups

## Quick Start

### 1. Apply cloud-init

Flash each node's cloud-init config via USB, PXE, or your provisioning method:

```bash
# Validate configs before flashing (optional)
cloud-init schema --config-file bootstrap/cloud-init/node-0.yaml
```

SSH keys are imported automatically from `github.com/arshsekhon.keys` on first boot — no manual key editing needed.

Boot each node. cloud-init runs on first boot, sets hostname/users/kernel/packages, and reboots. Wait for all 3 nodes to come back up before proceeding.

### 2. Generate SOPS age key

```bash
age-keygen -o bootstrap/ansible/age.key
```

Copy the public key (the `age1xxx...` line printed to stdout) into `.sops.yaml`, replacing the placeholder. Then tell SOPS where the private key lives:

```bash
export SOPS_AGE_KEY_FILE=bootstrap/ansible/age.key
```

Add this to your `~/.zshrc` so it persists across sessions.

### 3. Configure vault secrets

```bash
# Generate a random k3s cluster join token
openssl rand -hex 32

# Open the vault file (decrypts on open, re-encrypts on save)
# Replace CHANGE_ME_BEFORE_ENCRYPTING with the token from above
sops bootstrap/ansible/inventory/group_vars/vault.yaml
```

### 4. Run Ansible

```bash
cd bootstrap/ansible

# Bootstrap first server (node-0)
ansible-playbook site.yaml --limit node-0

# Join remaining servers
ansible-playbook site.yaml --limit node-1,node-2

# Validate cluster
ansible-playbook validate.yaml
```

### 5. Bootstrap Flux

```bash
flux bootstrap github \
  --owner=<github-user> \
  --repository=<repo-name> \
  --branch=main \
  --path=gitops/clusters/homelab-k3s \
  --personal
```

Flux reconciles the full platform stack in dependency order:
`platform-crds` → `platform-core` → `storage` + `observability` → `data-services` → `apps`

## Platform Services

| Service | Access | Purpose |
|---------|--------|---------|
| Grafana | `grafana.cluster.arpa` | Dashboards and alerting |
| Prometheus | `prometheus.cluster.arpa` | Metrics |
| Longhorn UI | `longhorn.cluster.arpa` | Storage management |
| MinIO Console | `minio.cluster.arpa` | Object storage (when enabled) |
| MinIO S3 API | `s3.cluster.arpa` | S3 endpoint (when enabled) |

## Storage

- **longhorn** (default) — 2 replicas, general workloads
- **longhorn-critical** — 3 replicas, databases and stateful services
- Daily snapshots (retain 7), weekly backups to off-cluster S3 (when configured)

## Backup Strategy

| Layer | Schedule | Retention | Target |
|-------|----------|-----------|--------|
| etcd snapshots | Every 6h | 5 snapshots | Local on each server node |
| Longhorn | Daily snapshots, weekly backups | 7 / 4 | Local + off-cluster S3 |
| CloudNativePG | Daily base + continuous WAL | 14 days | Off-cluster S3 |

See [docs/runbook-backup-restore.md](docs/runbook-backup-restore.md) for verification and restore drill procedures.

## Node Cleanup

```bash
cd bootstrap/ansible

# Safe mode — remove k3s, preserve storage data
ansible-playbook cleanup.yaml --limit <node>

# Full mode — complete reset to pre-bootstrap state
ansible-playbook cleanup.yaml --limit <node> \
  --extra-vars "cleanup_mode=full confirm_full_cleanup=yes"
```

## Testing

The repo includes 140 tests covering 9 correctness properties validated with property-based testing (hypothesis).

```bash
pip install -r tests/requirements.txt
pytest
```

| Property | What it validates |
|----------|-------------------|
| 1. Cloud-init completeness | Hostname, packages, modules, sysctls, reboot |
| 2. Ansible inventory | Node IPs, FQDNs, k3s roles |
| 3. k3s install flags | Pinned version, cluster-init, disable flags |
| 4. Kubeconfig rewrite | VIP endpoint substitution |
| 5. Flux dependency chain | DAG ordering, health gates, SOPS decryption |
| 6. Workload profiles | Resource limits, probes, PDB for all profiles |
| 7. Repo structure | Required directories and files |
| 8. Ansible variables | All required config keys present |
| 9. Cleanup round-trip | Full cleanup reverts all bootstrap configs |

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Distribution | k3s + embedded etcd | Lightweight, single-binary HA |
| API HA | kube-vip (L2/ARP) | Floating VIP, works pre-MetalLB |
| GitOps | Flux CD v2 | Native Kustomization, dependency ordering |
| Storage | Longhorn | Distributed replicated storage, k3s-native |
| Database | CloudNativePG | K8s-native PostgreSQL with HA failover |
| Secrets | SOPS + age | Git-friendly, no external dependencies |
| Observability | kube-prometheus-stack + Loki | Full metrics, alerting, and log aggregation |

## Documentation

- [Hardware and network context](docs/k8s-homelab-memory-context.md)
- [Backup and restore runbook](docs/runbook-backup-restore.md)
