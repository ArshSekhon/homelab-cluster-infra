"""Property 9: Cleanup reverts bootstrap kernel/sysctl configuration (round-trip).

Feature: k3s-homelab-platform, Property 9: Cleanup reverts bootstrap kernel/sysctl configuration
Validates: Requirements 11.4

For any node where cloud-init has applied kernel module configs (in
/etc/modules-load.d/) and sysctl configs (in /etc/sysctl.d/), executing the
cleanup role SHALL remove those specific config files, such that the set of
platform-created config files after cleanup is empty.
"""

import pathlib

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_NODE_INDICES = [0, 1, 2]

# Paths that cloud-init writes kernel/sysctl configs to
BOOTSTRAP_CONFIG_DIRS = ("/etc/modules-load.d/", "/etc/sysctl.d/")

_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_cloud_init(node_idx: int) -> dict:
    """Load and parse the cloud-init YAML for a given node index."""
    path = PROJECT_ROOT / "bootstrap" / "cloud-init" / f"node-{node_idx}.yaml"
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_cleanup_defaults() -> dict:
    """Load the node_cleanup role defaults."""
    path = (
        PROJECT_ROOT
        / "bootstrap"
        / "ansible"
        / "roles"
        / "node_cleanup"
        / "defaults"
        / "main.yaml"
    )
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _bootstrap_config_files(node_idx: int) -> set[str]:
    """Return the set of config file paths created by cloud-init write_files
    that live under /etc/modules-load.d/ or /etc/sysctl.d/."""
    config = _load_cloud_init(node_idx)
    paths: set[str] = set()
    for entry in config.get("write_files", []):
        file_path = entry.get("path", "")
        if any(file_path.startswith(d) for d in BOOTSTRAP_CONFIG_DIRS):
            paths.add(file_path)
    return paths


def _cleanup_config_files() -> set[str]:
    """Return the set of config file paths that the cleanup role removes
    (cleanup_sysctl_files + cleanup_module_load_files)."""
    defaults = _load_cleanup_defaults()
    sysctl = set(defaults.get("cleanup_sysctl_files", []))
    modules = set(defaults.get("cleanup_module_load_files", []))
    return sysctl | modules


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestCleanupRoundTrip:
    """**Validates: Requirements 11.4**"""

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_cleanup_removes_all_bootstrap_config_files(
        self, node_idx: int
    ) -> None:
        """For any valid node index, every kernel/sysctl config file created
        by cloud-init SHALL be present in the cleanup role's removal lists.

        The set of bootstrap-created config files minus the cleanup removal
        set must be empty — nothing is left behind.

        Feature: k3s-homelab-platform, Property 9: Cleanup reverts bootstrap kernel/sysctl configuration
        **Validates: Requirements 11.4**
        """
        bootstrap_files = _bootstrap_config_files(node_idx)
        cleanup_files = _cleanup_config_files()

        leftover = bootstrap_files - cleanup_files
        assert leftover == set(), (
            f"Node {node_idx}: cleanup does not remove bootstrap config files: "
            f"{sorted(leftover)}"
        )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_cleanup_does_not_target_extra_files(
        self, node_idx: int
    ) -> None:
        """For any valid node index, the cleanup role SHALL not target config
        files that were never created by cloud-init bootstrap.

        The cleanup removal set minus the bootstrap-created set must be empty
        — cleanup only removes what bootstrap created.

        Feature: k3s-homelab-platform, Property 9: Cleanup reverts bootstrap kernel/sysctl configuration
        **Validates: Requirements 11.4**
        """
        bootstrap_files = _bootstrap_config_files(node_idx)
        cleanup_files = _cleanup_config_files()

        extra = cleanup_files - bootstrap_files
        assert extra == set(), (
            f"Node {node_idx}: cleanup targets files not created by bootstrap: "
            f"{sorted(extra)}"
        )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_bootstrap_and_cleanup_sets_are_equal(
        self, node_idx: int
    ) -> None:
        """For any valid node index, the set of config files created by
        cloud-init bootstrap SHALL exactly equal the set of config files
        removed by the cleanup role.

        This is the round-trip property: create == remove.

        Feature: k3s-homelab-platform, Property 9: Cleanup reverts bootstrap kernel/sysctl configuration
        **Validates: Requirements 11.4**
        """
        bootstrap_files = _bootstrap_config_files(node_idx)
        cleanup_files = _cleanup_config_files()

        assert bootstrap_files == cleanup_files, (
            f"Node {node_idx}: bootstrap/cleanup config file mismatch.\n"
            f"  Bootstrap creates: {sorted(bootstrap_files)}\n"
            f"  Cleanup removes:   {sorted(cleanup_files)}"
        )

    @given(node_idx=st.sampled_from(VALID_NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_bootstrap_creates_nonempty_config_set(
        self, node_idx: int
    ) -> None:
        """For any valid node index, cloud-init SHALL create at least one
        kernel/sysctl config file (sanity check that the round-trip property
        is not vacuously true on empty sets).

        Feature: k3s-homelab-platform, Property 9: Cleanup reverts bootstrap kernel/sysctl configuration
        **Validates: Requirements 11.4**
        """
        bootstrap_files = _bootstrap_config_files(node_idx)

        assert len(bootstrap_files) > 0, (
            f"Node {node_idx}: cloud-init creates no kernel/sysctl config "
            f"files — round-trip property would be vacuously true"
        )
