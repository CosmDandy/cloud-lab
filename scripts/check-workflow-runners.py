#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Self-hosted раннер разрешён только на workflow_dispatch.

Раннер стоит на нашей же машине, а репозиторий публичный. Единственное, что
не пускает к нему постороннего, — то, что все ходящие на него workflow
объявлены через workflow_dispatch, а его может дёрнуть лишь обладатель
write-доступа. Стоит однажды дописать `pull_request` рядом с
`runs-on: hcloud-*` — и любой форк получит выполнение кода на control-plane.

Проверка существует потому, что эта договорённость иначе ничем не закреплена.
zizmor её не ловит: он ищет литеральную метку `self-hosted`, а метки здесь
именуются по хосту (`hcloud-htz-hel-01`).

Запуск: uv run scripts/check-workflow-runners.py
"""

import pathlib
import sys

import yaml

# Всё, что не начинается с этого, считается своим раннером. Направление
# ошибки выбрано намеренно: новая метка облачного раннера будет помечена
# лишней тревогой, а свой раннер не проскочит молча.
GITHUB_HOSTED_PREFIXES = ("ubuntu-", "windows-", "macos-")

ALLOWED_TRIGGERS = {"workflow_dispatch"}

WORKFLOW_DIR = pathlib.Path(".github/workflows")


def triggers_of(doc):
    # PyYAML разбирает ключ `on:` по правилам YAML 1.1, где это булево, —
    # документ приходит с ключом True, а не "on". Без этой строки проверка
    # молча не находит ни одного триггера и всегда зелёная.
    on = doc.get("on", doc.get(True))
    if isinstance(on, dict):
        return set(on)
    if isinstance(on, str):
        return {on}
    return set(on or [])


def labels_of(runs_on):
    if isinstance(runs_on, dict):  # форма {group: ..., labels: [...]}
        labels = runs_on.get("labels", [])
        return labels if isinstance(labels, list) else [labels]
    if isinstance(runs_on, list):
        return runs_on
    return [runs_on] if runs_on else []


def main():
    problems = []
    workflows = sorted(
        [*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")]
    )
    if not workflows:
        print(f"не найдено ни одного workflow в {WORKFLOW_DIR}", file=sys.stderr)
        return 1

    for path in workflows:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        triggers = triggers_of(doc)
        extra = triggers - ALLOWED_TRIGGERS
        if not extra:
            continue

        for job_name, job in (doc.get("jobs") or {}).items():
            own = [
                label
                for label in labels_of((job or {}).get("runs-on"))
                if not str(label).startswith(GITHUB_HOSTED_PREFIXES)
            ]
            if own:
                problems.append(
                    f"{path}: job «{job_name}» идёт на свой раннер {own}, "
                    f"а workflow запускается ещё и по {sorted(extra)}"
                )

    for line in problems:
        print(line)

    if problems:
        print(
            f"\nНайдено нарушений: {len(problems)}. Свой раннер стоит на нашей "
            "машине, а репозиторий публичный: всё, что запускается не только "
            "по workflow_dispatch, обязано идти на раннер GitHub.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: проверено workflow — {len(workflows)}, нарушений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
