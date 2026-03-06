"""Tests for the base_hardening Ansible role.

Validates: Requirements 2.2

The base_hardening role SHALL perform idempotent package and state checks:
packages installed, kernel modules loaded, sysctls applied, swap disabled,
and systemd-timesyncd running.
"""

import pathlib

import pytest
import yaml

from conftest import PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants from the design document
# ---------------------------------------------------------------------------

REQUIRED_PACKAGES = ["curl", "jq", "nfs-common", "open-iscsi", "qemu-guest-agent"]
REQUIRED_KERNEL_MODULES = ["overlay", "br_netfilter", "iscsi_tcp"]
REQUIRED_SYSCTLS = {
    "net.bridge.bridge-nf-call-iptables": 1,
    "net.bridge.bridge-nf-call-ip6tables": 1,
    "net.ipv4.ip_forward": 1,
}

ROLE_DIR = PROJECT_ROOT / "bootstrap" / "ansible" / "roles" / "base_hardening"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_tasks() -> list[dict]:
    """Load the main tasks file for the base_hardening role."""
    path = ROLE_DIR / "tasks" / "main.yaml"
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _load_defaults() -> dict:
    """Load the defaults file for the base_hardening role."""
    path = ROLE_DIR / "defaults" / "main.yaml"
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def _find_task(tasks: list[dict], module_key: str) -> list[dict]:
    """Return all tasks that use a given Ansible module key."""
    return [t for t in tasks if module_key in t]


# ---------------------------------------------------------------------------
# Defaults tests
# ---------------------------------------------------------------------------


class TestBaseHardeningDefaults:
    """Validate the role defaults contain all required values."""

    def test_defaults_file_exists(self) -> None:
        assert (ROLE_DIR / "defaults" / "main.yaml").is_file()

    def test_defaults_contains_all_packages(self) -> None:
        defaults = _load_defaults()
        assert set(REQUIRED_PACKAGES).issubset(set(defaults["hardening_packages"]))

    def test_defaults_contains_all_kernel_modules(self) -> None:
        defaults = _load_defaults()
        assert set(REQUIRED_KERNEL_MODULES).issubset(
            set(defaults["hardening_kernel_modules"])
        )

    def test_defaults_contains_all_sysctls(self) -> None:
        defaults = _load_defaults()
        for key, value in REQUIRED_SYSCTLS.items():
            assert key in defaults["hardening_sysctls"], f"Missing sysctl: {key}"
            assert defaults["hardening_sysctls"][key] == value


# ---------------------------------------------------------------------------
# Tasks structure tests
# ---------------------------------------------------------------------------


class TestBaseHardeningTasks:
    """Validate the role tasks cover all required hardening areas."""

    def test_tasks_file_exists(self) -> None:
        assert (ROLE_DIR / "tasks" / "main.yaml").is_file()

    def test_tasks_is_nonempty_list(self) -> None:
        tasks = _load_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_has_package_install_task(self) -> None:
        """Role SHALL install baseline packages via apt."""
        tasks = _load_tasks()
        apt_tasks = _find_task(tasks, "ansible.builtin.apt")
        assert len(apt_tasks) >= 1, "No ansible.builtin.apt task found"

    def test_has_kernel_module_persist_task(self) -> None:
        """Role SHALL persist kernel modules via /etc/modules-load.d/."""
        tasks = _load_tasks()
        copy_tasks = _find_task(tasks, "ansible.builtin.copy")
        module_persist = [
            t for t in copy_tasks
            if "modules-load.d" in str(t.get("ansible.builtin.copy", {}).get("dest", ""))
        ]
        assert len(module_persist) >= 1, "No task persists kernel modules to /etc/modules-load.d/"

    def test_has_kernel_module_load_task(self) -> None:
        """Role SHALL load kernel modules immediately via modprobe."""
        tasks = _load_tasks()
        modprobe_tasks = _find_task(tasks, "community.general.modprobe")
        assert len(modprobe_tasks) >= 1, "No community.general.modprobe task found"

    def test_has_sysctl_task(self) -> None:
        """Role SHALL apply sysctl settings."""
        tasks = _load_tasks()
        sysctl_tasks = _find_task(tasks, "ansible.posix.sysctl")
        assert len(sysctl_tasks) >= 1, "No ansible.posix.sysctl task found"

    def test_has_swap_disable_task(self) -> None:
        """Role SHALL disable swap at runtime."""
        tasks = _load_tasks()
        task_names = [t.get("name", "").lower() for t in tasks]
        swap_tasks = [n for n in task_names if "swap" in n]
        assert len(swap_tasks) >= 1, "No task disabling swap found"

    def test_has_timesyncd_task(self) -> None:
        """Role SHALL enable and start systemd-timesyncd."""
        tasks = _load_tasks()
        systemd_tasks = _find_task(tasks, "ansible.builtin.systemd")
        timesyncd = [
            t for t in systemd_tasks
            if t.get("ansible.builtin.systemd", {}).get("name") == "systemd-timesyncd"
        ]
        assert len(timesyncd) >= 1, "No task enabling systemd-timesyncd found"

    def test_all_tasks_use_become(self) -> None:
        """All tasks in this role require root — they SHALL use become: true."""
        tasks = _load_tasks()
        for task in tasks:
            assert task.get("become") is True, (
                f"Task '{task.get('name', '<unnamed>')}' is missing become: true"
            )

    def test_sysctl_task_writes_to_k8s_conf(self) -> None:
        """Sysctl settings SHALL be persisted to /etc/sysctl.d/k8s.conf."""
        tasks = _load_tasks()
        sysctl_tasks = _find_task(tasks, "ansible.posix.sysctl")
        for t in sysctl_tasks:
            sysctl_conf = t["ansible.posix.sysctl"]
            assert sysctl_conf.get("sysctl_file") == "/etc/sysctl.d/k8s.conf"

    def test_swap_fstab_cleanup(self) -> None:
        """Role SHALL remove swap entries from /etc/fstab."""
        tasks = _load_tasks()
        lineinfile_tasks = _find_task(tasks, "ansible.builtin.lineinfile")
        fstab_swap = [
            t for t in lineinfile_tasks
            if t.get("ansible.builtin.lineinfile", {}).get("path") == "/etc/fstab"
            and "swap" in str(t.get("ansible.builtin.lineinfile", {}).get("regexp", ""))
        ]
        assert len(fstab_swap) >= 1, "No task removes swap entries from /etc/fstab"
