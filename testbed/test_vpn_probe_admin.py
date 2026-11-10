"""Offline administrative-state and probe regression tests."""

import importlib.util
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FILES = Path(__file__).resolve().parents[1] / "ansible/roles/vpn_probe/files"
sys.path.insert(0, str(FILES))
import node_state  # noqa: E402

with patch.dict(
    os.environ,
    {
        "VPN_PROBE_SUBSCRIPTION_URL": "https://subscription.invalid/private",
        "VPN_PROBE_PUSH_URL": "https://metrics.invalid/import",
        "VPN_PROBE_PUSH_USER": "test",
        "VPN_PROBE_PUSH_PASSWORD": "test",
        "VPN_PROBE_PANEL_API_URL": "https://panel.invalid/api",
        "VPN_PROBE_PANEL_API_TOKEN": "test",
    },
):
    spec = importlib.util.spec_from_file_location(
        "vpn_probe_admin_test", FILES / "vpn-probe.py"
    )
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)


def payload(disabled=False):
    return {
        "response": [
            {
                "uuid": "one",
                "address": "192.0.2.1",
                "isDisabled": disabled,
                "isConnected": False,
                "rawConfig": {"privateKey": "must-not-be-cached"},
            }
        ]
    }


class NodeStateTests(unittest.TestCase):
    def test_offline_enabled_node_is_not_maintenance(self):
        nodes = node_state.parse_nodes(payload())
        flags, known = node_state.enabled_entries([{"host": "192.0.2.1"}], nodes)
        self.assertEqual(flags, [True])
        self.assertTrue(known)

    def test_disabled_and_reenabled(self):
        for disabled in [True, False]:
            flags, known = node_state.enabled_entries(
                [{"host": "192.0.2.1"}], node_state.parse_nodes(payload(disabled))
            )
            self.assertEqual(flags, [not disabled])
            self.assertTrue(known)

    def test_hostname_is_resolved_not_matched_by_display_name(self):
        with patch.object(node_state, "addresses", return_value={"192.0.2.1"}):
            flags, known = node_state.enabled_entries(
                [{"host": "renamed.example"}], node_state.parse_nodes(payload(True))
            )
        self.assertEqual(flags, [False])
        self.assertTrue(known)

    def test_unknown_and_shared_addresses_fail_open(self):
        for nodes in [
            [],
            [
                node_state.Node("a", "192.0.2.1", True),
                node_state.Node("b", "192.0.2.1", True),
            ],
        ]:
            flags, known = node_state.enabled_entries([{"host": "192.0.2.1"}], nodes)
            self.assertEqual(flags, [True])
            self.assertFalse(known)

    def test_dns_failure_does_not_hide_a_host(self):
        with patch.object(socket, "getaddrinfo", side_effect=socket.gaierror):
            flags, known = node_state.enabled_entries(
                [{"host": "unresolved.example"}], node_state.parse_nodes(payload(True))
            )
        self.assertEqual(flags, [True])
        self.assertFalse(known)

    def test_invalid_api_flags_are_not_coerced(self):
        data = payload()
        data["response"][0]["isDisabled"] = "false"
        with self.assertRaises(ValueError):
            node_state.parse_nodes(data)

    def test_cache_is_sanitized_and_retained_on_api_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "state.json"
            with patch.object(node_state.urllib.request, "urlopen") as request:
                request.return_value.__enter__.return_value.read.return_value = (
                    json.dumps(payload(True))
                )
                nodes, fresh, timestamp = node_state.load_state(
                    "https://panel.invalid/api", "secret", cache
                )
            self.assertTrue(fresh)
            self.assertTrue(nodes[0].disabled)
            self.assertNotIn("privateKey", cache.read_text())
            self.assertNotIn("secret", cache.read_text())
            self.assertEqual(cache.stat().st_mode & 0o777, 0o600)
            with patch.object(
                node_state.urllib.request, "urlopen", side_effect=OSError
            ):
                fallback, fresh, cached_time = node_state.load_state(
                    "https://panel.invalid/api", "secret", cache
                )
            self.assertFalse(fresh)
            self.assertEqual(nodes, fallback)
            self.assertEqual(timestamp, cached_time)

    def test_first_api_failure_keeps_checks_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(
                node_state.urllib.request, "urlopen", side_effect=OSError
            ):
                nodes, fresh, timestamp = node_state.load_state(
                    "https://panel.invalid/api", "secret", Path(tmp) / "cache"
                )
        self.assertEqual((nodes, fresh, timestamp), ([], False, 0.0))

    def test_main_skips_disabled_without_emitting_failure(self):
        entries = [
            dict(host="192.0.2.1", remark="RENAMED · Vision", scheme="vless"),
            dict(host="192.0.2.2", remark="WORKING · Vision", scheme="vless"),
        ]
        nodes = [
            node_state.Node("a", "192.0.2.1", True),
            node_state.Node("b", "192.0.2.2", False),
        ]
        with (
            patch.object(probe, "fetch", return_value=0.1),
            patch.object(probe, "load_links", return_value=(["a", "b"], True)),
            patch.object(probe.sub2client, "parse_link", side_effect=entries),
            patch.object(probe, "load_state", return_value=(nodes, True, 123)),
            patch.object(probe, "probe", return_value=(3, 0.1)) as check,
            patch.object(probe, "through", return_value=100),
            patch.object(probe, "deliver", return_value=True) as deliver,
        ):
            probe.main()
        check.assert_called_once_with(entries[1])
        body = deliver.call_args.args[0]
        self.assertIn(
            'vpn_probe_host_enabled{host="RENAMED · Vision",'
            'node="RENAMED",transport="Vision"} 0',
            body,
        )
        self.assertNotIn('vpn_probe_success_ratio{host="RENAMED', body)
        self.assertIn('vpn_probe_success_ratio{host="WORKING', body)
        self.assertIn("vpn_probe_admin_state_fresh 1 ", body)
        self.assertIn("vpn_probe_disabled_hosts 1 ", body)


if __name__ == "__main__":
    unittest.main()
