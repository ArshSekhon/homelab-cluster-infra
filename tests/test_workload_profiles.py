"""Property 6: Workload profile completeness.

Feature: k3s-homelab-platform, Property 6: Workload profile completeness
Validates: Requirements 6.3

For all defined workload profiles (agentic-realtime, agentic-batch, custom-app),
each profile SHALL specify CPU requests and limits, memory requests and limits,
at least one probe configuration (liveness), and a PodDisruptionBudget
minAvailable value.
"""

from typing import Dict

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILE_NAMES = [
    "agentic-realtime",
    "agentic-batch",
    "custom-app",
]

# Required data keys that every workload profile ConfigMap must contain
REQUIRED_RESOURCE_KEYS = [
    "cpu-request",
    "cpu-limit",
    "memory-request",
    "memory-limit",
]

# Suppress fixture-scoped warning — manifest files are read-only
_suppress = [HealthCheck.function_scoped_fixture]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AGENTIC_DIR = PROJECT_ROOT / "gitops" / "apps" / "agentic"
CUSTOM_DIR = PROJECT_ROOT / "gitops" / "apps" / "custom"


def _load_workload_profiles() -> Dict[str, dict]:
    """Load all workload profile ConfigMaps from the apps directories.

    Returns a dict keyed by profile name (extracted from the
    'workload-profile' label), mapping to the ConfigMap document.
    """
    result: Dict[str, dict] = {}
    profile_files = [
        AGENTIC_DIR / "workload-profiles.yaml",
        CUSTOM_DIR / "workload-profiles.yaml",
    ]
    for path in profile_files:
        if not path.exists():
            continue
        with open(path, "r") as fh:
            docs = list(yaml.safe_load_all(fh))
        for doc in docs:
            if not doc or doc.get("kind") != "ConfigMap":
                continue
            labels = doc.get("metadata", {}).get("labels", {})
            profile_name = labels.get("workload-profile")
            if profile_name:
                result[profile_name] = doc
    return result


# Pre-load once — files are static
_ALL_PROFILES = _load_workload_profiles()


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestWorkloadProfileCompleteness:
    """**Validates: Requirements 6.3**"""

    @given(profile=st.sampled_from(PROFILE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_profile_exists(self, profile: str) -> None:
        """For any defined profile name, a matching ConfigMap SHALL exist.

        Feature: k3s-homelab-platform, Property 6: Workload profile completeness
        **Validates: Requirements 6.3**
        """
        assert profile in _ALL_PROFILES, (
            f"Workload profile '{profile}' not found. "
            f"Available profiles: {list(_ALL_PROFILES.keys())}"
        )

    @given(profile=st.sampled_from(PROFILE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_cpu_and_memory_resources_specified(self, profile: str) -> None:
        """For any profile, CPU and memory requests/limits SHALL be specified.

        Feature: k3s-homelab-platform, Property 6: Workload profile completeness
        **Validates: Requirements 6.3**
        """
        doc = _ALL_PROFILES[profile]
        data = doc.get("data", {})

        for key in REQUIRED_RESOURCE_KEYS:
            assert key in data, (
                f"Profile '{profile}': missing required key '{key}'"
            )
            value = str(data[key]).strip()
            assert value != "", (
                f"Profile '{profile}': key '{key}' must not be empty"
            )

    @given(profile=st.sampled_from(PROFILE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_liveness_probe_configured(self, profile: str) -> None:
        """For any profile, at least a liveness probe SHALL be configured.

        Feature: k3s-homelab-platform, Property 6: Workload profile completeness
        **Validates: Requirements 6.3**
        """
        doc = _ALL_PROFILES[profile]
        data = doc.get("data", {})

        assert "liveness-probe" in data, (
            f"Profile '{profile}': missing 'liveness-probe' configuration"
        )
        probe_value = str(data["liveness-probe"]).strip()
        assert probe_value != "", (
            f"Profile '{profile}': 'liveness-probe' must not be empty"
        )

    @given(profile=st.sampled_from(PROFILE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_pdb_min_available_specified(self, profile: str) -> None:
        """For any profile, a PDB minAvailable value SHALL be specified.

        Feature: k3s-homelab-platform, Property 6: Workload profile completeness
        **Validates: Requirements 6.3**
        """
        doc = _ALL_PROFILES[profile]
        data = doc.get("data", {})

        assert "pdb-min-available" in data, (
            f"Profile '{profile}': missing 'pdb-min-available' value"
        )
        # pdb-min-available can be "0" which is valid, so just check it exists
        # and is not an empty string
        value = str(data["pdb-min-available"]).strip()
        assert value != "", (
            f"Profile '{profile}': 'pdb-min-available' must not be empty"
        )
