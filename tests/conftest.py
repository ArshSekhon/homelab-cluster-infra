"""Shared fixtures for k3s homelab platform tests."""

import pathlib

import pytest
import yaml
from hypothesis import settings

# ---------------------------------------------------------------------------
# Hypothesis profiles — design doc requires minimum 100 iterations
# ---------------------------------------------------------------------------

settings.register_profile("ci", max_examples=200)
settings.register_profile("default", max_examples=100)
settings.load_profile("default")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def project_root() -> pathlib.Path:
    """Return the absolute path to the repository root."""
    return PROJECT_ROOT


# ---------------------------------------------------------------------------
# Generic YAML loader
# ---------------------------------------------------------------------------


def _load_yaml(path: pathlib.Path):
    """Load a single YAML file and return its parsed content."""
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_all_yaml(path: pathlib.Path):
    """Load a multi-document YAML file and return a list of documents."""
    with open(path, "r") as fh:
        return list(yaml.safe_load_all(fh))


# ---------------------------------------------------------------------------
# Cloud-init fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cloud_init_dir() -> pathlib.Path:
    """Return the path to the cloud-init directory."""
    return PROJECT_ROOT / "bootstrap" / "cloud-init"


@pytest.fixture
def cloud_init_files(cloud_init_dir) -> dict[str, dict]:
    """Load all cloud-init YAML files, keyed by filename (e.g. 'node-0.yaml')."""
    result = {}
    for p in sorted(cloud_init_dir.glob("node-*.yaml")):
        result[p.name] = _load_yaml(p)
    return result


# ---------------------------------------------------------------------------
# Ansible fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ansible_dir() -> pathlib.Path:
    """Return the path to the Ansible directory."""
    return PROJECT_ROOT / "bootstrap" / "ansible"


@pytest.fixture
def ansible_inventory(ansible_dir) -> dict:
    """Load the Ansible inventory (hosts.yaml)."""
    return _load_yaml(ansible_dir / "inventory" / "hosts.yaml")


@pytest.fixture
def ansible_group_vars(ansible_dir) -> dict:
    """Load the k3s_servers group variables."""
    return _load_yaml(
        ansible_dir / "inventory" / "group_vars" / "k3s_servers.yaml"
    )


# ---------------------------------------------------------------------------
# Flux / GitOps fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gitops_dir() -> pathlib.Path:
    """Return the path to the gitops directory."""
    return PROJECT_ROOT / "gitops"


@pytest.fixture
def flux_cluster_dir(gitops_dir) -> pathlib.Path:
    """Return the path to the Flux cluster kustomizations directory."""
    return gitops_dir / "clusters" / "homelab-k3s"


@pytest.fixture
def flux_kustomizations(flux_cluster_dir) -> dict[str, dict]:
    """Load all Flux Kustomization YAML files from the cluster dir.

    Returns a dict keyed by stem name (e.g. 'platform-crds').
    Multi-document files are flattened; only Kustomization kinds are kept.
    """
    result = {}
    for p in sorted(flux_cluster_dir.glob("*.yaml")):
        # Skip the flux-system directory's own manifests
        if p.name.startswith("flux-system"):
            continue
        docs = _load_all_yaml(p)
        for doc in docs:
            if doc and doc.get("kind") == "Kustomization":
                name = doc["metadata"]["name"]
                result[name] = doc
    return result


# ---------------------------------------------------------------------------
# Workload profile fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def apps_agentic_dir(gitops_dir) -> pathlib.Path:
    return gitops_dir / "apps" / "agentic"


@pytest.fixture
def apps_custom_dir(gitops_dir) -> pathlib.Path:
    return gitops_dir / "apps" / "custom"
