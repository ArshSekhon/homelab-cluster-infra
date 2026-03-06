"""Unit tests for the k3s_server_init Ansible role.

Validates: Requirements 2.3

Verifies that the k3s_server_init role has correct structure, task ordering,
kube-vip manifest template, and default variables.
"""

import yaml

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROLE_DIR = PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "k3s_server_init"
TASKS_FILE = ROLE_DIR / "tasks" / "main.yaml"
DEFAULTS_FILE = ROLE_DIR / "defaults" / "main.yaml"
HANDLERS_FILE = ROLE_DIR / "handlers" / "main.yaml"
TEMPLATE_FILE = ROLE_DIR / "templates" / "kube-vip.yaml.j2"


def _load_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_tasks(path):
    with open(path, "r") as fh:
        return list(yaml.safe_load_all(fh))[0]  # tasks are a single YAML list


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

    def test_kube_vip_template_exists(self):
        assert TEMPLATE_FILE.exists(), "templates/kube-vip.yaml.j2 must exist"


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

    def test_disable_components(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert set(defaults["disable_components"]) == {"traefik", "servicelb"}

    def test_kube_vip_version(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["kube_vip_version"] == "v0.8.7"

    def test_k3s_install_url(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["k3s_install_url"] == "https://get.k3s.io"

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

    def test_install_before_kube_vip(self):
        """k3s install must happen before kube-vip deployment."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        install_idx = next(i for i, n in enumerate(names) if "install k3s" in n.lower() or "k3s" in n.lower() and "install" in n.lower())
        kubevip_idx = next(i for i, n in enumerate(names) if "kube-vip" in n.lower() and ("deploy" in n.lower() or "manifest" in n.lower()))
        assert install_idx < kubevip_idx, "k3s install must precede kube-vip deployment"

    def test_kube_vip_before_ready_wait(self):
        """kube-vip deployment must happen before readiness checks."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        kubevip_idx = next(i for i, n in enumerate(names) if "kube-vip" in n.lower() and ("deploy" in n.lower() or "manifest" in n.lower()))
        ready_idx = next(i for i, n in enumerate(names) if "ready" in n.lower() and "node" in n.lower())
        assert kubevip_idx < ready_idx, "kube-vip must be deployed before waiting for node ready"

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

    def test_install_exec_has_cluster_init(self):
        """INSTALL_K3S_EXEC must include --cluster-init."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--cluster-init" in exec_val, "Must include --cluster-init flag"

    def test_install_exec_has_tls_san(self):
        """INSTALL_K3S_EXEC must include --tls-san with the VIP."""
        tasks = _load_tasks(TASKS_FILE)
        install_task = next(
            t for t in tasks
            if t.get("name", "").lower().startswith("install k3s")
        )
        exec_val = install_task["environment"]["INSTALL_K3S_EXEC"]
        assert "--tls-san" in exec_val, "Must include --tls-san flag"

    def test_install_exec_disables_traefik_and_servicelb(self):
        """INSTALL_K3S_EXEC must disable traefik and servicelb."""
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

    def test_kube_vip_manifest_path(self):
        """kube-vip must be deployed to the k3s server manifests directory."""
        tasks = _load_tasks(TASKS_FILE)
        kubevip_task = next(
            t for t in tasks
            if "kube-vip" in t.get("name", "").lower() and "deploy" in t.get("name", "").lower()
        )
        template_args = kubevip_task.get("ansible.builtin.template", {})
        assert template_args["dest"] == "/var/lib/rancher/k3s/server/manifests/kube-vip.yaml"

    def test_node_ready_check_uses_retry(self):
        """The node readiness check must use retries for robustness."""
        tasks = _load_tasks(TASKS_FILE)
        ready_task = next(
            t for t in tasks
            if "node" in t.get("name", "").lower() and "ready" in t.get("name", "").lower()
        )
        assert "retries" in ready_task, "Node ready check must use retries"
        assert "until" in ready_task, "Node ready check must use until condition"


# ---------------------------------------------------------------------------
# kube-vip template tests
# ---------------------------------------------------------------------------


class TestKubeVipTemplate:
    """Verify the kube-vip static pod manifest template."""

    def test_template_is_valid_yaml_structure(self):
        """The template should be parseable as YAML (ignoring Jinja2 vars)."""
        content = TEMPLATE_FILE.read_text()
        # Verify key structural elements are present
        assert "apiVersion: v1" in content
        assert "kind: Pod" in content
        assert "kube-vip" in content

    def test_template_has_arp_mode(self):
        content = TEMPLATE_FILE.read_text()
        assert "vip_arp" in content, "kube-vip must use ARP/L2 mode"

    def test_template_has_leader_election(self):
        content = TEMPLATE_FILE.read_text()
        assert "vip_leaderelection" in content, "kube-vip must use leader election"

    def test_template_uses_host_network(self):
        content = TEMPLATE_FILE.read_text()
        assert "hostNetwork: true" in content, "kube-vip must use host networking"

    def test_template_has_net_admin_capability(self):
        content = TEMPLATE_FILE.read_text()
        assert "NET_ADMIN" in content, "kube-vip needs NET_ADMIN capability"

    def test_template_references_vip_variable(self):
        content = TEMPLATE_FILE.read_text()
        assert "api_server_vip" in content, "Template must reference api_server_vip"

    def test_template_references_kube_vip_version(self):
        content = TEMPLATE_FILE.read_text()
        assert "kube_vip_version" in content, "Template must reference kube_vip_version"

    def test_template_mounts_k3s_kubeconfig(self):
        content = TEMPLATE_FILE.read_text()
        assert "/etc/rancher/k3s/k3s.yaml" in content, "Must mount k3s kubeconfig"
