#!/usr/bin/env python3
"""
TCP counters node-exporter leaves out, as a textfile.

node-exporter exports a fixed subset of /proc/net/netstat, and the interesting
half is not in it. These are the counters that answer "was the retransmit even
necessary" and "is recovery itself failing" — without them a tuning change like
raising tcp_reordering cannot be evaluated at all, only argued about.

Picked deliberately, not wholesale: the file has ~120 counters, most of which
never move on a proxy node.
"""

import os
import subprocess
import sys
import tempfile

# Счётчик -> (имя метрики, пояснение). Всё, что отсюда, — накопительные
# счётчики ядра с момента загрузки.
COUNTERS = {
    # Сколько повторов оказалось лишними: пакет дошёл, отправитель зря решил,
    # что он потерян. Прямая мера того, насколько TCP ошибается на этом пути.
    "TcpExtTCPDSACKRecv": ("tcp_dsack_received_total", "Retransmits the peer reported as unnecessary"),
    "TcpExtTCPDSACKOfoRecv": ("tcp_dsack_ofo_received_total", "Duplicates caused by reordering"),
    # Потерялся сам повторно отправленный пакет — признак тяжёлых потерь,
    # когда обычная доля ретрансмитов уже не отражает картину.
    "TcpExtTCPLostRetransmit": ("tcp_lost_retransmit_total", "Retransmitted segments that were lost again"),
    # Восстановления: сколько раз входили в recovery и сколько раз это не
    # помогло. Растущая доля Fail означает, что канал не тянет вовсе.
    "TcpExtTCPSackRecovery": ("tcp_sack_recovery_total", "Recovery episodes driven by SACK"),
    "TcpExtTCPSackRecoveryFail": ("tcp_sack_recovery_fail_total", "SACK recovery that did not succeed"),
    "TcpExtTCPRenoRecovery": ("tcp_reno_recovery_total", "Recovery without SACK"),
    # Ложные таймауты: RTO сработал, а данные были в пути. Лечится не так, как
    # настоящие потери, поэтому считается отдельно.
    "TcpExtTCPSpuriousRTOs": ("tcp_spurious_rto_total", "Timeouts that turned out to be premature"),
    "TcpExtTCPTimeouts": ("tcp_timeouts_total", "Retransmission timeouts"),
    # Tail loss probe: дешёвый способ не ждать RTO в конце потока.
    "TcpExtTCPLossProbes": ("tcp_loss_probes_total", "Tail loss probes sent"),
    "TcpExtTCPLossProbeRecovery": ("tcp_loss_probe_recovery_total", "Losses recovered by a tail probe"),
    # Очередь приёма переполнена — пакет отброшен уже на самой ноде.
    "TcpExtTCPRcvQDrop": ("tcp_rcv_queue_drops_total", "Segments dropped because the receive queue was full"),
    "TcpExtListenDrops": ("tcp_listen_drops_total", "Connections dropped from the accept queue"),
    "TcpExtListenOverflows": ("tcp_listen_overflows_total", "Accept queue overflows"),
}


def read_counters():
    try:
        out = subprocess.run(
            ["nstat", "-az"], capture_output=True, text=True, timeout=15, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"nstat failed: {exc}", file=sys.stderr)
        return {}

    values = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in COUNTERS:
            try:
                values[parts[0]] = int(parts[1])
            except ValueError:
                continue
    return values


def render(values):
    lines = []
    for raw, (metric, help_text) in COUNTERS.items():
        if raw not in values:
            continue
        lines += [
            f"# HELP node_{metric} {help_text}",
            f"# TYPE node_{metric} counter",
            f"node_{metric} {values[raw]}",
        ]
    lines.append("# HELP node_nstat_extra_up Whether nstat could be read")
    lines.append("# TYPE node_nstat_extra_up gauge")
    lines.append(f"node_nstat_extra_up {1 if values else 0}")
    return "\n".join(lines) + "\n"


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "/var/lib/node-exporter/textfile/nstat-extra.prom"
    body = render(read_counters())

    directory = os.path.dirname(target)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".nstat-extra-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except Exception:
        os.unlink(tmp)
        raise


if __name__ == "__main__":
    main()
