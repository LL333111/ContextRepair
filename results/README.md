# Included Results

This public snapshot includes only completed milestones:

- `benchmark-pilot-v1/`: five-task preliminary pipeline validation (15 runs)
- `benchmark-fresh15-v1/`: fresh locked 15-task comparison (45 runs)

The fresh-15 directory is the result of record. It contains exactly 15 task directories, each
with `single`, `retry`, and `contextrepair` final results, plus `analysis.json`. Local workspaces,
repository mirrors, incomplete regressions, smoke tests, duplicated parallel-run roots, and any
future larger held-out benchmark are intentionally excluded.

Raw artifacts retain public task statements, model prompts/responses, code excerpts, patches,
and evaluator output for auditability. Machine-specific paths have been replaced with public
placeholders in this release copy.
