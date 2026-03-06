# Backup Verification and Restore Drill Runbook

## Overview

The homelab-k3s platform implements a three-layer backup strategy:

| Layer | Tool | Schedule | Retention | Target |
|-------|------|----------|-----------|--------|
| etcd snapshots | k3s built-in | Every 6 hours (`0 */6 * * *`) | 5 snapshots | Local: `/var/lib/rancher/k3s/server/db/snapshots` |
| Block storage | Longhorn | Daily snapshots (retain 7), weekly backups | 7 snapshots / 4 backups | Snapshots: local; Backups: off-cluster NAS/S3 |
| Database | CloudNativePG | Daily base backup + continuous WAL archiving | 14 days | Off-cluster NAS/S3 (`s3://cnpg-backups/`) |

All off-cluster backups target the endpoint configured via `backup_s3_endpoint` in Ansible group vars. If no backup target is configured, backup jobs are skipped or fail gracefully with alerts.

---

## 1. etcd Snapshot Verification

### List snapshots

```bash
# On any server node (node-0, node-1, or node-2)
sudo k3s etcd-snapshot list --etcd-snapshot-dir /var/lib/rancher/k3s/server/db/snapshots
```

### Verify snapshot integrity

```bash
# Check that the latest snapshot file exists and is non-empty
ls -lh /var/lib/rancher/k3s/server/db/snapshots/

# Verify the snapshot is a valid etcd database
sudo ETCDCTL_API=3 etcdctl snapshot status \
  /var/lib/rancher/k3s/server/db/snapshots/<snapshot-name> \
  --write-out=table
```

Expected output includes revision, total keys, and hash — a non-zero key count confirms a valid snapshot.

### Create an on-demand snapshot

```bash
sudo k3s etcd-snapshot save --name manual-drill-$(date +%Y%m%d)
```

### Restore from snapshot

> **Warning:** This is a destructive operation. It replaces the entire cluster state. Only perform during a planned drill or actual disaster recovery.

```bash
# 1. Stop k3s on ALL server nodes
# On node-0, node-1, node-2:
sudo systemctl stop k3s

# 2. Restore on the init node (node-0)
sudo k3s server \
  --cluster-reset \
  --cluster-reset-restore-path=/var/lib/rancher/k3s/server/db/snapshots/<snapshot-name>

# 3. Once node-0 is back, remove the cluster-reset lock on node-0
#    (k3s creates a reset flag file that must be cleared)

# 4. On join nodes (node-1, node-2), remove old etcd data and rejoin
sudo rm -rf /var/lib/rancher/k3s/server/db/etcd
sudo systemctl start k3s

# 5. Verify all nodes rejoin
kubectl get nodes
```

---

## 2. Longhorn Backup Verification

### Check recurring job status

```bash
# List recurring jobs
kubectl -n longhorn-system get recurringjobs

# Check the daily snapshot job
kubectl -n longhorn-system get recurringjob snapshot-daily -o yaml

# Check the weekly backup job
kubectl -n longhorn-system get recurringjob backup-weekly -o yaml
```

### Check volume backup status

```bash
# List all volumes and their last backup status
kubectl -n longhorn-system get volumes.longhorn.io

# Get detailed backup info for a specific volume
kubectl -n longhorn-system get backups.longhorn.io -l longhornvolume=<volume-name>

# Check backup target configuration
kubectl -n longhorn-system get settings.longhorn.io backup-target -o jsonpath='{.value}'
```

### Verify a backup via the Longhorn UI

1. Open `https://longhorn.cluster.arpa` in a browser
2. Navigate to **Backup** tab
3. Confirm backups exist for each volume with recent timestamps
4. Check that backup sizes are reasonable (not zero)

### Restore a volume from backup

```bash
# Option A: Restore via Longhorn UI
# 1. Go to Backup tab → select the backup → click "Restore"
# 2. Choose a name for the restored volume
# 3. Attach the restored volume to verify data

# Option B: Restore via kubectl
# 1. Create a restore volume from a backup URL
cat <<EOF | kubectl apply -f -
apiVersion: longhorn.io/v1beta2
kind: Volume
metadata:
  name: restore-drill-$(date +%Y%m%d)
  namespace: longhorn-system
spec:
  fromBackup: "s3://longhorn-backups@us-east-1/?backup=<backup-name>&volume=<volume-name>"
  numberOfReplicas: 2
  accessMode: rwo
EOF

# 2. Wait for the volume to become available
kubectl -n longhorn-system get volumes.longhorn.io restore-drill-$(date +%Y%m%d) -w

# 3. Clean up after verification
kubectl -n longhorn-system delete volume restore-drill-$(date +%Y%m%d)
```

### Verify snapshot health

```bash
# List snapshots for a specific volume
kubectl -n longhorn-system get snapshots.longhorn.io -l longhornvolume=<volume-name>
```

