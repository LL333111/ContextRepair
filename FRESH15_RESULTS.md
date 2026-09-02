# ContextRepair Fresh-15 Results

## Scope

This snapshot reports the completed fresh-15 milestone. The task set was locked before the
formal comparison, excludes all five preliminary-pilot tasks, and contains 15 public
SWE-bench Verified instances evaluated under three conditions (45 completed runs total).

- Dataset: `SWE-bench/SWE-bench_Verified`
- Model: `deepseek-v4-flash`, temperature 0
- Locked subset: `benchmark_subsets/fresh15.json`
- Seed: 31
- SHA-256: `808a76c2069da69a57e858ad372e9b15ad5d184eec4910cd8f0d507008160d42`
- Aggregate artifact: `results/benchmark-fresh15-v1/analysis.json`
- Completion: 45/45 task-condition runs; no partial result files

## Research question

Does a failure-conditioned recovery pipeline outperform a fresh independent retry when model,
tasks, maximum attempts, evaluator, and total inference budget are controlled?

ContextRepair converts the first attempt's trajectory, patch, and test evidence into a typed
failure analysis, performs targeted repository re-exploration, admits a bounded delta of new
context, and runs one recovery attempt. The primary control is an independent second attempt
with no structured failure analysis or context delta.

## Results

| Condition | Resolved | Recovery | Avg tokens/task | Cost/task | Cost/resolved |
|---|---:|---:|---:|---:|---:|
| Single | 5/15 (33.3%) | — | 89,782 | $0.0467 | $0.1400 |
| Independent Retry | 9/15 (60.0%) | 2/8 (25.0%) | 132,434 | $0.0671 | $0.1118 |
| ContextRepair | 8/15 (53.3%) | 2/9 (22.2%) | 147,450 | $0.0738 | $0.1384 |

The Retry-versus-ContextRepair paired table contains one ContextRepair-only success, two
Retry-only successes, seven joint successes, and five joint failures. ContextRepair's paired
difference is -6.7 percentage points. The two-sided exact McNemar test gives `p = 1.0`.
Descriptive Wilson 95% intervals are approximately 15.2–58.3% for Single, 35.7–80.2% for
Retry, and 30.1–75.2% for ContextRepair.

ContextRepair used 11.3% more tokens and 10.1% more cost per task than Retry while resolving
one fewer task. The observed result therefore does not support an improvement claim.

## Usage and cost

The 45 completed runs used 5,120,827 input tokens and 424,174 output tokens (5,545,001 total)
for $2.8131. One interrupted call used while splitting the final ContextRepair work across two
workers added $0.0274, making total charged milestone cost $2.8405. The split did not change
task prompts, configs, model settings, token ceilings, or evaluator commands.

## Failure analysis

Nine ContextRepair initial failures received structured analyses:

- `incomplete_fix`: 3
- `incorrect_causal_hypothesis`: 3
- `missing_cross_file_dependency`: 2
- `environment_test_failure`: 1

Two recovered. Recovered cases admitted 3.5 new files on average versus 3.29 for
non-recovered cases. This is descriptive context expansion, not ground-truth localization
recall; a pinned localization annotation release is still required for that mechanism claim.

## Interpretation

The engineering hypothesis was plausible, but under this model and budget a simpler retry was
more accurate and more cost-efficient. The milestone is a reproducible negative result: it
demonstrates a complete coding-agent recovery implementation and a controlled evaluation while
avoiding an unsupported uplift claim.

This is a controlled engineering benchmark, not a publication-scale performance claim: 15 tasks
produce wide uncertainty intervals, and the primary method did not beat its strongest control.

## Reproduction and audit trail

- `results/benchmark-fresh15-v1/<instance>/<condition>/final_result.json` contains the outcome
  of record for each run.
- `model_calls.json`, trajectories, patches, and test logs retain the model and execution audit
  trail.
- `analysis.json` contains the aggregate metrics.
- `configs/` contains the frozen inference and recovery budgets.
- `scripts/prepare_swebench_tasks.py` reconstructs descriptors from the public dataset and
  locked subset; local prepared mirrors are intentionally excluded from the release.
