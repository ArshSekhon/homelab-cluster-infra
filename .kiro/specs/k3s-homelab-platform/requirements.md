# Requirements Document

## Introduction

This document specifies the requirements for a reproducible, HA 3-node k3s Kubernetes platform on the `dynamind-node-{0,1,2}` homelab cluster. The platform uses cloud-init for first-boot baseline, Ansible for OS hardening and k3s bootstrap, and a GitOps controller for all in-cluster platform and application delivery. Target workloads include agentic tools, custom applications, ingress/reverse proxy, object storage, and databases with durable storage and off-cluster backups.

Reference: [`docs/k8s-homelab-memory-context.md`](../../docs/k8s-homelab-memory-context.md) for hardware, network, and environment details.

## Glossary

- **Platform**: The complete Kubernetes cluster including all infrastructure services, storage, data services, and application foundations deployed across the three homelab nodes.
- **Node**: One of the three physical machines (`dynamind-node-0`, `dynamind-node-1`, `dynamind-node-2`) running Ubuntu 24.04.4 LTS.
- **Cloud_Init**: The cloud-init subsystem responsible for first-boot OS configuration on each Node.
- **Ansible_Controller**: The Ansible automation subsystem running on the operator workstation that configures Nodes and bootstraps k3s.
- **K3s_Cluster**: The 3-server HA k3s Kubernetes cluster with embedded etcd running across all Nodes, with a floating API VIP (`10.0.110.200`) for HA API access.
- **GitOps_Controller**: The GitOps controller deployed in-cluster that reconciles all resources from the Git repository.
- **Load_Balancer**: The bare-metal load balancer providing service IPs from the reserved pool `10.0.110.201-219`.
- **Ingress_Controller**: The ingress controller receiving external traffic on a MetalLB-assigned IP from the service pool.
- **Certificate_Manager**: The controller managing TLS certificate lifecycle using an internal CA issuer for `*.cluster.arpa`.
- **Storage_System**: The distributed block storage system providing default and critical StorageClasses with replication.
- **Data_Services**: The set of stateful data workloads (databases, object stores, caches) deployed with operator-managed lifecycle, replication, and backup capabilities.
- **Observability_Stack**: The monitoring and logging subsystem providing metrics, alerting, dashboards, and centralized log aggregation.
- **GitOps_Repo**: The Git repository containing all bootstrap scripts, Ansible playbooks, and GitOps manifests organized under `bootstrap/` and `gitops/` directories.
- **Operator_Workstation**: The machine used by the operator to run Ansible, kubectl, and related CLI commands.

## Requirements

### Requirement 1: Cloud-Init First-Boot Baseline

**User Story:** As a platform operator, I want each Node to be automatically configured on first boot via cloud-init, so that the OS baseline is consistent and reproducible without manual intervention.

#### Acceptance Criteria

1. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL set the hostname to the Node FQDN matching the pattern `node-{0,1,2}.cluster.arpa`.
2. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL disable swap permanently by removing swap entries from `/etc/fstab` and disabling swap at runtime.
3. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL install the baseline packages required for Kubernetes storage and networking support.
4. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL load and persist the kernel modules required for Kubernetes networking and storage (overlay, bridge netfilter, iSCSI).
5. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL apply and persist sysctl settings required for Kubernetes bridge networking and IP forwarding.
6. WHEN Cloud_Init executes on a Node, THE Cloud_Init SHALL enable time synchronization via systemd-timesyncd.
7. WHEN Cloud_Init completes all configuration steps, THE Cloud_Init SHALL trigger a single reboot to normalize the Node state.

### Requirement 2: Ansible OS Hardening and k3s Bootstrap

**User Story:** As a platform operator, I want Ansible to harden the OS and bootstrap an HA k3s cluster, so that the cluster is secure, reproducible, and achieves control-plane quorum across all three Nodes.

#### Acceptance Criteria

1. THE Ansible_Controller SHALL define an inventory with a server group containing all three Nodes with host variables mapping each Node name to its fixed IP and FQDN.
2. THE Ansible_Controller SHALL provide a base hardening role that performs idempotent package and state checks on each Node.
3. WHEN the Ansible_Controller initializes the first server Node, THE Ansible_Controller SHALL install k3s at a pinned version with embedded etcd, disabling bundled ingress and load balancer components, and keeping the control-plane schedulable.
4. WHEN the Ansible_Controller joins additional server Nodes, THE Ansible_Controller SHALL join each Node to the existing K3s_Cluster as an additional server using the cluster token.
5. WHEN all three Nodes have joined the K3s_Cluster, THE Ansible_Controller SHALL retrieve the kubeconfig and rewrite the API server endpoint to the appropriate address.
6. WHEN the Ansible_Controller executes validation, THE Ansible_Controller SHALL confirm that all three Nodes report `Ready` status, cluster DNS resolves services, and core system workloads are running.
7. THE Ansible_Controller SHALL store the cluster token and sensitive variables in an encrypted vault.
8. THE Ansible_Controller SHALL execute playbooks in the defined order: first server initialization, then additional server joins, then validation.

