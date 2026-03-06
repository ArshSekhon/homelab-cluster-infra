"""Property 8: Ansible variables schema completeness.

Feature: k3s-homelab-platform, Property 8: Ansible variables schema completeness
Validates: Requirements 10.2

For any Ansible group_vars file for the k3s_servers group, the file SHALL
contain all required keys: cluster_name, k3s_version, k3s_token,
api_server_vip, api_server_port, disable_components, admin_user,
kube_vip_version, metallb_pool_start, metallb_pool_end,
backup_s3_endpoint, backup_bucket, backup_secret_ref, and minio_enabled.
"""

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants derived from the design document
# ---------------------------------------------------------------------------

REQUIRED_KEYS = [
    "cluster_name",
    "k3s_version",
    "k3s_token",
    "api_server_vip",
    "api_server_port",
    "disable_components",
    "admin_user",
    "kube_vip_version",
    "metallb_pool_start",
    "metallb_pool_end",
    "backup_s3_endpoint",
    "backup_bucket",
    "backup_secret_ref",
    "minio_enabled",
    "etcd_snapshot_schedule",
    "etcd_snapshot_retention",
    "etcd_snapshot_dir",
]

_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_group_vars() -> dict:
    """Load and parse the k3s_servers group variables YAML."""
    path = (
        PROJECT_ROOT
        / "bootstrap"
        / "ansible"
        / "inventory"
        / "group_vars"
        / "k3s_servers.yaml"
    )
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestAnsibleVariablesSchemaCompleteness:
    """**Validates: Requirements 10.2**"""

    @given(key=st.sampled_from(REQUIRED_KEYS))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_required_key_present(self, key: str) -> None:
        """For any required key, the group_vars file SHALL contain that key.

        Feature: k3s-homelab-platform, Property 8: Ansible variables schema completeness
        **Validates: Requirements 10.2**
        """
        group_vars = _load_group_vars()

        assert key in group_vars, (
            f"Required key '{key}' not found in k3s_servers group_vars. "
            f"Present keys: {sorted(group_vars.keys())}"
        )

    @given(key=st.sampled_from(REQUIRED_KEYS))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_required_key_is_defined(self, key: str) -> None:
        """For any required key, the value SHALL NOT be None (must be
        explicitly defined, even if empty string or false).

        Feature: k3s-homelab-platform, Property 8: Ansible variables schema completeness
        **Validates: Requirements 10.2**
        """
        group_vars = _load_group_vars()

        # Key must exist and have a non-None value.
        # Empty strings and False are valid (e.g. backup_s3_endpoint: "",
        # minio_enabled: false), but a bare key with no value (YAML null)
        # indicates a missing definition.
        value = group_vars.get(key)
        assert value is not None, (
            f"Required key '{key}' is present but has a null/undefined value"
        )

    def test_all_required_keys_present_at_once(self) -> None:
        """The group_vars file SHALL contain every required key.

        Feature: k3s-homelab-platform, Property 8: Ansible variables schema completeness
        **Validates: Requirements 10.2**
        """
        group_vars = _load_group_vars()
        present_keys = set(group_vars.keys())
        required = set(REQUIRED_KEYS)
        missing = required - present_keys

        assert not missing, (
            f"Missing required keys in k3s_servers group_vars: {sorted(missing)}"
        )
