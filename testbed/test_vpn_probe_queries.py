"""Evaluate the actual dashboard queries against a disposable VictoriaMetrics.

Set VPN_QUERY_TEST_URL to an empty, disposable server, never production.
VPN_QUERY_TEST_DASHBOARD overrides the dashboard path when running remotely.
"""

import json
import os
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

URL = os.environ.get("VPN_QUERY_TEST_URL", "")
DASHBOARD = Path(
    os.environ.get(
        "VPN_QUERY_TEST_DASHBOARD",
        str(
            Path(__file__).resolve().parents[1]
            / "ansible/roles/observability/files/grafana/dashboards"
            / "network/vpn-traffic.json"
        ),
    )
)


@unittest.skipUnless(URL, "Requires a disposable VictoriaMetrics server")
class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panels = {p["id"]: p for p in json.loads(DASHBOARD.read_text())["panels"]}

    def setUp(self):
        self.now = int(time.time())
        self.transport = self._testMethodName

    def emit(self, node, success=None, enabled=None, timestamp=None):
        timestamp = self.now - 20 if timestamp is None else timestamp
        labels = (
            f'instance="fixture",host="{self.transport}-{node}",'
            f'node="{self.transport}-{node}",transport="{self.transport}"'
        )
        lines = []
        for name, value in [
            ("vpn_probe_success_ratio", success),
            ("vpn_probe_host_enabled", enabled),
        ]:
            if value is not None:
                lines.append(f"{name}{{{labels}}} {value} {timestamp * 1000}\n")
        request = urllib.request.Request(
            URL + "/api/v1/import/prometheus",
            data="".join(lines).encode(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
        with urllib.request.urlopen(
            URL + "/internal/force_flush", timeout=10
        ) as response:
            response.read()

    def query(self, panel_id, timestamp=None):
        query = self.panels[panel_id]["targets"][0]["expr"].replace(
            "$__interval", "10m"
        )
        params = urllib.parse.urlencode(
            {"query": query, "time": timestamp or self.now, "nocache": "1"}
        )
        with urllib.request.urlopen(
            URL + "/api/v1/query?" + params, timeout=10
        ) as response:
            data = json.load(response)
        self.assertEqual(data["status"], "success")
        return [
            r
            for r in data["data"]["result"]
            if r["metric"].get("transport") == self.transport
            or r["metric"].get("node", "").startswith(self.transport + "-")
        ]

    def test_disabled_node_does_not_make_transport_yellow(self):
        self.emit("enabled", success=1, enabled=1)
        self.emit("disabled", success=0, enabled=0)
        result = self.query(63)
        self.assertEqual([float(r["value"][1]) for r in result], [1.0])

    def test_offline_enabled_node_still_reduces_success(self):
        self.emit("working", success=1, enabled=1)
        self.emit("offline", success=0, enabled=1)
        self.assertEqual(float(self.query(63)[0]["value"][1]), 0.5)

    def test_disabled_matrix_cell_is_gray_sentinel_not_success(self):
        self.emit("disabled", success=0, enabled=0)
        self.assertEqual(float(self.query(64)[0]["value"][1]), -1.0)
        self.assertEqual(float(self.query(60)[0]["value"][1]), -1.0)
        for panel in [60, 64]:
            mapping = self.panels[panel]["fieldConfig"]["defaults"]["mappings"][0]
            self.assertEqual(mapping["options"]["-1"]["color"], "gray")

    def test_reenabled_node_with_failure_is_red(self):
        self.emit("reenabled", enabled=0, timestamp=self.now - 120)
        self.emit("reenabled", success=0, enabled=1)
        self.assertEqual(float(self.query(64)[0]["value"][1]), 0.0)
        self.assertEqual(float(self.query(63)[0]["value"][1]), 0.0)

    def test_historical_failures_are_not_rewritten_by_current_disable(self):
        self.emit("historical", success=0, timestamp=self.now - 3600)
        self.emit("historical", enabled=0)
        self.assertEqual(float(self.query(63, self.now - 3600)[0]["value"][1]), 0.0)
        self.assertEqual(self.query(63), [])

    def test_unknown_admin_state_does_not_hide_failure(self):
        self.emit("unknown", success=0)
        self.assertEqual(float(self.query(63)[0]["value"][1]), 0.0)

    def test_all_disabled_is_no_transport_data_not_false_green(self):
        self.emit("disabled", success=0, enabled=0)
        self.assertEqual(self.query(63), [])


if __name__ == "__main__":
    unittest.main()
