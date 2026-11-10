"""Read administrative node state without treating an outage as maintenance."""

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Node:
    uuid: str
    address: str
    disabled: bool


def parse_nodes(payload: Any) -> list[Node]:
    rows = payload["response"]
    if isinstance(rows, dict):
        rows = rows["nodes"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Empty or invalid node response")
    nodes = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("isDisabled"), bool)
            or not isinstance(row.get("address"), str)
            or not isinstance(row.get("uuid"), str)
        ):
            raise ValueError("Invalid administrative state")
        nodes.append(Node(row["uuid"], row["address"], row["isDisabled"]))
    return nodes


def load_state(url: str, token: str, cache: Path) -> tuple[list[Node], bool, float]:
    """Cache only addresses, UUIDs and admin flags, never raw API configs or keys."""
    try:
        request = urllib.request.Request(
            url.rstrip("/") + "/nodes", headers={"Authorization": "Bearer " + token}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            nodes = parse_nodes(json.load(response))
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        try:
            cached = json.loads(cache.read_text())
            nodes = parse_nodes(
                {
                    "response": [
                        {
                            "uuid": row["uuid"],
                            "address": row["address"],
                            "isDisabled": row["disabled"],
                        }
                        for row in cached["nodes"]
                    ]
                }
            )
            return nodes, False, float(cached["fetched_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return [], False, 0.0
    fetched_at = time.time()
    temp = cache.with_suffix(".tmp")
    with open(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as out:
        json.dump({"nodes": [asdict(n) for n in nodes], "fetched_at": fetched_at}, out)
    os.replace(temp, cache)
    return nodes, True, fetched_at


def addresses(host: str) -> set[str]:
    try:
        return {str(ipaddress.ip_address(host))}
    except ValueError:
        try:
            return {
                str(ipaddress.ip_address(r[4][0]))
                for r in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            }
        except OSError:
            return set()


def enabled_entries(
    entries: list[dict[str, Any]], nodes: list[Node]
) -> tuple[list[bool], bool]:
    """Match endpoints, not display names; uncertain mappings must still be probed."""
    resolved = {
        host: addresses(host)
        for host in {n.address for n in nodes} | {e["host"] for e in entries}
    }
    flags = []
    known = True
    for entry in entries:
        matches = [
            n
            for n in nodes
            if n.address == entry["host"]
            or bool(resolved[n.address] & resolved[entry["host"]])
        ]
        # Shared addresses cannot establish which node owns a host's port.
        if len(matches) != 1:
            flags.append(True)
            known = False
        else:
            flags.append(not matches[0].disabled)
    return flags, known