### Requirement 3: GitOps Bootstrap and Reconciliation

**User Story:** As a platform operator, I want a GitOps controller to manage all in-cluster resources from a Git repository, so that cluster state is declarative, auditable, and drift-free.

#### Acceptance Criteria

1. WHEN the operator bootstraps the GitOps_Controller, THE GitOps_Controller SHALL be deployed from the main branch of the GitOps_Repo.
2. THE GitOps_Controller SHALL define ordered reconciliation units with a dependency chain ensuring CRDs deploy before controllers, controllers before storage and observability (in parallel), storage before data services, and data services and observability before applications.
3. THE GitOps_Controller SHALL enforce reconciliation intervals and health checks on each unit so that drift from the Git source is detected and corrected automatically.
4. WHILE the GitOps_Controller is operational, THE Platform SHALL treat the Git repository as the single source of truth for all cluster resources, with manual changes permitted only during documented break-glass incidents.

### Requirement 4: Core Platform Services

**User Story:** As a platform operator, I want load balancing, ingress routing, and automated TLS certificate management as core platform services, so that workloads have stable external access with encrypted traffic.

#### Acceptance Criteria

1. WHEN the Load_Balancer is deployed, THE Load_Balancer SHALL advertise IPs from the reserved address pool `10.0.110.201-10.0.110.219` on the local network.
2. WHEN the Ingress_Controller is deployed, THE Ingress_Controller SHALL bind to a stable IP from the Load_Balancer pool for receiving external traffic.
3. WHEN the Certificate_Manager is deployed, THE Certificate_Manager SHALL provide an internal CA issuer capable of issuing certificates for `*.cluster.arpa`.
4. WHEN a workload requests a TLS certificate for a `*.cluster.arpa` hostname, THE Certificate_Manager SHALL issue a valid certificate signed by the internal CA.
5. THE Platform SHALL apply baseline network policies to restrict default inter-namespace traffic.

### Requirement 5: Storage and Data Plane

**User Story:** As a platform operator, I want distributed block storage and a framework for deploying managed data services, so that stateful workloads have durable, replicated data with backup and restore capabilities.

#### Acceptance Criteria

1. WHEN the Storage_System is deployed, THE Storage_System SHALL provide a default StorageClass and a critical StorageClass with a replica count ensuring data survives a single Node failure.
2. WHEN the Storage_System is operational, THE Storage_System SHALL execute recurring snapshot and backup jobs according to the configured schedule.
3. WHEN Data_Services are deployed, THE Platform SHALL provide operator-managed lifecycle including multi-instance replication, scheduled backups, and archive capabilities.
4. WHEN a data service primary instance fails, THE Platform SHALL promote a replica and restore service without data loss from committed transactions.
5. WHERE in-cluster object storage is enabled, THE Platform SHALL provide an S3-compatible object storage endpoint accessible via ingress as a secondary cache for in-cluster consumers.
6. THE Platform SHALL define storage quotas and retention policies for block volumes and data service backups.
7. WHERE a backup target is configured, THE Platform SHALL direct primary backups (storage snapshots, database archives) to the off-cluster NAS or S3-compatible endpoint. IF no backup target is configured, THEN THE Platform SHALL emit a warning and skip backup job creation.

### Requirement 6: Agentic and Custom Application Foundation

**User Story:** As a platform operator, I want pre-configured namespaces, shared primitives, and workload profiles, so that agentic tools and custom applications can be deployed consistently with enforced resource and security defaults.

#### Acceptance Criteria

1. THE Platform SHALL create dedicated namespaces for agentic tools and custom applications with appropriate labels and annotations.
2. THE Platform SHALL deploy shared primitives including a message broker or event bus, a secret synchronization mechanism, and standard ingress and certificate templates.
3. THE Platform SHALL define workload profiles for real-time agentic, batch agentic, and custom application workloads specifying resource requests/limits, probe configurations, and PodDisruptionBudget settings.
4. THE Platform SHALL enforce mandatory defaults for all workloads: resource requests and limits, liveness and readiness probes, PodDisruptionBudgets, and approved container registries.

### Requirement 7: Observability, Security, and Day-2 Operations

