"""Property 3: k3s install flags are correct for each role.

Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
Validates: Requirements 2.3, 2.4

For any node with role init, the generated k3s install command SHALL include
the pinned version, --cluster-init flag, and disable flags for traefik and
servicelb. For any node with role join, the generated k3s install command
SHALL include the pinned version, the server URL pointing to the init node,
the cluster token, and the same disable flags.
"""

from typing import Dict, List, Optional

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants from the design document
# ---------------------------------------------------------------------------

ROLES = ["init", "join"]

ROLE_TASK_PATHS = {
    "init": PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_init" / "tasks" / "main.yaml",
    "join": PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_join" / "tasks" / "main.yaml",
}

ROLE_DEFAULTS_PATHS = {
    "init": PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_init" / "defaults" / "main.yaml",
    "join": PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_join" / "defaults" / "main.yaml",
}

GROUP_VARS_PATH = (
    PROJECT_ROOT / "bootstrap" / "ansible" / "inventory" / "group_vars" / "k3s_servers.yaml"
)

REQUIRED_DISABLE_COMPONENTS = {"traefik", "servicelb"}

_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml(path) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_tasks(role: str) -> List[Dict]:
    """Load the task list for a given role."""
    return _load_yaml(ROLE_TASK_PATHS[role])


def _load_defaults(role: str) -> Dict:
    """Load the defaults for a given role."""
    return _load_yaml(ROLE_DEFAULTS_PATHS[role])


def _load_group_vars() -> Dict:
    """Load the group variables."""
    return _load_yaml(GROUP_VARS_PATH)


def _find_install_task(tasks: List[Dict]) -> Optional[Dict]:
    """Find the k3s install task that sets INSTALL_K3S_EXEC."""
    for task in tasks:
        env = task.get("environment", {})
        if "INSTALL_K3S_EXEC" in env:
            return task
    return None


def _get_install_exec(task: dict) -> str:
    """Extract the INSTALL_K3S_EXEC value from a task."""
    return task["environment"]["INSTALL_K3S_EXEC"]


