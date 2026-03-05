# Implementation Plan: k3s Homelab Platform

## Overview

This plan implements the k3s homelab platform in phases matching the bootstrap flow: repo structure → cloud-init → Ansible → Flux manifests → platform services → storage → data services → observability → app foundation → cleanup. Each phase builds on the previous and ends with a checkpoint. Property-based tests use Python `hypothesis` to validate structural correctness of generated configs.

## Tasks

- [ ] 1. Set up repository structure and testing framework
  - [ ] 1.1 Create the directory scaffold
    - Create all directories: `bootstrap/cloud-init/`, `bootstrap/ansible/inventory/`, `bootstrap/ansible/roles/{base_hardening,k3s_server_init,k3s_server_join,kubeconfig_export,cluster_smoke_tests,node_cleanup}/tasks/`, `bootstrap/ansible/roles/*/defaults/`, `gitops/clusters/homelab-k3s/flux-system/`, `gitops/infrastructure/{metallb,ingress-nginx,cert-manager,network-policies,crds,longhorn,observability}/`, `gitops/data-services/{cloudnative-pg,minio,redis}/`, `gitops/apps/{agentic,custom}/`
    - Create placeholder `.gitkeep` files in empty leaf directories
    - _Requirements: 10.1, 9.2_

  - [ ] 1.2 Create `.sops.yaml` configuration file at repo root
    - Define encryption rules per path (e.g., `bootstrap/ansible/group_vars/vault.yaml`)
    - Reference age public key placeholder
    - _Requirements: 2.7_

  - [ ] 1.3 Set up Python test infrastructure
    - Create `tests/` directory with `requirements.txt` (hypothesis, pyyaml, pytest)
    - Create `tests/conftest.py` with shared fixtures for loading YAML files
    - _Requirements: Testing Strategy_

  - [ ]* 1.4 Write property test for repository structure completeness
    - **Property 7: Repository structure completeness**
    - **Validates: Requirements 9.2, 10.1**

- [ ] 2. Checkpoint - Verify repo structure
  - Ensure all directories exist, test framework runs, ask the user if questions arise.

- [ ] 3. Create cloud-init configurations
  - [ ] 3.1 Create per-node cloud-init YAML files
    - Create `bootstrap/cloud-init/node-0.yaml`, `node-1.yaml`, `node-2.yaml`
    - Each file sets hostname/FQDN, creates `kadmin` user with SSH key placeholder, disables swap, installs baseline packages, loads kernel modules, applies sysctls, enables timesyncd, triggers reboot
    - Only difference between files: hostname and FQDN (`node-{N}.cluster.arpa`)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 3.2 Write property test for cloud-init configuration completeness
    - **Property 1: Cloud-init configuration completeness**
    - **Validates: Requirements 1.1, 1.2, 1.4, 1.5, 1.6**

- [ ] 4. Create Ansible inventory and group variables
  - [ ] 4.1 Create Ansible inventory file
    - Create `bootstrap/ansible/inventory/hosts.yaml` with `k3s_servers` group
    - Map each node to IP, FQDN, and k3s_role (init/join)
    - _Requirements: 2.1_

  - [ ] 4.2 Create Ansible group variables
    - Create `bootstrap/ansible/inventory/group_vars/k3s_servers.yaml` with all required variables: `cluster_name`, `k3s_version`, `k3s_token`, `api_server_vip`, `api_server_port`, `disable_components`, `admin_user`, `kube_vip_version`, `metallb_pool_start`, `metallb_pool_end`, `backup_s3_endpoint`, `backup_bucket`, `backup_secret_ref`, `minio_enabled`
    - Create `bootstrap/ansible/inventory/group_vars/vault.yaml` placeholder for encrypted secrets
    - _Requirements: 10.2, 2.7_

  - [ ] 4.3 Create `ansible.cfg`
    - Set inventory path, roles path, SSH settings, vault password file reference
    - _Requirements: 2.1_

  - [ ]* 4.4 Write property test for Ansible inventory correctness
    - **Property 2: Ansible inventory maps all nodes correctly**
    - **Validates: Requirements 2.1**

  - [ ]* 4.5 Write property test for Ansible variables schema completeness
    - **Property 8: Ansible variables schema completeness**
    - **Validates: Requirements 10.2**

