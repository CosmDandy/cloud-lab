#!/usr/bin/env python3
"""
Сводка боевого стенда: results/<дата>-prod/*.raw → SUMMARY.md.

Отдельно от сводки run-all.sh, потому что вопрос здесь другой. Там сравнивают
транспорты между собой на одной машине, здесь — ноды и протоколы на реальном
пути, и главная колонка не «сколько мегабит», а «сколько от прямого канала»:
без неё медленный протокол неотличим от медленного дня.
"""

import re
import sys
from pathlib import Path


def read_raw(path: Path) -> dict:
    data = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if re.fullmatch(r"[a-z_0-9]+", key):
                data[key] = value
    return data


def mbit(value: str | int | None) -> str:
    try:
        return f"{int(value) * 8 / 1_000_000:.1f}"
    except (TypeError, ValueError):
        return "—"


def share(value: str | None, base: int) -> str:
    try:
        if base <= 0:
            return "—"
        return f"{int(value) * 100 / base:.0f} %"
    except (TypeError, ValueError):
        return "—"


def node_of(remark: str) -> str:
    match = re.search(r"HHH-[A-Z]+", remark)
    return match.group(0) if match else "?"


def proto_of(remark: str) -> str:
    return remark.split("·", 1)[1].strip() if "·" in remark else remark


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

    rows = []
    for raw in sorted(out_dir.glob("*.raw")):
        if raw.name.startswith("baseline"):
            continue
        data = read_raw(raw)
        # Знаменатель лежит в самом замере: у каждой ноды он свой, и общий
        # столбец «от канала» без этого сравнивал бы Осло со стокгольмским.
        try:
            base = int(float(data.get("baseline_direct_bytes_s", 0)))
        except ValueError:
            base = 0
        remark = data.get("remark", raw.stem)
        handshake = dict(
            token.split("=", 1) for token in data.get("handshake_raw", "").split() if "=" in token
        )
        rows.append(
            {
                "node": node_of(remark),
                "proto": proto_of(remark),
                "status": data.get("status", "ok"),
                # Приёмник отвечает по http, поэтому time_appconnect всегда ноль;
                # смысл имеет TTFB — в него входит подъём туннеля.
                "ttfb": handshake.get("ttfb", "—"),
                "base": base,
                "dl": data.get("dl_avg_bytes_s"),
                "ul": data.get("ul_avg_bytes_s"),
                "fails": f"{data.get('dl_fails', '-')}/{data.get('ul_fails', '-')}",
                "parallel": data.get("parallel", "1"),
            }
        )

    rows.sort(key=lambda r: (r["node"], r["proto"]))

    bases = {r["node"]: r["base"] for r in rows if r.get("base")}
    lines = [f"# Боевой стенд — {out_dir.name}", ""]
    if bases:
        lines.append("Прямой канал до ноды, без туннеля — знаменатель колонки «от канала»:")
        lines.append("")
        for node, value in sorted(bases.items()):
            lines.append(f"- {node}: **{mbit(value)} Мбит/с**")
        lines.append("")
    lines += [
        "| Нода | Протокол | TTFB, с | DL Мбит/с | от канала | UL Мбит/с | сбои dl/ul |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] != "ok":
            lines.append(f"| {r['node']} | {r['proto']} | — | — | — | — | **{r['status']}** |")
            continue
        lines.append(
            f"| {r['node']} | {r['proto']} | {r['ttfb']} | **{mbit(r['dl'])}** | "
            f"{share(r['dl'], r['base'])} | {mbit(r['ul'])} | {r['fails']} |"
        )

    summary = out_dir / "SUMMARY.md"
    summary.write_text("\n".join(lines) + "\n")
    print(f"Сводка: {summary}")


if __name__ == "__main__":
    main()
