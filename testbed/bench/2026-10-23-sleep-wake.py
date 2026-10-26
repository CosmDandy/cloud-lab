"""Sleep/wake bench: time from wake to the first request that gets through.

Models a laptop waking on a network where its old flows are gone: the router drops
packets of unknown flows silently, new flows pass. For each variant: start xray,
warm the transport, idle, "sleep" (SIGSTOP xray, then iptables DROP on the local
ports of every socket xray holds to the node), wake (SIGCONT) and retry a fresh
request every 0.5 s with a 4 s timeout until one succeeds or 120 s pass.

    python3 2026-10-23-sleep-wake.py <variant,...> <reps> <idle_s>

Runs as root on the office testbed (iptables), with the configs from
2026-10-23-sleep-wake-configs.py in ./out next to it; delete ./out afterwards.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
XRAY = "/usr/local/bin/xray"
NODE = "167.104.104.131"
URL = "https://www.gstatic.com/generate_204"
CHAIN = "XMUXLAB"
OUT = os.path.join(D, "results.jsonl")


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def chain_reset():
    for hook in ("OUTPUT", "INPUT"):
        while sh("iptables", "-D", hook, "-j", CHAIN).returncode == 0:
            pass
    sh("iptables", "-F", CHAIN)
    sh("iptables", "-X", CHAIN)


def blackhole(pid):
    """DROP both directions of every socket the xray process holds to the node."""
    sh("iptables", "-N", CHAIN)
    sh("iptables", "-I", "OUTPUT", "-j", CHAIN)
    sh("iptables", "-I", "INPUT", "-j", CHAIN)
    ports = []
    # NOTE: quic-go uses an unconnected UDP socket, so its peer is *:* and a
    # `dst` filter would miss it; every UDP socket of the process is taken.
    for proto, flt in (("t", ["dst", NODE]), ("u", [])):
        out = sh("ss", f"-H{proto}anp", *flt).stdout
        for line in out.splitlines():
            if f"pid={pid}," not in line:
                continue
            port = re.search(r":(\d+)$", line.split()[3]).group(1)
            p = "tcp" if proto == "t" else "udp"
            ports.append(f"{p}/{port}")
            sh(
                "iptables",
                "-A",
                CHAIN,
                "-p",
                p,
                "-d",
                NODE,
                "--sport",
                port,
                "-j",
                "DROP",
            )
            sh(
                "iptables",
                "-A",
                CHAIN,
                "-p",
                p,
                "-s",
                NODE,
                "--dport",
                port,
                "-j",
                "DROP",
            )
    return ports


def curl(port, timeout=4):
    t = time.monotonic()
    r = sh(
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "-m",
        str(timeout),
        "-x",
        f"socks5h://127.0.0.1:{port}",
        URL,
    )
    return r.stdout.strip() == "204", time.monotonic() - t


def run(name, rep, idle):
    cfg = os.path.join(D, "out", name + ".json")
    port = json.load(open(cfg))["inbounds"][0]["port"]
    log = open(os.path.join(D, f"xray-{name}.log"), "a")
    x = subprocess.Popen([XRAY, "run", "-config", cfg], stdout=log, stderr=log)
    time.sleep(1.5)
    res = {"variant": name, "rep": rep, "idle": idle}
    try:
        warm = [curl(port, 10) for _ in range(3)]
        res["warm_ok"] = all(ok for ok, _ in warm)
        res["warm_s"] = round(max(t for _, t in warm), 2)
        if not res["warm_ok"]:
            return res
        time.sleep(idle)
        x.send_signal(signal.SIGSTOP)
        res["dropped"] = blackhole(x.pid)
        time.sleep(2)
        x.send_signal(signal.SIGCONT)
        t0 = time.monotonic()
        fails = 0
        while time.monotonic() - t0 < 120:
            ok, _ = curl(port)
            if ok:
                res["wake_s"] = round(time.monotonic() - t0, 1)
                break
            fails += 1
            time.sleep(0.5)
        res["fails"] = fails
        res["after_ok"] = sum(curl(port)[0] for _ in range(3))
        return res
    finally:
        x.kill()
        x.wait()
        chain_reset()


def main():
    variants, reps, idle = sys.argv[1].split(","), int(sys.argv[2]), float(sys.argv[3])
    chain_reset()
    for rep in range(1, reps + 1):
        for name in variants:
            r = run(name, rep, idle)
            print(json.dumps(r), flush=True)
            with open(OUT, "a") as f:
                f.write(json.dumps(r) + "\n")
    print("done", flush=True)


if __name__ == "__main__":
    main()
