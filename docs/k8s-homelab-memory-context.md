# Kubernetes Homelab Memory Context

Last updated: 2026-03-04
Owner: arshsekhon
Purpose: Provide stable context for an LLM to design and operate this homelab Kubernetes cluster.

## Objective

Build a 3-node Kubernetes homelab on Ubuntu 24.04.4 LTS systems connected through a TP-Link managed switch using VLAN 110.

## Environment Facts

### OS

- All three nodes run Ubuntu 24.04.4 LTS (GNU/Linux 6.8.0-101-generic x86_64).

### Nodes

1. `node-0`
   - CPU: Intel Core i5-10600T @ 2.40GHz
   - RAM: 16 GiB
   - Disk: Patriot M.2 P320 512GB NVMe (`/dev/nvme0n1`)
   - NIC: `eno2` (Intel I219-LM)
2. `node-1`
   - CPU: Intel Core i5-10600T @ 2.40GHz
   - RAM: 16 GiB
   - Disk: KIOXIA KXG60ZNV256G 256GB NVMe (`/dev/nvme0n1`)
   - NIC: `eno2` (Intel I219-LM)
3. `node-2`
   - CPU: Intel Core i5-10600T @ 2.40GHz
   - RAM: 16 GiB
   - Disk: Samsung PM991 128GB NVMe (`/dev/nvme0n1`)
   - NIC: `eno2` (Intel I219-LM)

### Aggregate Capacity

- CPU: 18 physical cores total (36 threads total)
- RAM: 48 GiB total
- NVMe raw storage: ~896 GB total

## Network / Switch Context

### Switch VLAN Setup (TP-Link, 802.1Q enabled)

- VLAN `1` (Default)
  - Member ports: `1,2,6,7,8`
  - Untagged ports: `1,2,6,7,8`
- VLAN `110` (Name: `Cluster`)
  - Member ports: `1,3,4,5`
  - Tagged ports: `1`
  - Untagged ports: `3,4,5`

### PVIDs

- Port 1: PVID 1
- Port 2: PVID 1
- Port 3: PVID 110
- Port 4: PVID 110
- Port 5: PVID 110
- Port 6: PVID 1
- Port 7: PVID 1
- Port 8: PVID 1

### Link Status Snapshot

- Up at 1 Gbps full duplex: ports `1,3,4,5`
- Down: ports `2,6,7,8`

### DHCP Static Mappings (OPNsense)

- `node-0`
  - MAC: `a4:bb:6d:73:fa:ed`
  - Reserved IP: `10.0.110.10`
- `node-1`
  - MAC: `a4:bb:6d:73:ff:5b`
  - Reserved IP: `10.0.110.11`
- `node-2`
  - MAC: `a4:bb:6d:73:ff:97`
  - Reserved IP: `10.0.110.12`

### DNS Records (OPNsense)

- Local zone/domain: `cluster.arpa`
- `node-0.cluster.arpa` -> `10.0.110.10`
- `node-1.cluster.arpa` -> `10.0.110.11`
- `node-2.cluster.arpa` -> `10.0.110.12`
- Naming note:
  - `node-0` corresponds to `node-0`
  - `node-1` corresponds to `node-1`
  - `node-2` corresponds to `node-2`

### Inference

- Ports `3,4,5` are likely access ports for cluster nodes on untagged VLAN 110.
- Port `1` is likely an uplink/trunk carrying VLAN 110 tagged traffic.
- Node-to-port mapping is not explicitly confirmed yet.
- Cluster node addressing is in the `10.0.110.x` range on VLAN 110.

## Current Unknowns (Need Confirmation)

- VLAN 110 subnet mask/CIDR (likely `10.0.110.0/24`, but not explicitly confirmed)
- Default gateway IP for VLAN 110
- DNS resolver IP(s) and NTP server(s) used by nodes
- Whether cluster should be:
  - single control-plane + workers, or
  - 3 control-plane HA design
- Kubernetes distro preference (`k3s`, `kubeadm`, or `microk8s`)
- Storage layer preference (`local-path`, `Longhorn`, `Rook/Ceph`, `NFS`)

## Recommended Baseline Direction

- Use `k3s` for first stable cluster bring-up.
- Run all 3 nodes as server/control-plane + schedulable workers for HA and simplicity.
- Keep CNI default initially (Flannel), then migrate to Cilium later if needed.
- Start with local-path storage, then add distributed storage only if workloads demand it.

## Desired LLM Output Format

When using this context, ask the LLM to return:

1. A concrete preflight checklist (BIOS, OS, kernel modules, swap, time sync, firewall).
2. Exact commands for all nodes and clear node-specific sections.
3. A phased install plan with validation after each phase.
4. Networking assumptions stated explicitly (CIDR, service CIDR, pod CIDR, ingress/LB strategy).
5. Rollback and troubleshooting steps for each critical phase.

## Copy-Paste Prompt Template

```text
Use the following homelab memory context as source-of-truth. If information is missing, list assumptions explicitly before giving commands.

[BEGIN MEMORY CONTEXT]
<paste this entire file>
[END MEMORY CONTEXT]

Task:
- Design and provide a complete, production-sane but homelab-practical Kubernetes bootstrap plan.
- Prefer k3s unless constraints clearly require kubeadm.
- Output:
  1) Prerequisites checklist
  2) Exact commands per node
  3) Validation commands and expected output
  4) Minimal baseline add-ons (ingress, cert-manager, metrics, dashboard optional)
  5) Day-2 operations checklist (backup, upgrades, security hardening)
```
