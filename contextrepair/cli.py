from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from contextrepair.agent.controller import ExperimentController
from contextrepair.config import load_config
from contextrepair.evaluation.metrics import aggregate_results
from contextrepair.evaluation.subsets import load_locked_subset, lock_subset
from contextrepair.evaluation.swebench import SWEbenchAdapter, load_prepared_tasks
from contextrepair.run_state import (
    archive_partial_task,
    atomic_write_json,
    consumed_cost_usd,
    load_completed_result,
    worst_case_task_cost_usd,
    write_run_ledger,
)
from contextrepair.types import Task


def _task_from_dict(value: dict) -> Task:
    return Task(
        instance_id=str(value["instance_id"]),
        issue=str(value["issue"]),
        repo_path=Path(value["repo_path"]),
        test_command=str(value["test_command"]),
        base_commit=value.get("base_commit"),
        metadata=dict(value.get("metadata", {})),
    )


def _resolve_task(task: str, tasks_file: str | None) -> Task:
    candidate = Path(task)
    if candidate.is_file():
        return _task_from_dict(json.loads(candidate.read_text(encoding="utf-8")))
    if not tasks_file:
        default = Path("tasks") / f"{task}.json"
        if default.is_file():
            return _task_from_dict(json.loads(default.read_text(encoding="utf-8")))
        raise SystemExit("--task must be a descriptor JSON path, or use --tasks-file with an ID")
    matches = load_prepared_tasks(tasks_file, {task})
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one descriptor for {task!r}; found {len(matches)}")
    return _task_from_dict(matches[0])


