"""Property 4: Kubeconfig endpoint rewrite.

Feature: k3s-homelab-platform, Property 4: Kubeconfig endpoint rewrite
Validates: Requirements 2.5

For any kubeconfig retrieved from a k3s node, rewriting the API server
endpoint to the target address and then parsing the result SHALL produce
a valid kubeconfig with the server field matching the target address and port.
"""

import re

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Strategies — generate realistic kubeconfig inputs
# ---------------------------------------------------------------------------

# Valid IPv4 octets (1-254 to avoid network/broadcast edge cases)
_octet = st.integers(min_value=1, max_value=254)

ipv4_addresses = st.tuples(_octet, _octet, _octet, _octet).map(
    lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"
)

# Valid port numbers (1024-65535 — unprivileged range, realistic for k8s API)
valid_ports = st.integers(min_value=1024, max_value=65535)

# Random source port on 127.0.0.1 (what k3s writes into its kubeconfig)
source_ports = st.integers(min_value=1, max_value=65535)

_suppress = [HealthCheck.function_scoped_fixture]


def _build_kubeconfig(source_port: int) -> str:
    """Build a minimal but valid kubeconfig YAML with 127.0.0.1:<port>."""
    return yaml.dump(
        {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [
                {
                    "cluster": {
                        "certificate-authority-data": "LS0tLS1CRUdJTi...",
                        "server": f"https://127.0.0.1:{source_port}",
                    },
                    "name": "default",
                }
            ],
            "contexts": [
                {
                    "context": {"cluster": "default", "user": "default"},
                    "name": "default",
                }
            ],
            "current-context": "default",
            "users": [
                {
                    "name": "default",
                    "user": {
                        "client-certificate-data": "LS0tLS1CRUdJTi...",
                        "client-key-data": "LS0tLS1CRUdJTi...",
                    },
                }
            ],
        },
        default_flow_style=False,
    )


def _rewrite_endpoint(kubeconfig_str: str, vip: str, port: int) -> str:
    """Apply the same regex_replace logic used by the Ansible kubeconfig_export role.

    Ansible filter:
        regex_replace('https://127\\.0\\.0\\.1:\\d+',
                       'https://' + api_server_vip + ':' + (api_server_port | string))
    """
    return re.sub(
        r"https://127\.0\.0\.1:\d+",
        f"https://{vip}:{port}",
        kubeconfig_str,
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestKubeconfigEndpointRewrite:
    """**Validates: Requirements 2.5**"""

    @given(
        vip=ipv4_addresses,
        target_port=valid_ports,
        source_port=source_ports,
    )
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_rewritten_kubeconfig_is_valid_yaml(
        self, vip: str, target_port: int, source_port: int
    ) -> None:
        """For any kubeconfig, rewriting the endpoint SHALL produce valid YAML.

        Feature: k3s-homelab-platform, Property 4: Kubeconfig endpoint rewrite
        **Validates: Requirements 2.5**
        """
        raw = _build_kubeconfig(source_port)
        rewritten = _rewrite_endpoint(raw, vip, target_port)
        parsed = yaml.safe_load(rewritten)

        assert parsed is not None, "Rewritten kubeconfig is not valid YAML"
        assert parsed.get("apiVersion") == "v1"
        assert parsed.get("kind") == "Config"

    @given(
        vip=ipv4_addresses,
        target_port=valid_ports,
        source_port=source_ports,
    )
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_server_field_matches_target(
        self, vip: str, target_port: int, source_port: int
    ) -> None:
        """For any kubeconfig, the rewritten server field SHALL match the
        target VIP and port exactly.

        Feature: k3s-homelab-platform, Property 4: Kubeconfig endpoint rewrite
        **Validates: Requirements 2.5**
        """
        raw = _build_kubeconfig(source_port)
        rewritten = _rewrite_endpoint(raw, vip, target_port)
        parsed = yaml.safe_load(rewritten)

        server = parsed["clusters"][0]["cluster"]["server"]
        expected = f"https://{vip}:{target_port}"

        assert server == expected, (
            f"Server field '{server}' does not match expected '{expected}'"
        )

    @given(
        vip=ipv4_addresses,
        target_port=valid_ports,
        source_port=source_ports,
    )
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_no_localhost_remains(
        self, vip: str, target_port: int, source_port: int
    ) -> None:
        """For any kubeconfig, after rewriting there SHALL be no remaining
        references to https://127.0.0.1 in the output.

        Feature: k3s-homelab-platform, Property 4: Kubeconfig endpoint rewrite
        **Validates: Requirements 2.5**
        """
        raw = _build_kubeconfig(source_port)
        rewritten = _rewrite_endpoint(raw, vip, target_port)

        assert "https://127.0.0.1" not in rewritten, (
            "Rewritten kubeconfig still contains https://127.0.0.1"
        )

    @given(
        vip=ipv4_addresses,
        target_port=valid_ports,
        source_port=source_ports,
    )
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_non_server_fields_preserved(
        self, vip: str, target_port: int, source_port: int
    ) -> None:
        """For any kubeconfig, rewriting SHALL preserve all non-server fields
        (contexts, users, certificate data).

        Feature: k3s-homelab-platform, Property 4: Kubeconfig endpoint rewrite
        **Validates: Requirements 2.5**
        """
        raw = _build_kubeconfig(source_port)
        original = yaml.safe_load(raw)
        rewritten = yaml.safe_load(_rewrite_endpoint(raw, vip, target_port))

        # Contexts preserved
        assert rewritten["contexts"] == original["contexts"]
        # Users preserved
        assert rewritten["users"] == original["users"]
        # current-context preserved
        assert rewritten["current-context"] == original["current-context"]
        # Certificate data preserved
        orig_cluster = original["clusters"][0]["cluster"]
        new_cluster = rewritten["clusters"][0]["cluster"]
        assert (
            new_cluster["certificate-authority-data"]
            == orig_cluster["certificate-authority-data"]
        )
