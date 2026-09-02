# ContextRepair Experimental Report

## Status

A fresh locked 15-task comparison completed on 2026-09-02 after the five-task pipeline pilot.
It contains 45 complete task-condition runs with no partial result files. The result is a
pilot-scale matched-task benchmark, but remains too small for a broad performance claim.

- Benchmark: `SWE-bench/SWE-bench_Verified`
- Subset size and seed: 15 tasks, seed 31; all five pilot tasks excluded
- Subset checksum: `808a76c2069da69a57e858ad372e9b15ad5d184eec4910cd8f0d507008160d42`
- Model: `deepseek-v4-flash`, temperature 0, thinking enabled
- Conditions: single, independent retry, ContextRepair
- Pricing used for the conservative estimate: $0.44/M input tokens and $1.32/M output tokens
- Raw combined artifacts: `results/benchmark-fresh15-v1/`
- Aggregate analysis: `results/benchmark-fresh15-v1/analysis.json`

Conditions and the final ContextRepair shards ran concurrently in isolated result roots to
reduce elapsed time. They used separate workspaces and containers with unchanged task prompts,
budgets, model settings, and evaluator commands. Artifacts were copied into the combined root
after completion. Scheduling therefore must not be used for a cross-condition throughput claim.

## Research questions

1. Does ContextRepair improve SWE-bench Verified resolution over an independent retry under the same total inference-token ceiling?
2. Does failure-conditioned re-exploration find new ground-truth relevant repository context?
3. What token and monetary overhead is required per recovered issue?

## Locked design

- Primary benchmark: SWE-bench Verified.
- Mechanism benchmark: SWE-Explore or a named equivalent with file/line annotations.
- Conditions: SINGLE, RETRY, CONTEXTREPAIR.
- Recovery cycles: one.
- Primary endpoint: official Resolved %.
- Primary control: RETRY versus CONTEXTREPAIR.
- Required ablation: remove execution evidence.
- Matching variables: model/version, temperature, task IDs, environment images, evaluator, max attempts, and total inference-token ceiling.

Record the final subset checksum, dataset revisions, model version, prices, container images, source commit, and start date here before launching the final run.

## Main results

| Method | Resolved | Recovery | Avg input tokens | Avg output tokens | Cost / task |
|---|---:|---:|---:|---:|---:|
| SINGLE | 5/15 (33.3%) | — | 81,627 | 8,156 | $0.0467 |
| RETRY | 9/15 (60.0%) | 2/8 (25.0%) | 122,452 | 9,982 | $0.0671 |
| CONTEXTREPAIR | 8/15 (53.3%) | 2/9 (22.2%) | 137,310 | 10,140 | $0.0738 |

| Instance | SINGLE | RETRY | CONTEXTREPAIR |
|---|---:|---:|---:|
| `astropy__astropy-13977` | Fail | Fail | Fail |
| `django__django-10097` | Fail | Fail | Fail |
| `django__django-11740` | Fail | Pass | Fail |
| `django__django-12143` | Pass | Fail | Pass |
| `django__django-12155` | Pass | Pass | Pass |
| `django__django-12262` | Pass | Pass | Pass |
| `django__django-13568` | Fail | Pass | Pass |
| `django__django-15732` | Fail | Fail | Fail |
| `django__django-16877` | Pass | Pass | Pass |
| `matplotlib__matplotlib-25311` | Fail | Fail | Fail |
| `scikit-learn__scikit-learn-11578` | Fail | Pass | Pass |
| `scikit-learn__scikit-learn-14496` | Fail | Pass | Pass |
| `sphinx-doc__sphinx-7454` | Fail | Pass | Fail |
| `sphinx-doc__sphinx-7889` | Pass | Pass | Pass |
| `sympy__sympy-23413` | Fail | Fail | Fail |

The 45 completed runs used 5,120,827 input tokens and 424,174 output tokens, for 5,545,001
total tokens and $2.8131. One interrupted ContextRepair call used while splitting the remaining
work added $0.0274, making total charged experiment cost $2.8405. ContextRepair recovered two
initial failures, but independent retry resolved one more task overall. ContextRepair consumed
11.3% more tokens and 10.1% more cost per task than Retry.

The paired Retry-versus-ContextRepair table contains one ContextRepair-only success, two
Retry-only successes, seven joint successes, and five joint failures. The paired difference is
-6.7 percentage points; the two-sided exact McNemar test gives p=1.0. Wilson 95% intervals for
the unpaired descriptive rates are approximately 15.2–58.3% (Single), 35.7–80.2% (Retry), and
30.1–75.2% (ContextRepair). These wide intervals prohibit a general improvement claim.

## Mechanism observations

| Metric | Initial | After re-exploration | Difference |
|---|---:|---:|---:|

The fresh run generated nine recovery analyses: three `incomplete_fix`, three
`incorrect_causal_hypothesis`, two `missing_cross_file_dependency`, and one
`environment_test_failure`. Two cases recovered. Recovered cases admitted 3.5 new files on
average versus 3.29 for non-recovered cases. This is descriptive, not relevant-file recall;
ground-truth SWE-Explore annotations are still required for the preregistered mechanism metrics.
Ground-truth localization metrics and execution-evidence ablations remain future work because this benchmark did not include a pinned SWE-Explore annotation release.

## Ablations

| Condition | Resolved % | Recovery % | Localization delta | Avg tokens |
|---|---:|---:|---:|---:|

## Failure analysis protocol

Sample approximately 20 failed tasks before reading outcomes for qualitative selection. Assign one primary category and optional secondary category:

- localization failure
- missing dependency
- incorrect hypothesis
- correct localization / bad implementation
- incomplete multi-file fix
- regression
- environment/test problem
- context budget exhaustion

Record counts, representative trajectories, whether new relevant context was found, and why repair still failed. Include at least one detailed ContextRepair failure alongside any successful case study.

## Evidence gates

- M1: **met** — real-model trajectories, patches, provider usage, and executed tests are saved.
- M2: **met** — 15 fresh public tasks completed in all three conditions after a separate pilot.
- M3–M5: **met for system execution** — complete recovery loops, typed failure analyses,
  new-only deltas, and two recoveries are included; extended case studies are future work.
- M6: **not met** — no standardized localization annotation run has completed.
- M7: **not met** — no frozen held-out 50-task subset has completed.
- M8: **met at pilot scale, not publication scale** — the frozen fresh-15 benchmark completed;
  a larger budget-bounded held-out run is future work.

Every performance claim in this release points to its exact output file and evaluator run.
Engineering claims describe implemented and verified infrastructure without implying an
unsupported resolution-rate improvement.