def run_command(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    task = _resolve_task(args.task, args.tasks_file)
    result = ExperimentController(config, Path(args.results)).run(task)
    print(json.dumps(result, indent=2))
    return 0 if result["resolved"] else 1


def benchmark_command(args: argparse.Namespace) -> int:
    config_path = args.config or str(Path("configs") / f"{args.condition}.yaml")
    config = load_config(config_path)
    if config.condition != args.condition:
        raise SystemExit(
            f"Config condition {config.condition!r} does not match --condition {args.condition!r}"
        )
    ids = set(load_locked_subset(args.subset))
    tasks = load_prepared_tasks(args.tasks_file, ids)
    task_ids = [item["instance_id"] for item in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise SystemExit("Prepared task descriptors contain duplicate instance IDs")
    missing = ids - {item["instance_id"] for item in tasks}
    if missing:
        raise SystemExit(f"Prepared task descriptors missing {len(missing)} instances")
    results = []
    for item in sorted(tasks, key=lambda value: value["instance_id"]):
        instance_id = str(item["instance_id"])
        completed = load_completed_result(args.results, instance_id, args.condition)
        if completed is not None:
            results.append(completed)
            continue

        archive_partial_task(args.results, instance_id, args.condition)
        consumed, _, _ = consumed_cost_usd(args.results)
        reserve = worst_case_task_cost_usd(config)
        if (
            args.max_total_cost_usd is not None
            and consumed + reserve > args.max_total_cost_usd
        ):
            ledger = write_run_ledger(
                args.results,
                max_total_cost_usd=args.max_total_cost_usd,
                status="budget_stopped",
                current_task=instance_id,
                error=(
                    f"Starting the next task could exceed the global cost cap; "
                    f"consumed=${consumed:.6f}, reserve=${reserve:.6f}"
                ),
            )
            print(json.dumps(ledger, indent=2))
            return 2

        # A fresh controller gives each task an identical independent budget.
        result = None
        for attempt in range(args.task_retries + 1):
            write_run_ledger(
                args.results,
                max_total_cost_usd=args.max_total_cost_usd,
                status="running",
                current_task=instance_id,
            )
            try:
                result = ExperimentController(config, Path(args.results)).run(
                    _task_from_dict(item)
                )
                break
            except KeyboardInterrupt:
                write_run_ledger(
                    args.results,
                    max_total_cost_usd=args.max_total_cost_usd,
                    status="interrupted",
                    current_task=instance_id,
                )
                raise
            except Exception as exc:
                write_run_ledger(
                    args.results,
                    max_total_cost_usd=args.max_total_cost_usd,
                    status="retrying" if attempt < args.task_retries else "failed",
                    current_task=instance_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
                if attempt >= args.task_retries:
                    raise
                archive_partial_task(args.results, instance_id, args.condition)
                time.sleep(min(30, 2**attempt))
        if result is None:  # Defensive; the loop either returns a result or raises.
            raise RuntimeError(f"Task produced no result: {instance_id}")
        results.append(result)
        incremental = aggregate_results(results)
        output = Path(args.results) / f"summary_{args.condition}.json"
        atomic_write_json(output, incremental)
        write_run_ledger(
            args.results,
            max_total_cost_usd=args.max_total_cost_usd,
            status="running",
        )
    summary = aggregate_results(results)
    output = Path(args.results) / f"summary_{args.condition}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output, summary)
    write_run_ledger(
        args.results,
        max_total_cost_usd=args.max_total_cost_usd,
        status="complete",
    )
    print(json.dumps(summary, indent=2))
    return 0


def analyze_command(args: argparse.Namespace) -> int:
    root = Path(args.results)
    summaries: dict[str, dict] = {}
    for condition in ("single", "retry", "contextrepair"):
        values = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in root.glob(f"*/{condition}/final_result.json")
        ]
        if values:
            summaries[condition] = aggregate_results(values)
    recovery_paths = list(root.glob("*/contextrepair/recovery_analysis.json"))
    if recovery_paths:
        categories = Counter()
        delta_by_outcome: dict[str, list[int]] = {"recovered": [], "not_recovered": []}
        for analysis_path in recovery_paths:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            categories[str(analysis.get("failure_type", "unknown"))] += 1
            result = json.loads(
                (analysis_path.parent / "final_result.json").read_text(encoding="utf-8")
            )
            delta_path = analysis_path.parent / "context_delta.json"
            new_files = 0
            if delta_path.exists():
                delta = json.loads(delta_path.read_text(encoding="utf-8"))
                new_files = len(delta.get("new_files", []))
            key = "recovered" if result.get("recovered") else "not_recovered"
            delta_by_outcome[key].append(new_files)
        summaries["failure_analysis"] = {
            "failure_type_counts": dict(sorted(categories.items())),
            "avg_new_files": {
                key: (sum(values) / len(values) if values else None)
                for key, values in delta_by_outcome.items()
            },
        }
    output = root / "analysis.json"
    output.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(json.dumps(summaries, indent=2))
    return 0


def lock_subset_command(args: argparse.Namespace) -> int:
    universe = [
        line.strip()
        for line in Path(args.instances).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    payload = lock_subset(
        args.output, universe, size=args.size, seed=args.seed, source=args.source
    )
    print(json.dumps(payload, indent=2))
    return 0


def evaluate_command(args: argparse.Namespace) -> int:
    adapter = SWEbenchAdapter()
    predictions = adapter.predictions(
        Path(args.results), args.condition, Path(args.predictions), args.model_name
    )
    if args.prepare_only:
        print(predictions)
        return 0
    completed = adapter.run_official_evaluator(
        predictions,
        dataset_name=args.dataset,
        run_id=args.run_id,
        max_workers=args.max_workers,
    )
    evaluator_log = Path(args.results) / f"evaluator_{args.condition}_{args.run_id}.log"
    evaluator_log.parent.mkdir(parents=True, exist_ok=True)
    evaluator_log.write_text(
        f"exit_code={completed.returncode}\n\nSTDOUT\n{completed.stdout}\n\nSTDERR\n{completed.stderr}",
        encoding="utf-8",
    )
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contextrepair")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run one prepared repository task")
    run.add_argument("--task", required=True)
    run.add_argument("--config", required=True)
    run.add_argument("--tasks-file")
    run.add_argument("--results", default="results")
    run.set_defaults(handler=run_command)

    benchmark = subparsers.add_parser("benchmark", help="run a locked prepared subset")
    benchmark.add_argument("--subset", required=True)
    benchmark.add_argument("--condition", choices=["single", "retry", "contextrepair"], required=True)
    benchmark.add_argument("--tasks-file", required=True)
    benchmark.add_argument("--config")
    benchmark.add_argument("--results", default="results")
    benchmark.add_argument(
        "--max-total-cost-usd",
        type=float,
        help="shared hard cost cap across completed and interrupted runs in --results",
    )
    benchmark.add_argument(
        "--task-retries",
        type=int,
        default=2,
        help="automatic retries after transient task failures (default: 2)",
    )
    benchmark.set_defaults(handler=benchmark_command)

    analyze = subparsers.add_parser("analyze", help="aggregate completed task results")
    analyze.add_argument("--results", default="results")
    analyze.set_defaults(handler=analyze_command)

    subset = subparsers.add_parser("lock-subset", help="deterministically create an immutable subset")
    subset.add_argument("--instances", required=True, help="text file containing one instance ID per line")
    subset.add_argument("--output", required=True)
    subset.add_argument("--size", required=True, type=int)
    subset.add_argument("--seed", type=int, default=0)
    subset.add_argument("--source", default="princeton-nlp/SWE-bench_Verified")
    subset.set_defaults(handler=lock_subset_command)

    evaluate = subparsers.add_parser("evaluate", help="invoke the official SWE-bench evaluator")
    evaluate.add_argument("--results", default="results")
    evaluate.add_argument("--condition", choices=["single", "retry", "contextrepair"], required=True)
    evaluate.add_argument("--predictions", required=True)
    evaluate.add_argument("--model-name", required=True)
    evaluate.add_argument("--run-id", default="contextrepair")
    evaluate.add_argument("--dataset", default="SWE-bench/SWE-bench_Verified")
    evaluate.add_argument("--max-workers", type=int, default=4)
    evaluate.add_argument("--prepare-only", action="store_true")
    evaluate.set_defaults(handler=evaluate_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
