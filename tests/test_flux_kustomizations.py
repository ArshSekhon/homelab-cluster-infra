"""Property 5: Flux Kustomization dependency chain and health configuration.

Feature: k3s-homelab-platform, Property 5: Flux Kustomization dependency chain and health configuration
Validates: Requirements 3.2, 3.3

For all Flux Kustomization manifests in the gitops directory, each Kustomization
SHALL have a dependsOn field consistent with the defined DAG:
- platform-crds has no dependencies
- platform-core depends on platform-crds
- storage and observability each depend on platform-core
- data-services depends on storage
- apps depends on both data-services and observability

Each Kustomization SHALL also have a non-empty interval field and either a
healthChecks list or wait: true.
"""

import pathlib
from typing import Dict, List

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants derived from the design document
# ---------------------------------------------------------------------------

KUSTOMIZATION_NAMES = [
    "platform-crds",
    "platform-core",
    "storage",
    "observability",
    "data-services",
    "apps",
]

# Expected dependency DAG: name -> sorted list of dependency names
EXPECTED_DEPS: Dict[str, List[str]] = {
    "platform-crds": [],
    "platform-core": ["platform-crds"],
    "storage": ["platform-core"],
    "observability": ["platform-core"],
    "data-services": ["storage"],
    "apps": ["data-services", "observability"],
}

# Suppress fixture-scoped warning — manifest files are read-only
_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLUSTER_DIR = PROJECT_ROOT / "gitops" / "clusters" / "homelab-k3s"


def _load_kustomizations() -> Dict[str, dict]:
    """Load all Flux Kustomization manifests from the cluster directory.

    Returns a dict keyed by metadata.name.
    """
    result: Dict[str, dict] = {}
    for p in sorted(CLUSTER_DIR.glob("*.yaml")):
        if p.name.startswith("flux-system"):
            continue
        with open(p, "r") as fh:
            docs = list(yaml.safe_load_all(fh))
        for doc in docs:
            if doc and doc.get("kind") == "Kustomization":
                name = doc["metadata"]["name"]
                result[name] = doc
    return result


# Pre-load once — files are static
_ALL_KUSTOMIZATIONS = _load_kustomizations()


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestFluxKustomizationDependencyChain:
    """**Validates: Requirements 3.2, 3.3**"""

    @given(name=st.sampled_from(KUSTOMIZATION_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_dependency_dag_is_correct(self, name: str) -> None:
        """For any Kustomization, its dependsOn SHALL match the expected DAG.

        Feature: k3s-homelab-platform, Property 5: Flux Kustomization dependency chain and health configuration
        **Validates: Requirements 3.2**
        """
        assert name in _ALL_KUSTOMIZATIONS, (
            f"Kustomization '{name}' not found in {CLUSTER_DIR}"
        )
        doc = _ALL_KUSTOMIZATIONS[name]
        spec = doc.get("spec", {})

        depends_on = spec.get("dependsOn", [])
        actual_deps = sorted(d["name"] for d in depends_on)
        expected = sorted(EXPECTED_DEPS[name])

        assert actual_deps == expected, (
            f"Kustomization '{name}': expected dependsOn={expected}, "
            f"got {actual_deps}"
        )

    @given(name=st.sampled_from(KUSTOMIZATION_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_interval_is_non_empty(self, name: str) -> None:
        """For any Kustomization, the interval field SHALL be non-empty.

        Feature: k3s-homelab-platform, Property 5: Flux Kustomization dependency chain and health configuration
        **Validates: Requirements 3.3**
        """
        assert name in _ALL_KUSTOMIZATIONS, (
            f"Kustomization '{name}' not found in {CLUSTER_DIR}"
        )
        doc = _ALL_KUSTOMIZATIONS[name]
        spec = doc.get("spec", {})

        interval = spec.get("interval")
        assert interval is not None and str(interval).strip() != "", (
            f"Kustomization '{name}': interval must be non-empty, "
            f"got '{interval}'"
        )

    @given(name=st.sampled_from(KUSTOMIZATION_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_health_check_or_wait(self, name: str) -> None:
        """For any Kustomization, it SHALL have either healthChecks or wait: true.

        Feature: k3s-homelab-platform, Property 5: Flux Kustomization dependency chain and health configuration
        **Validates: Requirements 3.3**
        """
        assert name in _ALL_KUSTOMIZATIONS, (
            f"Kustomization '{name}' not found in {CLUSTER_DIR}"
        )
        doc = _ALL_KUSTOMIZATIONS[name]
        spec = doc.get("spec", {})

        has_health_checks = bool(spec.get("healthChecks"))
        has_wait = spec.get("wait") is True

        assert has_health_checks or has_wait, (
            f"Kustomization '{name}': must have either healthChecks or "
            f"wait: true (healthChecks={spec.get('healthChecks')}, "
            f"wait={spec.get('wait')})"
        )

    @given(name=st.sampled_from(KUSTOMIZATION_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_decryption_references_sops_age(self, name: str) -> None:
        """For any Kustomization, spec.decryption SHALL reference sops-age secret.

        Feature: k3s-homelab-platform, Property 5: Flux Kustomization dependency chain and health configuration
        **Validates: Requirements 3.1**
        """
        assert name in _ALL_KUSTOMIZATIONS, (
            f"Kustomization '{name}' not found in {CLUSTER_DIR}"
        )
        doc = _ALL_KUSTOMIZATIONS[name]
        spec = doc.get("spec", {})

        decryption = spec.get("decryption")
        assert decryption is not None, (
            f"Kustomization '{name}': missing spec.decryption block"
        )
        assert decryption.get("provider") == "sops", (
            f"Kustomization '{name}': decryption.provider must be 'sops', "
            f"got '{decryption.get('provider')}'"
        )
        secret_ref = decryption.get("secretRef", {})
        assert secret_ref.get("name") == "sops-age", (
            f"Kustomization '{name}': decryption.secretRef.name must be "
            f"'sops-age', got '{secret_ref.get('name')}'"
        )