def _get_install_version(task: dict) -> str:
    """Extract the INSTALL_K3S_VERSION value from a task."""
    return task["environment"]["INSTALL_K3S_VERSION"]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestK3sInstallFlagsCorrectness:
    """**Validates: Requirements 2.3, 2.4**"""

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_install_task_exists(self, role: str) -> None:
        """For any role, there SHALL be an install task with INSTALL_K3S_EXEC.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3, 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)

        assert install_task is not None, (
            f"Role '{role}': no task found with INSTALL_K3S_EXEC environment variable"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_pinned_version_is_set(self, role: str) -> None:
        """For any role, the install task SHALL reference the pinned k3s version.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3, 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        version_ref = _get_install_version(install_task)
        # The version should reference the k3s_version variable via Jinja2
        assert "k3s_version" in version_ref, (
            f"Role '{role}': INSTALL_K3S_VERSION does not reference k3s_version variable, "
            f"got '{version_ref}'"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_disable_flags_present(self, role: str) -> None:
        """For any role, the install command SHALL include disable flags for
        traefik and servicelb.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3, 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        # The INSTALL_K3S_EXEC should contain --disable= referencing disable_components
        assert "--disable=" in exec_value, (
            f"Role '{role}': INSTALL_K3S_EXEC missing --disable= flag, "
            f"got '{exec_value}'"
        )
        # Verify it references the disable_components variable
        assert "disable_components" in exec_value, (
            f"Role '{role}': --disable flag does not reference disable_components variable, "
            f"got '{exec_value}'"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_disable_components_defaults_correct(self, role: str) -> None:
        """For any role, the defaults SHALL list traefik and servicelb as
        disabled components.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3, 2.4**
        """
        defaults = _load_defaults(role)
        disable_list = set(defaults.get("disable_components", []))

        assert REQUIRED_DISABLE_COMPONENTS.issubset(disable_list), (
            f"Role '{role}': defaults disable_components={disable_list} "
            f"missing required {REQUIRED_DISABLE_COMPONENTS - disable_list}"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_group_vars_disable_components_correct(self, role: str) -> None:
        """For any role, the group_vars SHALL also list traefik and servicelb
        as disabled components (overrides defaults).

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3, 2.4**
        """
        group_vars = _load_group_vars()
        disable_list = set(group_vars.get("disable_components", []))

        assert REQUIRED_DISABLE_COMPONENTS.issubset(disable_list), (
            f"Group vars disable_components={disable_list} "
            f"missing required {REQUIRED_DISABLE_COMPONENTS - disable_list}"
        )

    # -- Init-specific properties --

    @given(role=st.just("init"))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_init_has_cluster_init_flag(self, role: str) -> None:
        """For the init role, the install command SHALL include --cluster-init.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.3**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--cluster-init" in exec_value, (
            f"Role 'init': INSTALL_K3S_EXEC missing --cluster-init flag, "
            f"got '{exec_value}'"
        )

    # -- Join-specific properties --

    @given(role=st.just("join"))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_join_has_server_url(self, role: str) -> None:
        """For the join role, the install command SHALL include --server=
        pointing to the init node's API VIP.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--server=" in exec_value, (
            f"Role 'join': INSTALL_K3S_EXEC missing --server= flag, "
            f"got '{exec_value}'"
        )
        # Should reference the api_server_vip and api_server_port variables
        assert "api_server_vip" in exec_value, (
            f"Role 'join': --server flag does not reference api_server_vip, "
            f"got '{exec_value}'"
        )
        assert "api_server_port" in exec_value, (
            f"Role 'join': --server flag does not reference api_server_port, "
            f"got '{exec_value}'"
        )

    @given(role=st.just("join"))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_join_has_token(self, role: str) -> None:
        """For the join role, the install command SHALL include --token=
        with the cluster token.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--token=" in exec_value, (
            f"Role 'join': INSTALL_K3S_EXEC missing --token= flag, "
            f"got '{exec_value}'"
        )

    @given(role=st.just("join"))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_join_does_not_have_cluster_init(self, role: str) -> None:
        """For the join role, the install command SHALL NOT include --cluster-init.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 2.4**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--cluster-init" not in exec_value, (
            f"Role 'join': INSTALL_K3S_EXEC should NOT contain --cluster-init, "
            f"got '{exec_value}'"
        )

    # -- etcd snapshot properties (both roles) --

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_etcd_snapshot_schedule_flag_present(self, role: str) -> None:
        """For any role, the install command SHALL include --etcd-snapshot-schedule-cron.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 7.3**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--etcd-snapshot-schedule-cron" in exec_value, (
            f"Role '{role}': INSTALL_K3S_EXEC missing --etcd-snapshot-schedule-cron flag, "
            f"got '{exec_value}'"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_etcd_snapshot_retention_flag_present(self, role: str) -> None:
        """For any role, the install command SHALL include --etcd-snapshot-retention.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 7.3**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--etcd-snapshot-retention" in exec_value, (
            f"Role '{role}': INSTALL_K3S_EXEC missing --etcd-snapshot-retention flag, "
            f"got '{exec_value}'"
        )

    @given(role=st.sampled_from(ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_etcd_snapshot_dir_flag_present(self, role: str) -> None:
        """For any role, the install command SHALL include --etcd-snapshot-dir.

        Feature: k3s-homelab-platform, Property 3: k3s install flags are correct for each role
        **Validates: Requirements 7.3**
        """
        tasks = _load_tasks(role)
        install_task = _find_install_task(tasks)
        assert install_task is not None

        exec_value = _get_install_exec(install_task)
        assert "--etcd-snapshot-dir" in exec_value, (
            f"Role '{role}': INSTALL_K3S_EXEC missing --etcd-snapshot-dir flag, "
            f"got '{exec_value}'"
        )
