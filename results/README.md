# Included Results

This public snapshot includes three completed milestones:

- `benchmark-pilot-v1/`: five-task preliminary pipeline validation (15 runs)
- `benchmark-fresh15-v1/`: fresh locked 15-task comparison (45 full-trace runs)
- `benchmark-heldout40-v1/`: locked 40-task comparison (120 final results)

The held-out directory is the primary result of record. It contains exactly 40 task directories,
each with `single`, `retry`, and `contextrepair` final results, plus aggregate metrics, paired
statistics, condition summaries, ledgers, and ContextRepair failure-analysis artifacts.

The fresh-15 directory retains full public model/evaluator traces for auditability. To keep the
repository lightweight, the held-out release includes final results and analysis artifacts rather
than duplicating all 120 model-call transcripts and test logs. The complete held-out traces remain
in the local experiment archive. Local workspaces, repository mirrors, incomplete runs, smoke
tests, and duplicated execution roots are excluded.