---

## 3. CloudNativePG Backup Verification

### Check cluster and backup status

```bash
# Check CNPG cluster health
kubectl -n data-system get clusters.postgresql.cnpg.io postgres-cluster

# Detailed cluster status (includes backup info)
kubectl -n data-system describe cluster postgres-cluster

# Check the scheduled backup resource
kubectl -n data-system get scheduledbackups.postgresql.cnpg.io
```

### Verify WAL archiving

```bash
# Check WAL archiving status on the primary
kubectl -n data-system exec -it postgres-cluster-1 -c postgres -- \
  psql -U postgres -c "SELECT * FROM pg_stat_archiver;"

# Verify the last successful WAL archive timestamp
kubectl -n data-system exec -it postgres-cluster-1 -c postgres -- \
  psql -U postgres -c "SELECT last_archived_wal, last_archived_time FROM pg_stat_archiver;"

# Check for archiving failures
kubectl -n data-system exec -it postgres-cluster-1 -c postgres -- \
  psql -U postgres -c "SELECT failed_count, last_failed_wal, last_failed_time FROM pg_stat_archiver;"
```

A `failed_count` of 0 and a recent `last_archived_time` confirm healthy WAL archiving.

### List available backups

```bash
# List all backups
kubectl -n data-system get backups.postgresql.cnpg.io

# Get details of the latest backup
kubectl -n data-system get backups.postgresql.cnpg.io -o wide
```

### Trigger an on-demand backup

```bash
cat <<EOF | kubectl apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: postgres-cluster-drill-$(date +%Y%m%d)
  namespace: data-system
spec:
  method: barmanObjectStore
  cluster:
    name: postgres-cluster
EOF

# Monitor backup progress
kubectl -n data-system get backup postgres-cluster-drill-$(date +%Y%m%d) -w
```

### Restore from backup (into a new cluster)

> **Note:** CNPG restores create a new cluster from a backup. This is non-destructive to the running cluster.

```bash
cat <<EOF | kubectl apply -f -
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-restore-drill
  namespace: data-system
spec:
  description: "Restore drill — temporary cluster"
  imageName: ghcr.io/cloudnative-pg/postgresql:16
  instances: 1

  storage:
    storageClass: longhorn
    size: 10Gi

  bootstrap:
    recovery:
      source: postgres-cluster

  externalClusters:
    - name: postgres-cluster
      barmanObjectStore:
        destinationPath: "s3://cnpg-backups/"
        endpointURL: "${BACKUP_S3_ENDPOINT}"
        s3Credentials:
          accessKeyId:
            name: cnpg-backup-creds
            key: ACCESS_KEY_ID
          secretAccessKey:
            name: cnpg-backup-creds
            key: ACCESS_SECRET_KEY
        wal:
          maxParallel: 2
EOF

# Monitor restore progress
kubectl -n data-system get cluster postgres-restore-drill -w

# Verify data integrity once the restore cluster is ready
kubectl -n data-system exec -it postgres-restore-drill-1 -c postgres -- \
  psql -U postgres -c "SELECT count(*) FROM pg_database;"
```

### Clean up after restore drill

```bash
kubectl -n data-system delete cluster postgres-restore-drill
```

---

## 4. Monthly Restore Drill Procedure

Perform this drill on the first weekend of each month. Estimated time: 60–90 minutes.

### Pre-drill checklist

- [ ] Confirm all 3 nodes are `Ready`: `kubectl get nodes`
- [ ] Confirm no active alerts: check Alertmanager at `https://prometheus.cluster.arpa`
- [ ] Notify any users of potential brief disruptions
- [ ] Open a terminal session to each node (or have SSH access ready)

### Drill Step 1: etcd snapshot verification (15 min)

- [ ] List etcd snapshots on node-0:
  ```bash
  sudo k3s etcd-snapshot list --etcd-snapshot-dir /var/lib/rancher/k3s/server/db/snapshots
  ```
- [ ] Verify the latest snapshot has a non-zero size
- [ ] Create an on-demand snapshot:
  ```bash
  sudo k3s etcd-snapshot save --name drill-$(date +%Y%m%d)
  ```
- [ ] Confirm the new snapshot appears in the list
- [ ] Record snapshot name and timestamp in drill log

### Drill Step 2: Longhorn backup verification (20 min)

- [ ] Check recurring job status:
  ```bash
  kubectl -n longhorn-system get recurringjobs
  ```
- [ ] Verify at least one recent backup exists per critical volume:
  ```bash
  kubectl -n longhorn-system get backups.longhorn.io
  ```
- [ ] Open Longhorn UI (`https://longhorn.cluster.arpa`) and confirm backup timestamps
- [ ] Restore a non-critical volume from backup to a temporary volume
- [ ] Verify the restored volume is accessible and contains expected data
- [ ] Delete the temporary restored volume
- [ ] Record volume name, backup name, and restore result in drill log

