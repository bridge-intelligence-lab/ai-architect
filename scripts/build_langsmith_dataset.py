#!/usr/bin/env python3
"""Build/sync the `ai-architect-golden` LangSmith dataset (backlog LS-4b).

Reads eval/architect_prompts_v2.jsonl (source of truth, reviewed via
docs/eval_prompt_set_v2.md) and upserts one LangSmith example per prompt.

Idempotent: examples are keyed by the `id` field stored in example metadata.
Re-running updates changed examples in place, creates new ones, and deletes
examples whose id no longer appears in the jsonl.

Usage:
    LANGCHAIN_API_KEY=... python scripts/build_langsmith_dataset.py
    python scripts/build_langsmith_dataset.py --dry-run
    python scripts/build_langsmith_dataset.py --dataset my-test-dataset

Requires: pip install langsmith
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DATASET = "ai-architect-golden"
PROMPTS_FILE = Path(__file__).resolve().parent.parent / "eval" / "architect_prompts_v2.jsonl"

# Metadata keys copied onto each example; evaluators read these.
META_KEYS = ("id", "category", "expect_grounded", "expect_citations", "keywords", "expected_behavior")


def load_prompts(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_ids = set()
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "id" not in row or "question" not in row:
            raise ValueError(f"{path.name}:{lineno}: every row needs 'id' and 'question'")
        if row["id"] in seen_ids:
            raise ValueError(f"{path.name}:{lineno}: duplicate id {row['id']!r}")
        seen_ids.add(row["id"])
        rows.append(row)
    return rows


def to_example(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "inputs": {"question": row["question"]},
        "metadata": {k: row[k] for k in META_KEYS if k in row},
    }


def sync(dataset_name: str, rows: List[Dict[str, Any]], dry_run: bool) -> None:
    from langsmith import Client

    client = Client()

    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if datasets:
        dataset = datasets[0]
    elif dry_run:
        print(f"[dry-run] would create dataset {dataset_name!r}")
        for row in rows:
            print(f"[dry-run] would create example {row['id']}")
        return
    else:
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=(
                "Golden eval set for the Architect agent. Source of truth: "
                "eval/architect_prompts_v2.jsonl (see docs/eval_prompt_set_v2.md). "
                "Managed by scripts/build_langsmith_dataset.py; do not edit by hand."
            ),
        )
        print(f"created dataset {dataset_name!r} ({dataset.id})")

    existing = {}
    for ex in client.list_examples(dataset_id=dataset.id):
        ex_id = (ex.metadata or {}).get("id")
        if ex_id:
            existing[ex_id] = ex

    created = updated = unchanged = 0
    for row in rows:
        desired = to_example(row)
        current = existing.pop(row["id"], None)
        if current is None:
            if dry_run:
                print(f"[dry-run] would create {row['id']}")
            else:
                client.create_example(dataset_id=dataset.id, **desired)
            created += 1
        # LangSmith injects its own metadata keys (e.g. dataset_split), so
        # compare only the keys we manage.
        elif current.inputs != desired["inputs"] or {
            k: v for k, v in (current.metadata or {}).items() if k in META_KEYS
        } != desired["metadata"]:
            if dry_run:
                print(f"[dry-run] would update {row['id']}")
            else:
                client.update_example(example_id=current.id, **desired)
            updated += 1
        else:
            unchanged += 1

    deleted = 0
    for ex_id, ex in existing.items():
        if dry_run:
            print(f"[dry-run] would delete stale example {ex_id}")
        else:
            client.delete_example(example_id=ex.id)
        deleted += 1

    prefix = "[dry-run] " if dry_run else ""
    print(
        f"{prefix}{dataset_name}: {created} created, {updated} updated, "
        f"{unchanged} unchanged, {deleted} deleted ({len(rows)} total in source)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--file", type=Path, default=PROMPTS_FILE)
    parser.add_argument("--dry-run", action="store_true", help="print planned changes without touching LangSmith")
    args = parser.parse_args()

    if not args.dry_run and not os.getenv("LANGCHAIN_API_KEY"):
        print("LANGCHAIN_API_KEY is not set", file=sys.stderr)
        return 1

    rows = load_prompts(args.file)
    sync(args.dataset, rows, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
