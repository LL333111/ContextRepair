# ContextRepair Held-out 40 Results

## Scope

This report covers the completed held-out benchmark: 40 locked SWE-bench Verified tasks under
three conditions, for **120/120 completed task-condition runs**. The subset excludes every
five-task pilot and fresh-15 instance.

- Dataset: `SWE-bench/SWE-bench_Verified`
- Model: `deepseek-v4-flash`, temperature 0
- Locked subset: `benchmark_subsets/heldout40.json`
- Seed: 47
- Subset checksum: `1efc1c75bcdf286a9fcd579d05fc8375abfbf34952cccfbfa0325a960516f626`
- Combined artifacts: `results/benchmark-heldout40-v1/`
- Aggregate metrics: `analysis.json`
- Paired statistics: `statistics.json`

## Results

| Condition | Resolved | Recovery | Avg tokens/task | Cost/task | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|
| Single | 22/40 (55.0%) | — | 91,975 | $0.0480 | 39.8–69.3% |
| Independent Retry | 21/40 (52.5%) | 3/22 (13.6%) | 133,464 | $0.0666 | 37.5–67.1% |
| ContextRepair | 22/40 (55.0%) | 1/19 (5.3%) | 135,692 | $0.0680 | 39.8–69.3% |

The primary paired comparison contains two ContextRepair-only successes, one Retry-only
success, 20 joint successes, and 17 joint failures. ContextRepair's observed difference is
**+2.5 percentage points**, but the two-sided exact McNemar test gives **p = 1.0**. The result
does not support an improvement claim.

ContextRepair used 1.7% more tokens and 2.1% more completed-run cost per task than Retry. Its
recovery stage fixed one of 19 initial failures, while independent Retry fixed three of 22.
The equal 55.0% final rate for Single and ContextRepair also shows that final resolution alone
does not establish a mechanism benefit on this sample.

## Usage and cost

The 120 completed runs used 14,445,242 tokens and $7.3056 in completed-run cost. One interrupted
Retry call added $0.0099, so total charged held-out cost was **$7.3154**, below the combined
$8.90 condition caps. Together with the fresh-15 milestone, cumulative charged formal
evaluation cost was approximately **$10.1559**, below the $12 project ceiling.

## Operational disclosures

Two general runner fixes were made after held-out execution began; neither changed the model,
agent logic, prompts, task set, token budgets, or official 30-minute evaluation rule:

1. The fifth task on the concurrently running Single and Retry lines encountered 334
   rebuildable third-party `.eggs` cache artifacts before any model call. The artifact seeding
   filter was extended to omit `.eggs`, then both lines resumed.
2. Retry task 26 issued a broad host-side `rg` search that exceeded 60 seconds. The shell tool
   was changed to return an actionable timeout result so the agent could narrow its query. The
   interrupted partial call cost $0.00988152 and is included above.

A separate zero-cost launcher permission failure occurred before the first ContextRepair model
call; the same frozen command was relaunched with host Docker access. No prompt, configuration,
or result was reused from that empty partial.

## Interpretation

The system and evaluation pipeline are complete and auditable, but the research result remains
non-significant. ContextRepair matched Single and exceeded Retry by one task, while using
slightly more tokens than Retry and recovering fewer initial failures. This is a useful
engineering and evaluation result, not evidence that failure-conditioned re-exploration
generally improves coding-agent resolution.