### Drill Step 3: CloudNativePG backup verification (20 min)

- [ ] Check CNPG cluster health:
  ```bash
  kubectl -n data-system get clusters.postgresql.cnpg.io postgres-cluster
  ```
- [ ] Verify WAL archiving is current:
  ```bash
  kubectl -n data-system exec -it postgres-cluster-1 -c postgres -- \
    psql -U postgres -c "SELECT last_archived_wal, last_archived_time, failed_count FROM pg_stat_archiver;"
  ```
- [ ] List available backups:
  ```bash
  kubectl -n data-system get backups.postgresql.cnpg.io
  ```
- [ ] Create a restore drill cluster (single instance):
  ```bash
  # Apply the restore cluster manifest from Section 3 above
  ```
- [ ] Wait for the restore cluster to become ready
- [ ] Run a basic data integrity query on the restored cluster
- [ ] Delete the restore drill cluster:
  ```bash
  kubectl -n data-system delete cluster postgres-restore-drill
  ```
- [ ] Record backup name, restore time, and data verification result in drill log

### Drill Step 4: Post-drill validation (10 min)

- [ ] Confirm the production CNPG cluster is still healthy:
  ```bash
  kubectl -n data-system get clusters.postgresql.cnpg.io postgres-cluster
  ```
- [ ] Confirm all Longhorn volumes are healthy:
  ```bash
  kubectl -n longhorn-system get volumes.longhorn.io
  ```
- [ ] Confirm all nodes are still `Ready`:
  ```bash
  kubectl get nodes
  ```
- [ ] Check for any new alerts in Alertmanager
- [ ] Clean up any drill artifacts (temporary volumes, restore clusters)

### Drill log template

```
Date: YYYY-MM-DD
Operator: <name>
Duration: <minutes>

etcd:
  Snapshot count: <N>
  Latest snapshot: <name> (<timestamp>)
  On-demand snapshot: PASS / FAIL

Longhorn:
  Recurring jobs active: YES / NO
  Backup count: <N>
  Restore test volume: <name>
  Restore result: PASS / FAIL

CloudNativePG:
  WAL archiving: CURRENT / BEHIND / FAILED
  Last archived WAL: <name> (<timestamp>)
  Backup count: <N>
  Restore cluster: PASS / FAIL
  Data integrity check: PASS / FAIL

Overall: PASS / FAIL
Notes: <any issues or observations>
```

---

## 5. Troubleshooting

### etcd snapshots not being created

```bash
# Check k3s server flags include snapshot configuration
ps aux | grep k3s | grep etcd-snapshot

# Verify the snapshot directory exists and is writable
ls -la /var/lib/rancher/k3s/server/db/snapshots/

# Check k3s logs for snapshot errors
sudo journalctl -u k3s --since "6 hours ago" | grep -i snapshot
```

### Longhorn backups failing

```bash
# Check if backup target is configured
kubectl -n longhorn-system get settings.longhorn.io backup-target

# Check Longhorn manager logs
kubectl -n longhorn-system logs -l app=longhorn-manager --tail=50 | grep -i backup

# Verify S3 credentials are valid
kubectl -n longhorn-system get secret longhorn-backup-secret -o yaml

# Check recurring job events
kubectl -n longhorn-system describe recurringjob backup-weekly
```

Common causes:
- `backup_s3_endpoint` not configured — backups are skipped by design
- S3 credentials expired or incorrect
- Network connectivity to NAS/S3 endpoint lost
- Disk space on backup target exhausted

### CNPG WAL archiving failures

```bash
# Check archiver status
kubectl -n data-system exec -it postgres-cluster-1 -c postgres -- \
  psql -U postgres -c "SELECT * FROM pg_stat_archiver;"

# Check CNPG operator logs
kubectl -n cnpg-system logs -l app.kubernetes.io/name=cloudnative-pg --tail=50

# Check backup credentials secret
kubectl -n data-system get secret cnpg-backup-creds -o yaml

# Check CNPG cluster events
kubectl -n data-system describe cluster postgres-cluster | tail -20
```

Common causes:
- `cnpg-backup-creds` secret missing or incorrect
- S3 endpoint unreachable from the cluster
- WAL volume running out of space (check `walStorage` PVC usage)
- CNPG operator not running

### Restore drill cluster stuck in "Not Ready"

```bash
# Check restore cluster events
kubectl -n data-system describe cluster postgres-restore-drill

# Check pod logs
kubectl -n data-system logs postgres-restore-drill-1 -c postgres --tail=50

# Check if the backup being restored from actually exists
kubectl -n data-system get backups.postgresql.cnpg.io
```

Common causes:
- Backup data corrupted or incomplete
- S3 credentials different from those used during backup
- Insufficient cluster resources to schedule the restore pod
- WAL files missing for point-in-time recovery