- [ ] 5. Create Ansible roles - base hardening and k3s bootstrap
  - [ ] 5.1 Implement `base_hardening` role
    - Create `roles/base_hardening/tasks/main.yaml`
    - Idempotent checks: verify packages installed, kernel modules loaded, sysctls applied, swap disabled, timesyncd running
    - _Requirements: 2.2_

  - [ ] 5.2 Implement `k3s_server_init` role
    - Create `roles/k3s_server_init/tasks/main.yaml` and `roles/k3s_server_init/defaults/main.yaml`
    - Install k3s at pinned version with `--cluster-init`, `--tls-san={{ api_server_vip }}`, disable traefik and servicelb
    - Deploy kube-vip static pod manifest to `/var/lib/rancher/k3s/server/manifests/`
    - Wait for k3s to be ready
    - _Requirements: 2.3_

  - [ ] 5.3 Implement `k3s_server_join` role
    - Create `roles/k3s_server_join/tasks/main.yaml` and `roles/k3s_server_join/defaults/main.yaml`
    - Install k3s with `--server https://{{ api_server_vip }}:{{ api_server_port }}` and `--token {{ k3s_token }}`
    - Same disable flags and TLS SAN as init role
    - Wait for node to join and report Ready
    - _Requirements: 2.4_

  - [ ] 5.4 Implement `kubeconfig_export` role
    - Create `roles/kubeconfig_export/tasks/main.yaml`
    - Fetch `/etc/rancher/k3s/k3s.yaml` from node-0
    - Rewrite server endpoint to `https://{{ api_server_vip }}:{{ api_server_port }}`
    - Save to operator workstation
    - _Requirements: 2.5_

  - [ ] 5.5 Implement `cluster_smoke_tests` role
    - Create `roles/cluster_smoke_tests/tasks/main.yaml`
    - Validate: all 3 nodes Ready, CoreDNS pods running, kube-system pods healthy
    - Use `kubectl` commands with the exported kubeconfig
    - _Requirements: 2.6_

  - [ ]* 5.6 Write property test for k3s install flags correctness
    - **Property 3: k3s install flags are correct for each role**
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 5.7 Write property test for kubeconfig endpoint rewrite
    - **Property 4: Kubeconfig endpoint rewrite**
    - **Validates: Requirements 2.5**

- [ ] 6. Create Ansible playbooks and wire roles together
  - [ ] 6.1 Create `site.yaml` playbook
    - Orchestrate roles based on host's `k3s_role` variable: `base_hardening` for all, `k3s_server_init` for init nodes, `k3s_server_join` for join nodes, `kubeconfig_export` for init node
    - _Requirements: 2.8_

  - [ ] 6.2 Create `validate.yaml` playbook
    - Run `cluster_smoke_tests` role against localhost using exported kubeconfig
    - _Requirements: 2.6, 2.8_

  - [ ] 6.3 Create `cleanup.yaml` playbook
    - Accept `cleanup_mode` variable (default: `safe`)
    - Require `confirm_full_cleanup=yes` for full mode
    - Run `node_cleanup` role
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

- [ ] 7. Implement node cleanup role
  - [ ] 7.1 Implement `node_cleanup` role with safe/full modes
    - Create `roles/node_cleanup/tasks/main.yaml` and `roles/node_cleanup/defaults/main.yaml`
    - Safe mode: stop k3s, run uninstall script, remove `/etc/rancher`, `/var/lib/rancher`, `/var/lib/kubelet`, CNI dirs
    - Full mode (with confirmation): additionally remove Longhorn data, containerd data, iptables cleanup, unload kernel modules, remove sysctl and module-load configs
    - All tasks use conditional checks for idempotency
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 7.2 Write property test for cleanup config revert (round-trip)
    - **Property 9: Cleanup reverts bootstrap kernel/sysctl configuration**
    - **Validates: Requirements 11.4**

- [ ] 8. Checkpoint - Verify Ansible artifacts
  - Ensure all roles, playbooks, and inventory are syntactically valid. Run `ansible-lint` if available. Ensure all property tests pass. Ask the user if questions arise.

- [ ] 9. Create Flux bootstrap and Kustomization manifests
  - [ ] 9.1 Create Flux Kustomization manifests in `gitops/clusters/homelab-k3s/`
    - Create `platform-crds.yaml`, `platform-core.yaml`, `storage.yaml`, `data-services.yaml`, `observability.yaml`, `apps.yaml`
    - Each with correct `dependsOn`, `interval`, `path`, `prune: true`, `wait: true`
    - Add `decryption` config referencing `sops-age` secret
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 9.2 Write property test for Flux Kustomization dependency chain
    - **Property 5: Flux Kustomization dependency chain and health configuration**
    - **Validates: Requirements 3.2, 3.3**

- [ ] 10. Create core platform service manifests
  - [ ] 10.1 Create MetalLB manifests
    - Create `gitops/infrastructure/metallb/` with HelmRelease, IPAddressPool (`10.0.110.201-219`), L2Advertisement
    - _Requirements: 4.1_

  - [ ] 10.2 Create ingress-nginx manifests
    - Create `gitops/infrastructure/ingress-nginx/` with HelmRelease, set as default IngressClass
    - _Requirements: 4.2_

  - [ ] 10.3 Create cert-manager manifests
    - Create `gitops/infrastructure/cert-manager/` with HelmRelease, self-signed root CA, ClusterIssuer `internal-ca`, wildcard Certificate for `*.cluster.arpa`
    - _Requirements: 4.3, 4.4_

  - [ ] 10.4 Create baseline network policies
    - Create `gitops/infrastructure/network-policies/` with default-deny ingress, allow from ingress namespace, allow intra-namespace, allow kube-system and monitoring
    - _Requirements: 4.5_

