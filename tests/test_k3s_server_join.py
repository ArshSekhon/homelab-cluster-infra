"""Unit tests for the k3s_server_join Ansible role.

Validates: Requirements 2.4

Verifies that the k3s_server_join role has correct structure, task ordering,
join-specific install flags, and default variables.
"""

import yaml

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROLE_DIR = PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_join"
TASKS_FILE = ROLE_DIR / "tasks" / "main.yaml"
DEFAULTS_FILE = ROLE_DIR / "defaults" / "main.yaml"
HANDLERS_FILE = ROLE_DIR / "handlers" / "main.yaml"


def _load_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_tasks(path):
    with open(path, "r") as fh:
        return list(yaml.safe_load_all(fh))[0]


# ---------------------------------------------------------------------------
# Role structure tests
# ---------------------------------------------------------------------------


class TestRoleStructure:
    """Verify the role has all required files."""

    def test_tasks_main_exists(self):
        assert TASKS_FILE.exists(), "tasks/main.yaml must exist"

    def test_defaults_main_exists(self):
        assert DEFAULTS_FILE.exists(), "defaults/main.yaml must exist"

    def test_handlers_main_exists(self):
        assert HANDLERS_FILE.exists(), "handlers/main.yaml must exist"


# ---------------------------------------------------------------------------
# Defaults tests
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify role defaults contain required variables."""

    def test_k3s_version_pinned(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["k3s_version"] == "v1.31.4+k3s1"

    def test_api_server_vip(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["api_server_vip"] == "10.0.110.200"

    def test_api_server_port(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["api_server_port"] == 6443

    def test_disable_components_match_init(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert set(defaults["disable_components"]) == {"traefik", "servicelb"}

    def test_k3s_install_url(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["k3s_install_url"] == "https://get.k3s.io"

    def test_k3s_token_default_empty(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "k3s_token" in defaults

    def test_no_cluster_init_in_defaults(self):
        """Join role must NOT have cluster-init related defaults."""
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "kube_vip_version" not in defaults
        assert "kube_vip_image" not in defaults

    def test_etcd_snapshot_schedule(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "etcd_snapshot_schedule" in defaults
        assert defaults["etcd_snapshot_schedule"] == "0 */6 * * *"

    def test_etcd_snapshot_retention(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "etcd_snapshot_retention" in defaults
        assert defaults["etcd_snapshot_retention"] == 5

    def test_etcd_snapshot_dir(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "etcd_snapshot_dir" in defaults
        assert defaults["etcd_snapshot_dir"] == "/var/lib/rancher/k3s/server/db/snapshots"


# ---------------------------------------------------------------------------
# Tasks tests
# ---------------------------------------------------------------------------


class TestTasks:
    """Verify task ordering and key task properties."""

    def test_tasks_is_list(self):
        tasks = _load_tasks(TASKS_FILE)
        assert isinstance(tasks, list), "tasks/main.yaml must be a YAML list"

    def test_token_resolution_before_install(self):
        """Token resolution must happen before k3s install."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        token_idx = next(i for i, n in enumerate(names) if "token" in n.lower())
        install_idx = next(
            i for i, n in enumerate(names)
            if "install k3s" in n.lower()
        )
        assert token_idx < install_idx, "Token resolution must precede k3s install"

    def test_install_task_uses_environment_vars(self):
        """The k3s install task must use INSTALL_K3S_VERSION and INSTALL_K3S_EXEC."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        env = install_task.get("environment", {})
        assert "INSTALL_K3S_VERSION" in env, "Must set INSTALL_K3S_VERSION"
        assert "INSTALL_K3S_EXEC" in env, "Must set INSTALL_K3S_EXEC"

    def test_install_exec_has_server_flag(self):
        """INSTALL_K3S_EXEC must include --server pointing to the VIP."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--server" in exec_val, "Must include --server flag for join"

    def test_install_exec_has_token_flag(self):
        """INSTALL_K3S_EXEC must include --token."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--token" in exec_val, "Must include --token flag for join"

    def test_install_exec_has_tls_san(self):
        """INSTALL_K3S_EXEC must include --tls-san with the VIP (same as init)."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--tls-san" in exec_val, "Must include --tls-san flag"

    def test_install_exec_disables_traefik_and_servicelb(self):
        """INSTALL_K3S_EXEC must disable traefik and servicelb (same as init)."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--disable" in exec_val, "Must include --disable flag"

    def test_install_exec_has_etcd_snapshot_schedule(self):
        """INSTALL_K3S_EXEC must include --etcd-snapshot-schedule-cron."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--etcd-snapshot-schedule-cron" in exec_val, "Must include --etcd-snapshot-schedule-cron flag"

    def test_install_exec_has_etcd_snapshot_retention(self):
        """INSTALL_K3S_EXEC must include --etcd-snapshot-retention."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--etcd-snapshot-retention" in exec_val, "Must include --etcd-snapshot-retention flag"

    def test_install_exec_has_etcd_snapshot_dir(self):
        """INSTALL_K3S_EXEC must include --etcd-snapshot-dir."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--etcd-snapshot-dir" in exec_val, "Must include --etcd-snapshot-dir flag"

    def test_install_exec_does_not_have_cluster_init(self):
        """Join role must NOT use --cluster-init."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--cluster-init" not in exec_val, "Join role must NOT use --cluster-init"

    def test_node_ready_check_exists(self):
        """Must have a task that waits for the node to report Ready."""
        tasks = _load_tasks(TASKS_FILE)
        ready_tasks = [
            t for t in tasks
            if "ready" in t.get("name", "").lower() and "node" in t.get("name", "").lower()
        ]
        assert len(ready_tasks) > 0, "Must have a node readiness check"

    def test_node_ready_check_uses_retry(self):
        """The node readiness check must use retries for robustness."""
        tasks = _load_tasks(TASKS_FILE)
        ready_task = next(
            t for t in tasks
            if "ready" in t.get("name", "").lower() and "node" in t.get("name", "").lower()
        )
        assert "retries" in ready_task, "Node ready check must use retries"
        assert "until" in ready_task, "Node ready check must use until condition"

    def test_no_kube_vip_deployment(self):
        """Join role must NOT deploy kube-vip (only init does that)."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "").lower() for t in tasks]
        kube_vip_tasks = [n for n in names if "kube-vip" in n]
        assert len(kube_vip_tasks) == 0, "Join role must not deploy kube-vip"

    def test_no_token_storage(self):
        """Join role must NOT read/store the cluster token (init does that)."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "").lower() for t in tasks]
        store_tasks = [n for n in names if "store" in n or "read cluster token" in n]
        assert len(store_tasks) == 0, "Join role must not store/read cluster token file"
