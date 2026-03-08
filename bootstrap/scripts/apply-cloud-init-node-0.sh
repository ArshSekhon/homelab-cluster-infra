#!/usr/bin/env bash
set -euo pipefail

NODE="node-0.cluster.arpa"
CONFIG="bootstrap/cloud-init/node-0.yaml"

echo "Copying cloud-init config to $NODE..."
scp "$CONFIG" "${NODE}:/tmp/node-0.yaml"

echo "Injecting config and triggering re-run..."
ssh -o RequestTTY=force "$NODE" "sudo mkdir -p /var/lib/cloud/seed/nocloud && \
  sudo cp /tmp/node-0.yaml /var/lib/cloud/seed/nocloud/user-data && \
  sudo touch /var/lib/cloud/seed/nocloud/meta-data && \
  sudo cloud-init clean --reboot"

echo "Node is rebooting. Wait ~60s then reconnect as kadmin@${NODE}"
