"""Property 7: Repository structure completeness.

Feature: k3s-homelab-platform, Property 7: Repository structure completeness
Validates: Requirements 9.2, 10.1

For any complete platform repository, the directory tree SHALL contain:
- bootstrap/cloud-init/ with one YAML file per node
- bootstrap/ansible/ with inventory, roles, and playbook files
- gitops/ with subdirectories for clusters/homelab-k3s/, infrastructure/,
  data-services/, apps/agentic/, and apps/custom/.
"""

import pathlib

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Expected directory structure derived from Requirements 9.2 and 10.1
# ---------------------------------------------------------------------------

REQUIRED_DIRS = [
    "bootstrap/cloud-init",
    "bootstrap/ansible",
    "bootstrap/ansible/inventory",
    "bootstrap/ansible/roles",
    "gitops/clusters/homelab-k3s",
    "gitops/infrastructure",
    "gitops/data-services",
    "gitops/apps/agentic",
    "gitops/apps/custom",
]

REQUIRED_ANSIBLE_ROLES = [
    "base_hardening",
    "k3s_server_init",
    "k3s_server_join",
    "kubeconfig_export",
    "cluster_smoke_tests",
    "node_cleanup",
]

NODE_INDICES = [0, 1, 2]

# project_root is read-only and invariant across iterations, safe to suppress
_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Property test: any subset of required dirs should exist in the repo
# ---------------------------------------------------------------------------


class TestRepoStructureCompleteness:
    """**Validates: Requirements 9.2, 10.1**"""

    @given(subset=st.sets(st.sampled_from(REQUIRED_DIRS), min_size=1))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_required_directories_exist(
        self, project_root: pathlib.Path, subset: set[str]
    ) -> None:
        """For any subset of required directories, each SHALL exist.

        Feature: k3s-homelab-platform, Property 7: Repository structure completeness
        **Validates: Requirements 9.2, 10.1**
        """
        for rel_dir in subset:
            full_path = project_root / rel_dir
            assert full_path.is_dir(), (
                f"Required directory missing: {rel_dir}"
            )

    @given(node_idx=st.sampled_from(NODE_INDICES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_cloud_init_has_yaml_per_node(
        self, project_root: pathlib.Path, node_idx: int
    ) -> None:
        """For any node index, bootstrap/cloud-init/ SHALL contain a YAML file.

        Feature: k3s-homelab-platform, Property 7: Repository structure completeness
        **Validates: Requirements 9.2, 10.1**
        """
        ci_dir = project_root / "bootstrap" / "cloud-init"
        node_file = ci_dir / f"node-{node_idx}.yaml"
        assert node_file.is_file(), (
            f"Missing cloud-init file for node-{node_idx}: {node_file}"
        )

    @given(role=st.sampled_from(REQUIRED_ANSIBLE_ROLES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_ansible_roles_exist(
        self, project_root: pathlib.Path, role: str
    ) -> None:
        """For any required Ansible role, the role directory SHALL exist
        under bootstrap/ansible/roles/ with a tasks/ subdirectory.

        Feature: k3s-homelab-platform, Property 7: Repository structure completeness
        **Validates: Requirements 9.2, 10.1**
        """
        role_dir = project_root / "bootstrap" / "ansible" / "roles" / role
        assert role_dir.is_dir(), (
            f"Required Ansible role directory missing: {role}"
        )
        tasks_dir = role_dir / "tasks"
        assert tasks_dir.is_dir(), (
            f"Ansible role '{role}' missing tasks/ subdirectory"
        )

    @given(
        subdir=st.sampled_from(
            [
                "clusters/homelab-k3s",
                "infrastructure",
                "data-services",
                "apps/agentic",
                "apps/custom",
            ]
        )
    )
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_gitops_subdirectories_exist(
        self, project_root: pathlib.Path, subdir: str
    ) -> None:
        """For any required gitops subdirectory, it SHALL exist under gitops/.

        Feature: k3s-homelab-platform, Property 7: Repository structure completeness
        **Validates: Requirements 9.2, 10.1**
        """
        full_path = project_root / "gitops" / subdir
        assert full_path.is_dir(), (
            f"Required gitops subdirectory missing: gitops/{subdir}"
        )