**User Story:** As a platform operator, I want centralized monitoring, logging, security scanning, and backup verification, so that the platform is observable, secure, and recoverable.

#### Acceptance Criteria

1. WHEN the Observability_Stack is deployed, THE Observability_Stack SHALL provide metrics collection with alerting, dashboards, and centralized log aggregation.
2. THE Platform SHALL perform container image CVE scanning, secret rotation, and RBAC review as part of ongoing security operations.
3. THE Platform SHALL execute etcd snapshots, storage backup verification, data service backup verification, and periodic restore drills as part of backup and disaster recovery operations.
4. THE Platform SHALL support periodic k3s patch upgrades performed one Node at a time with rollback capability.

### Requirement 8: High Availability and Fault Tolerance

**User Story:** As a platform operator, I want the platform to tolerate the loss of any single Node without losing control-plane quorum or critical application availability, so that the homelab remains operational during hardware failures or maintenance.

#### Acceptance Criteria

1. WHILE one Node is unavailable, THE K3s_Cluster SHALL maintain etcd quorum and continue serving the Kubernetes API.
2. WHILE one Node is unavailable, THE Platform SHALL continue running critical workloads on the remaining two Nodes without manual intervention.
3. WHEN a Node with replicated storage volumes becomes unavailable, THE Storage_System SHALL rebuild replicas on the remaining Nodes to restore the configured replica count.
4. WHEN a Node hosting a data service instance becomes unavailable, THE Platform SHALL failover to a replica on another Node and restore service.

### Requirement 9: Reproducibility and Bootstrap Time

**User Story:** As a platform operator, I want the entire platform to be rebuildable from bare Ubuntu hosts within 90 minutes, so that disaster recovery is predictable and time-bounded.

#### Acceptance Criteria

1. WHEN the operator executes the full bootstrap sequence (cloud-init, Ansible, GitOps reconciliation) on three bare Ubuntu 24.04 Nodes, THE Platform SHALL reach a ready state with all platform services operational within 90 minutes.
2. THE GitOps_Repo SHALL contain all artifacts needed to rebuild the Platform: cloud-init configs under `bootstrap/cloud-init/`, Ansible playbooks under `bootstrap/ansible/`, and GitOps manifests under `gitops/`.
3. THE Ansible_Controller SHALL produce idempotent playbook runs, allowing re-execution without side effects on an already-configured Node.

### Requirement 10: Repository Structure and GitOps Contract

**User Story:** As a platform operator, I want a well-defined repository structure, so that all infrastructure-as-code artifacts are organized, discoverable, and maintainable.

#### Acceptance Criteria

1. THE GitOps_Repo SHALL organize cloud-init files under `bootstrap/cloud-init/`, Ansible artifacts under `bootstrap/ansible/`, and GitOps manifests under `gitops/clusters/homelab-k3s/`, `gitops/infrastructure/`, `gitops/data-services/`, `gitops/apps/agentic/`, and `gitops/apps/custom/`.
2. THE Ansible_Controller SHALL accept configuration through a defined variables schema including: cluster name, k3s version, cluster token, API server VIP, API server port, components to disable, load balancer pool range, and backup target credentials.
3. WHEN the operator modifies any manifest in the GitOps_Repo and merges to the main branch, THE GitOps_Controller SHALL detect and reconcile the change to the K3s_Cluster within the configured reconciliation interval.

### Requirement 11: Node Cleanup and Reset

**User Story:** As a platform operator, I want a scripted node cleanup and reset procedure, so that any Node can be returned to a pre-bootstrap state for re-provisioning or decommissioning.

#### Acceptance Criteria

1. WHEN the operator executes the cleanup script in safe mode on a Node, THE cleanup script SHALL stop and uninstall k3s, removing k3s binaries, configuration, and CNI config, while preserving storage data and container images.
2. WHEN the operator executes the cleanup script in full mode on a Node with explicit confirmation, THE cleanup script SHALL remove all k3s artifacts, container runtime data, storage volumes, device mappings, kernel module configs, and sysctl overrides.
3. IF the operator executes the cleanup script in full mode without explicit confirmation, THEN THE cleanup script SHALL abort with an error message and make no changes.
4. WHEN the operator executes the cleanup script on a Node, THE cleanup script SHALL revert kernel module and sysctl configurations applied during bootstrap to their default state (full mode only).
5. WHEN the full cleanup script completes on a Node, THE Node SHALL be in a state where the full bootstrap sequence (cloud-init, Ansible) can be re-executed cleanly without conflicts from prior installations.
6. THE cleanup script SHALL be idempotent, producing no errors when executed on a Node that is already in a clean state.
