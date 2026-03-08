"""Property 2: Ansible inventory maps all nodes correctly.

Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
Validates: Requirements 2.1

For any node in the set {node-0, node-1, node-2},
the Ansible inventory SHALL contain a host entry with the correct fixed IP
address (10.0.110.{10,11,12} respectively), the correct FQDN
(node-{0,1,2}.cluster.arpa), and a k3s role assignment (init for node-0,
join for node-1 and node-2).
"""

import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants derived from the design document
# ---------------------------------------------------------------------------

NODE_DEFINITIONS = {
    "node-0": {
        "ansible_host": "10.0.110.10",
        "node_fqdn": "node-0.cluster.arpa",
        "k3s_role": "init",
    },
    "node-1": {
        "ansible_host": "10.0.110.11",
        "node_fqdn": "node-1.cluster.arpa",
        "k3s_role": "join",
    },
    "node-2": {
        "ansible_host": "10.0.110.12",
        "node_fqdn": "node-2.cluster.arpa",
        "k3s_role": "join",
    },
}

ALL_NODE_NAMES = list(NODE_DEFINITIONS.keys())

_suppress = [HealthCheck.function_scoped_fixture]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_inventory() -> dict:
    """Load and parse the Ansible inventory YAML."""
    path = PROJECT_ROOT / "bootstrap" / "ansible" / "inventory" / "hosts.yaml"
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _get_hosts(inventory: dict) -> dict:
    """Extract the hosts dict from the k3s_servers group."""
    return inventory["all"]["children"]["k3s_servers"]["hosts"]


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestAnsibleInventoryCorrectness:
    """**Validates: Requirements 2.1**"""

    @given(node_name=st.sampled_from(ALL_NODE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_node_present_in_inventory(self, node_name: str) -> None:
        """For any node in the defined set, the inventory SHALL contain
        a host entry for that node.

        Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
        **Validates: Requirements 2.1**
        """
        inventory = _load_inventory()
        hosts = _get_hosts(inventory)

        assert node_name in hosts, (
            f"Node '{node_name}' not found in inventory hosts"
        )

    @given(node_name=st.sampled_from(ALL_NODE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_node_has_correct_ip(self, node_name: str) -> None:
        """For any node, the inventory SHALL map it to the correct fixed IP.

        Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
        **Validates: Requirements 2.1**
        """
        inventory = _load_inventory()
        hosts = _get_hosts(inventory)
        expected_ip = NODE_DEFINITIONS[node_name]["ansible_host"]

        assert hosts[node_name]["ansible_host"] == expected_ip, (
            f"Node '{node_name}': expected IP '{expected_ip}', "
            f"got '{hosts[node_name].get('ansible_host')}'"
        )

    @given(node_name=st.sampled_from(ALL_NODE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_node_has_correct_fqdn(self, node_name: str) -> None:
        """For any node, the inventory SHALL map it to the correct FQDN.

        Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
        **Validates: Requirements 2.1**
        """
        inventory = _load_inventory()
        hosts = _get_hosts(inventory)
        expected_fqdn = NODE_DEFINITIONS[node_name]["node_fqdn"]

        assert hosts[node_name]["node_fqdn"] == expected_fqdn, (
            f"Node '{node_name}': expected FQDN '{expected_fqdn}', "
            f"got '{hosts[node_name].get('node_fqdn')}'"
        )

    @given(node_name=st.sampled_from(ALL_NODE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_node_has_correct_k3s_role(self, node_name: str) -> None:
        """For any node, the inventory SHALL assign the correct k3s role
        (init for node-0, join for node-1 and node-2).

        Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
        **Validates: Requirements 2.1**
        """
        inventory = _load_inventory()
        hosts = _get_hosts(inventory)
        expected_role = NODE_DEFINITIONS[node_name]["k3s_role"]

        assert hosts[node_name]["k3s_role"] == expected_role, (
            f"Node '{node_name}': expected k3s_role '{expected_role}', "
            f"got '{hosts[node_name].get('k3s_role')}'"
        )

    @given(node_name=st.sampled_from(ALL_NODE_NAMES))
    @settings(max_examples=100, suppress_health_check=_suppress)
    def test_inventory_contains_all_three_nodes(self, node_name: str) -> None:
        """The inventory SHALL contain exactly the three expected nodes.

        Feature: k3s-homelab-platform, Property 2: Ansible inventory maps all nodes correctly
        **Validates: Requirements 2.1**
        """
        inventory = _load_inventory()
        hosts = _get_hosts(inventory)

        assert set(hosts.keys()) == set(ALL_NODE_NAMES), (
            f"Inventory hosts mismatch: expected {set(ALL_NODE_NAMES)}, "
            f"got {set(hosts.keys())}"
        )