- [ ] 11. Create storage manifests
  - [ ] 11.1 Create Longhorn manifests
    - Create `gitops/infrastructure/longhorn/` with HelmRelease, StorageClass `longhorn` (replicas=2, default), StorageClass `longhorn-critical` (replicas=3)
    - Configure node labels for storage-tier, disk reservation threshold (25%)
    - Configure recurring snapshot jobs (daily, retain 7) and backup jobs (weekly, conditional on backup target)
    - _Requirements: 5.1, 5.2_

- [ ] 12. Create data services manifests
  - [ ] 12.1 Create CloudNativePG manifests
    - Create `gitops/data-services/cloudnative-pg/` with operator HelmRelease, 3-instance Cluster CR using `longhorn-critical`, backup schedule (conditional on backup target), pod anti-affinity
    - _Requirements: 5.3, 5.4_

  - [ ] 12.2 Create MinIO manifests (optional, gated)
    - Create `gitops/data-services/minio/` with Tenant CR: 3 servers × 2 volumes, `longhorn-critical` StorageClass, Ingress for `s3.cluster.arpa` and `minio.cluster.arpa`
    - Include a Kustomize patch or condition to skip when `minio_enabled: false`
    - _Requirements: 5.5_

  - [ ] 12.3 Create Redis manifests
    - Create `gitops/data-services/redis/` with HelmRelease for Redis Sentinel mode
    - _Requirements: 6.2_

- [ ] 13. Create observability manifests
  - [ ] 13.1 Create kube-prometheus-stack manifests
    - Create `gitops/infrastructure/observability/` with HelmRelease for kube-prometheus-stack
    - Configure Prometheus (15d retention), Alertmanager (node down, pod crash, disk pressure rules), Grafana with ingress at `grafana.cluster.arpa`
    - Add disk usage alert at 70% per node
    - _Requirements: 7.1_

  - [ ] 13.2 Create Loki manifests
    - Create Loki + Promtail HelmRelease in observability directory
    - Configure 7d retention, integrate as Grafana datasource
    - _Requirements: 7.1_

- [ ] 14. Create application foundation manifests
  - [ ] 14.1 Create namespace manifests
    - Create `gitops/apps/agentic/namespace.yaml` and `gitops/apps/custom/namespace.yaml`
    - Add labels and annotations, default StorageClass annotation per namespace
    - _Requirements: 6.1_

  - [ ] 14.2 Create workload profile templates
    - Create workload profile definitions for `agentic-realtime`, `agentic-batch`, `custom-app`
    - Each specifies CPU/memory requests/limits, probe configs, PDB settings
    - Create shared ingress and certificate templates
    - _Requirements: 6.3, 6.2_

  - [ ]* 14.3 Write property test for workload profile completeness
    - **Property 6: Workload profile completeness**
    - **Validates: Requirements 6.3**

- [ ] 15. Create backup and day-2 operations manifests
  - [ ] 15.1 Create etcd snapshot CronJob or k3s config
    - Configure automatic etcd snapshots via k3s server flags or a CronJob
    - _Requirements: 7.3_

  - [ ] 15.2 Create backup verification and restore drill documentation
    - Add runbook entries for Longhorn backup verification, CNPG backup restore, monthly drill procedure
    - _Requirements: 7.3, 7.4_

- [ ] 16. Checkpoint - Verify all manifests
  - Ensure all YAML manifests are syntactically valid. Ensure all property tests pass. Ask the user if questions arise.

- [ ] 17. Create SOPS bootstrap and Flux wiring
  - [ ] 17.1 Add SOPS age key bootstrap to Ansible
    - Add a task to `k3s_server_init` role (or a new role) that creates the `sops-age` secret in `flux-system` namespace from the age key file
    - Add Flux bootstrap command to the playbook or document as a manual step
    - _Requirements: 2.7, 3.1_

  - [ ] 17.2 Wire Flux decryption in all Kustomizations
    - Ensure each Kustomization in `gitops/clusters/homelab-k3s/` has `spec.decryption` referencing `sops-age`
    - _Requirements: 3.1_

- [ ] 18. Final checkpoint - Full validation
  - Ensure all tests pass, all manifests are valid, directory structure is complete. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use Python `hypothesis` library with minimum 100 iterations
- The implementation is primarily YAML (cloud-init, Ansible, Kubernetes manifests) with Python for tests
- Ansible roles use Jinja2 templating for variable substitution
- All sensitive values use SOPS/age encryption in the Git repo
