# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

3-node HA k3s homelab cluster (k3s v1.31.4+k3s1) managed via GitOps. Three-layer bootstrap: cloud-init → Ansible → Flux CD. All in-cluster state post-bootstrap is reconciled by Flux from the `main` branch.

Nodes: `node-0` (10.0.110.10, init), `node-1` (10.0.110.11, join), `node-2` (10.0.110.12, join) on VLAN 110. API VIP: 10.0.110.200 (kube-vip). MetalLB pool: 10.0.110.201–219.

## Commands

### Run tests
```bash
pip install -r tests/requirements.txt
pytest                    # all ~140 tests
pytest tests/test_flux_kustomizations.py  # single module
pytest -k "test_name"     # single test by name
```

### Bootstrap cluster
```bash
# 1. Apply cloud-init per node
bash bootstrap/scripts/apply-cloud-init-node-0.sh
# 2. Run Ansible
cd bootstrap/ansible && ansible-playbook site.yaml
# 3. Validate
ansible-playbook validate.yaml
# 4. Cleanup a node (if needed)
ansible-playbook cleanup.yaml
```

### Flux operations (requires cluster access)
```bash
flux get kustomizations           # reconciliation status
flux get helmreleases -A          # helm release status
flux reconcile kustomization flux-system --with-source  # force sync
```

### SOPS encryption
```bash
# Encrypt a file (requires age.key)
export SOPS_AGE_KEY_FILE=bootstrap/ansible/age.key
sops -e -i gitops/path/to/secret.yaml
sops -d -i gitops/path/to/secret.yaml  # decrypt
```

## Architecture

### Flux Kustomization Dependency DAG
```
flux-system (root, syncs from git)
└── platform-crds (HelmRepositories)
    └── platform-core (cert-manager, ingress-nginx, metallb, network-policies)
        ├── platform-issuers (ClusterIssuer, wildcard cert)
        ├── platform-metallb-config (IPAddressPool, L2Advertisement)
        ├── storage (longhorn HelmRelease)
        │   ├── platform-longhorn-config (recurring snapshot/backup jobs)
        │   ├── platform-longhorn-classes (StorageClasses)
        │   ├── data-services (redis, cnpg, minio) [SUSPENDED]
        │   └── observability (prometheus, grafana, loki, promtail)
        │       └── platform-observability-config (alerting rules)
        └── apps (agentic, custom workloads) [depends on observability]
```

All Flux Kustomizations use `prune: true`, `wait: true`, and SOPS decryption via `sops-age` secret.

### Key directories
- `gitops/clusters/homelab-k3s/` — Flux Kustomization CRs (the DAG above)
- `gitops/clusters/homelab-k3s/flux-system/` — Flux bootstrap (do not edit gotk-components.yaml)
- `gitops/infrastructure/` — Platform HelmReleases and manifests
- `gitops/data-services/` — Stateful services (redis, cnpg, minio)
- `gitops/apps/` — Application workloads
- `bootstrap/cloud-init/` — Per-node first-boot YAML
- `bootstrap/ansible/` — Ansible playbooks and 7 roles
- `tests/` — Property-based tests (pytest + hypothesis)

### SOPS encryption rules (`.sops.yaml`)
- `bootstrap/ansible/inventory/group_vars/vault.yaml` — Ansible vault
- `gitops/.*secret.*\.yaml$` — Kubernetes secrets in gitops tree
- `\.enc\.yaml$` — Catch-all encrypted files
- Private key: `bootstrap/ansible/age.key` (git-ignored)

### Testing approach
Property-based testing with hypothesis validating structural correctness: cloud-init completeness, Ansible inventory/variables schema, k3s install flags, Flux DAG consistency, SOPS config, workload profiles, repo structure, and cleanup idempotency. Tests read YAML files from the repo — no cluster needed.

## Conventions

- HelmRelease chart versions use semver wildcards (e.g., `v1.16.*`) — patch versions float
- Each infrastructure component gets its own directory with `kustomization.yaml`, `helmrelease.yaml`, and `namespace.yaml`
- Post-install CRs (IPAddressPool, StorageClass, RecurringJob, etc.) are split into separate Kustomizations with explicit `dependsOn` on the parent HelmRelease's Kustomization
- Ingress hostnames use `*.cluster.arpa` domain with TLS via `internal-ca` ClusterIssuer
- Commit messages follow conventional commits: `fix:`, `feat:`, etc.
