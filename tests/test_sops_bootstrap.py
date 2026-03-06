"""Unit tests for the sops_bootstrap Ansible role.

Validates: Requirements 2.7, 3.1

Verifies that the sops_bootstrap role has correct structure, idempotent tasks,
proper defaults, and is wired into the site.yaml playbook.
"""

import yaml

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROLE_DIR = PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "sops_bootstrap"
TASKS_FILE = ROLE_DIR / "tasks" / "main.yaml"
DEFAULTS_FILE = ROLE_DIR / "defaults" / "main.yaml"
SITE_YAML = PROJECT_ROOT / "bootstrap" / "ansible" / "site.yaml"
GROUP_VARS = PROJECT_ROOT / "bootstrap" / "ansible" / "inventory" / "group_vars" / "k3s_servers.yaml"


def _load_yaml(path):
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_all_yaml(path):
    with open(path, "r") as fh:
        return list(yaml.safe_load_all(fh))


def _load_tasks(path):
    with open(path, "r") as fh:
        return list(yaml.safe_load_all(fh))[0]


# ---------------------------------------------------------------------------
# Role structure tests
# ---------------------------------------------------------------------------


class TestRoleStructure:
    """Verify the sops_bootstrap role has all required files."""

    def test_tasks_main_exists(self):
        assert TASKS_FILE.exists(), "tasks/main.yaml must exist"

    def test_defaults_main_exists(self):
        assert DEFAULTS_FILE.exists(), "defaults/main.yaml must exist"


# ---------------------------------------------------------------------------
# Defaults tests
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify role defaults contain required variables."""

    def test_sops_age_key_file_defined(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert "sops_age_key_file" in defaults

    def test_sops_namespace_is_flux_system(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["sops_namespace"] == "flux-system"

    def test_sops_secret_name(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["sops_secret_name"] == "sops-age"

    def test_sops_secret_key(self):
        defaults = _load_yaml(DEFAULTS_FILE)
        assert defaults["sops_secret_key"] == "age.agekey"


# ---------------------------------------------------------------------------
# Tasks tests
# ---------------------------------------------------------------------------


class TestTasks:
    """Verify task ordering and idempotency patterns."""

    def test_tasks_is_list(self):
        tasks = _load_tasks(TASKS_FILE)
        assert isinstance(tasks, list), "tasks/main.yaml must be a YAML list"

    def test_age_key_validation_is_first(self):
        """The role must validate the age key file exists before anything else."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        verify_idx = next(i for i, n in enumerate(names) if "age key" in n.lower() and "verify" in n.lower())
        assert verify_idx <= 1, "Age key verification should be among the first tasks"

    def test_namespace_created_before_secret(self):
        """flux-system namespace must be created before the secret."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        ns_idx = next(i for i, n in enumerate(names) if "namespace" in n.lower() and "create" in n.lower())
        secret_idx = next(i for i, n in enumerate(names) if "sops-age" in n.lower() and "create" in n.lower())
        assert ns_idx < secret_idx, "Namespace creation must precede secret creation"

    def test_secret_check_before_create(self):
        """The role must check if the secret exists before creating it (idempotency)."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        check_idx = next(i for i, n in enumerate(names) if "check" in n.lower() and "sops-age" in n.lower())
        create_idx = next(i for i, n in enumerate(names) if "create" in n.lower() and "sops-age" in n.lower())
        assert check_idx < create_idx, "Secret existence check must precede creation"

    def test_secret_creation_is_conditional(self):
        """The secret creation task must have a 'when' condition for idempotency."""
        tasks = _load_tasks(TASKS_FILE)
        create_task = next(
            t for t in tasks
            if "create" in t.get("name", "").lower() and "sops-age" in t.get("name", "").lower()
        )
        assert "when" in create_task, "Secret creation must be conditional"

    def test_temp_key_cleaned_up(self):
        """The temporary age key must be removed from the node after secret creation."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        has_cleanup = any("remove" in n.lower() and "age key" in n.lower() for n in names)
        assert has_cleanup, "Must clean up temporary age key from node"

    def test_verification_step_exists(self):
        """The role must verify the secret was created successfully."""
        tasks = _load_tasks(TASKS_FILE)
        names = [t.get("name", "") for t in tasks]
        has_verify = any("verify" in n.lower() and "sops-age" in n.lower() for n in names)
        assert has_verify, "Must verify sops-age secret exists after creation"


# ---------------------------------------------------------------------------
# Playbook wiring tests
# ---------------------------------------------------------------------------


class TestPlaybookWiring:
    """Verify sops_bootstrap is correctly wired into site.yaml."""

    @staticmethod
    def _load_plays():
        """Load site.yaml as a list of plays (single YAML document)."""
        return _load_yaml(SITE_YAML)

    def test_sops_bootstrap_in_site_yaml(self):
        """site.yaml must include the sops_bootstrap role."""
        plays = self._load_plays()
        role_names = []
        for play in plays:
            if play and "roles" in play:
                role_names.extend(play["roles"])
        assert "sops_bootstrap" in role_names, "sops_bootstrap must be in site.yaml"

    def test_sops_bootstrap_after_kubeconfig_export(self):
        """sops_bootstrap must run after kubeconfig_export (k3s must be up)."""
        plays = self._load_plays()
        kubeconfig_idx = None
        sops_idx = None
        for i, play in enumerate(plays):
            if play and "roles" in play:
                if "kubeconfig_export" in play["roles"]:
                    kubeconfig_idx = i
                if "sops_bootstrap" in play["roles"]:
                    sops_idx = i
        assert kubeconfig_idx is not None, "kubeconfig_export must be in site.yaml"
        assert sops_idx is not None, "sops_bootstrap must be in site.yaml"
        assert sops_idx > kubeconfig_idx, "sops_bootstrap must run after kubeconfig_export"

    def test_sops_bootstrap_runs_on_init_node(self):
        """sops_bootstrap play must target init nodes only."""
        plays = self._load_plays()
        sops_play = next(
            p for p in plays
            if p and "roles" in p and "sops_bootstrap" in p["roles"]
        )
        assert sops_play.get("when") == 'k3s_role == "init"', \
            "sops_bootstrap must run only on init nodes"


# ---------------------------------------------------------------------------
# Group vars tests
# ---------------------------------------------------------------------------


class TestGroupVars:
    """Verify sops_age_key_file is in group variables."""

    def test_sops_age_key_file_in_group_vars(self):
        gv = _load_yaml(GROUP_VARS)
        assert "sops_age_key_file" in gv, "sops_age_key_file must be in group_vars"
