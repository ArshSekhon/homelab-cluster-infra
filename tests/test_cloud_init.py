"""Property 1: Cloud-init configuration completeness.

Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
Validates: Requirements 1.1, 1.2, 1.4, 1.5, 1.6

For any valid node index (0, 1, 2), the generated cloud-init YAML SHALL contain:
- a hostname matching `node-{N}.cluster.arpa`
- a non-root admin user with SSH key
- the required baseline packages (curl, jq, nfs-common, open-iscsi)
- the required kernel modules (overlay, br_netfilter, iscsi_tcp) in both
  write_files and runcmd
- the required sysctl settings (bridge-nf-call-iptables, bridge-nf-call-ip6tables,
  ip_forward) in write_files
- a power_state reboot directive
"""

import pathlib
from typing import Dict, List, Optional

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants derived from the design document
# ---------------------------------------------------------------------------

VALID_NODE_INDICES = [0, 1, 2]

REQUIRED_PACKAGES = ["curl", "jq", "nfs-common", "open-iscsi"]

REQUIRED_KERNEL_MODULES = ["overlay", "br_netfilter", "iscsi_tcp"]

REQUIRED_SYSCTL_KEYS = [
    "net.bridge.bridge-nf-call-iptables",
    "net.bridge.bridge-nf-call-ip6tables",
    "net.ipv4.ip_forward",
]

ADMIN_USER = "kadmin"

# Suppress fixture-scoped warning — cloud-init files are read-only
_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_cloud_init(node_idx: int) -> dict:
    """Load and parse the cloud-init YAML for a given node index."""
    path = PROJECT_ROOT / "bootstrap" / "cloud-init" / f"node-{node_idx}.yaml"
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _get_write_file_content(config: dict, target_path: str) -> Optional[str]:
    """Extract the content of a write_files entry by its path."""
    for entry in config.get("write_files", []):
        if entry.get("path") == target_path:
            return entry.get("content", "")
    return None


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestCloudInitCompleteness:
    """**Validates: Requirements 1.1, 1.2, 1.4, 1.5, 1.6**"""

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_hostname_matches_fqdn_pattern(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL set the FQDN to
        node-{N}.cluster.arpa.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.1**
        """
        config = _load_cloud_init(node_idx)
        expected_fqdn = f"node-{node_idx}.cluster.arpa"

        assert config.get("fqdn") == expected_fqdn, (
            f"Node {node_idx}: expected fqdn '{expected_fqdn}', "
            f"got '{config.get('fqdn')}'"
        )
        assert config.get("hostname") == f"node-{node_idx}", (
            f"Node {node_idx}: expected hostname 'node-{node_idx}', "
            f"got '{config.get('hostname')}'"
        )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_admin_user_with_ssh_key(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL create a non-root
        admin user with an SSH authorized key.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.1**
        """
        config = _load_cloud_init(node_idx)
        users = config.get("users", [])

        admin_users = [u for u in users if u.get("name") == ADMIN_USER]
        assert len(admin_users) == 1, (
            f"Node {node_idx}: expected exactly one '{ADMIN_USER}' user, "
            f"found {len(admin_users)}"
        )

        admin = admin_users[0]
        assert admin.get("name") != "root", (
            f"Node {node_idx}: admin user must not be root"
        )
        ssh_keys = admin.get("ssh_authorized_keys", [])
        assert len(ssh_keys) >= 1, (
            f"Node {node_idx}: admin user must have at least one SSH key"
        )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_required_packages_installed(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL install the required
        baseline packages.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.2**
        """
        config = _load_cloud_init(node_idx)
        packages = config.get("packages", [])

        for pkg in REQUIRED_PACKAGES:
            assert pkg in packages, (
                f"Node {node_idx}: required package '{pkg}' not in packages list"
            )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_kernel_modules_in_write_files(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL persist the required
        kernel modules via write_files.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.4**
        """
        config = _load_cloud_init(node_idx)
        modules_content = _get_write_file_content(
            config, "/etc/modules-load.d/k8s.conf"
        )

        assert modules_content is not None, (
            f"Node {node_idx}: missing write_files entry for "
            "/etc/modules-load.d/k8s.conf"
        )

        for module in REQUIRED_KERNEL_MODULES:
            assert module in modules_content, (
                f"Node {node_idx}: kernel module '{module}' not found in "
                "/etc/modules-load.d/k8s.conf write_files content"
            )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_kernel_modules_in_runcmd(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL load the required
        kernel modules at runtime via runcmd.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.4**
        """
        config = _load_cloud_init(node_idx)
        runcmd = config.get("runcmd", [])

        for module in REQUIRED_KERNEL_MODULES:
            expected_cmd = f"modprobe {module}"
            assert expected_cmd in runcmd, (
                f"Node {node_idx}: expected '{expected_cmd}' in runcmd"
            )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_sysctl_settings_in_write_files(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL persist the required
        sysctl settings via write_files.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.5**
        """
        config = _load_cloud_init(node_idx)
        sysctl_content = _get_write_file_content(
            config, "/etc/sysctl.d/k8s.conf"
        )

        assert sysctl_content is not None, (
            f"Node {node_idx}: missing write_files entry for "
            "/etc/sysctl.d/k8s.conf"
        )

        for key in REQUIRED_SYSCTL_KEYS:
            assert key in sysctl_content, (
                f"Node {node_idx}: sysctl key '{key}' not found in "
                "/etc/sysctl.d/k8s.conf write_files content"
            )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_power_state_reboot_directive(self, node_idx: int) -> None:
        """For any valid node index, the cloud-init SHALL include a power_state
        reboot directive.

        Feature: k3s-homelab-platform, Property 1: Cloud-init configuration completeness
        **Validates: Requirements 1.6**
        """
        config = _load_cloud_init(node_idx)
        power_state = config.get("power_state")

        assert power_state is not None, (
            f"Node {node_idx}: missing power_state directive"
        )
        assert power_state.get("mode") == "reboot", (
            f"Node {node_idx}: power_state mode must be 'reboot', "
            f"got '{power_state.get('mode')}'"
        )
