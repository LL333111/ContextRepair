# ContextRepair Experimental Report

## Status

A locked 40-task held-out comparison completed on 2026-09-02 after the five-task pilot and
fresh-15 milestone. It contains 120 complete task-condition runs with no partial results in the
combined root. This is a substantial engineering-portfolio benchmark, but not a broad model or
publication-scale claim.

- Benchmark: `SWE-bench/SWE-bench_Verified`
- Subset size and seed: 40 tasks, seed 47; all pilot and fresh-15 tasks excluded
- Subset checksum: `1efc1c75bcdf286a9fcd579d05fc8375abfbf34952cccfbfa0325a960516f626`
- Model: `deepseek-v4-flash`, temperature 0, thinking enabled
- Conditions: single, independent retry, ContextRepair
- Pricing used for the conservative estimate: $0.44/M input tokens and $1.32/M output tokens
- Raw combined artifacts: `results/benchmark-heldout40-v1/`
- Aggregate analysis: `results/benchmark-heldout40-v1/analysis.json`
- Paired statistics: `results/benchmark-heldout40-v1/statistics.json`

Single and Retry ran concurrently in isolated result roots; ContextRepair ran afterward under
the same frozen task and inference contract. All conditions used separate workspaces and
containers with unchanged prompts, budgets, model settings, and evaluator commands. Artifacts
were copied into the combined root after completion. Scheduling is not used for a throughput
claim.

## Execution integrity disclosures

Two general runner fixes were made after held-out execution began. Neither changed the model,
agent logic, prompts, task set, token budgets, or official 30-minute evaluation rule:

1. The fifth task on the Single and Retry lines encountered 334 rebuildable third-party
   `.eggs` cache artifacts before any model call. The artifact-seeding filter was extended to
   omit `.eggs`, then both lines resumed.
2. Retry task 26 issued a broad host-side `rg` query that exceeded 60 seconds. The shell tool
   was changed to return an actionable timeout result so the agent could narrow the query. The
   interrupted partial call cost $0.00988152 and is included in charged cost.

A zero-cost launcher permission failure also occurred before the first ContextRepair model call;
the frozen command was relaunched with host Docker access. It produced no model call or result.

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

The final subset checksum, model settings, prices, task metadata, container images, and run
timestamps are retained in the locked subset and per-task artifacts.

## Main results

| Method | Resolved | Recovery | Avg input tokens | Avg output tokens | Cost / task | Wilson 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| SINGLE | 22/40 (55.0%) | — | 83,412 | 8,563 | $0.0480 | 39.8–69.3% |
| RETRY | 21/40 (52.5%) | 3/22 (13.6%) | 124,484 | 8,980 | $0.0666 | 37.5–67.1% |
| CONTEXTREPAIR | 22/40 (55.0%) | 1/19 (5.3%) | 126,256 | 9,436 | $0.0680 | 39.8–69.3% |

The 120 completed runs used 14,445,242 tokens and $7.3056. One interrupted Retry call added
$0.0099, making total charged held-out cost $7.3154. ContextRepair used 1.7% more tokens and
2.1% more completed-run cost per task than Retry.

The primary paired Retry-versus-ContextRepair table contains two ContextRepair-only successes,
one Retry-only success, 20 joint successes, and 17 joint failures. The observed difference is
+2.5 percentage points; the two-sided exact McNemar test gives p=1.0. ContextRepair and Single
both resolved 22 tasks, with one discordant success in each direction. These results do not
support a resolution-uplift or mechanism-improvement claim.

## Mechanism results

| Metric | Initial | After re-exploration | Difference |
|---|---:|---:|---:|
| Relevant-file recall | PENDING | PENDING | PENDING |
| Relevant-line coverage | PENDING | PENDING | PENDING |
| Relevant context / 1K tokens | PENDING | PENDING | PENDING |

The held-out run generated 19 recovery analyses: five `incorrect_causal_hypothesis`, four
`incomplete_fix`, four `environment_test_failure`, three `regression`, two
`wrong_localization`, and one `api_behavior_misunderstanding`. One case recovered. The recovered
case admitted no new file, versus 2.56 new files on average for non-recovered cases. This is
descriptive, not relevant-file recall; ground-truth SWE-Explore annotations are still required
for the preregistered mechanism metrics.

## Ablations

| Condition | Resolved % | Recovery % | Localization delta | Avg tokens |
|---|---:|---:|---:|---:|
| Independent retry | PENDING | PENDING | — | PENDING |
| ContextRepair | PENDING | PENDING | PENDING | PENDING |
| ContextRepair without execution evidence | PENDING | PENDING | PENDING | PENDING |

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
- M2: **met** — 15 fresh tasks and 40 disjoint held-out tasks completed in all three conditions.
- M3–M5: **met for system execution** — complete recovery loops, typed failure analyses,
  new-only deltas, and two recoveries exist; manual case-study writeups remain pending.
- M6: **not met** — no standardized localization annotation run has completed.
- M7: **partially met** — a frozen 40-task held-out subset completed; the original 50-task target
  and publication-scale replication remain unfulfilled.
- M8: **met at strong portfolio scale, not publication scale** — the 120-run held-out comparison
  completed with full task artifacts and paired statistics.

Resume performance claims must remain unwritten until M8. Any X/Y/Z claim must point to its
exact output file and evaluator run; engineering claims may describe implemented and verified
infrastructure without implying a resolution-rate improvement.

## Resume-safe wording

The current artifacts support a strong engineering/evaluation claim and an honest
non-significant research result, not an improvement claim:

> Built a failure-conditioned LLM coding-agent recovery system with typed failure analysis,
> targeted repository re-exploration, Docker isolation, resumable spend caps, and provider-level
> tracing across 120 held-out SWE-bench Verified evaluations.

> Evaluated 40 held-out tasks across three controlled conditions (14.45M tokens); measured
> 55.0% ContextRepair, 52.5% matched-budget Retry, and 55.0% Single resolution, reporting the
> non-significant +2.5-point paired result honestly (exact McNemar p=1.0).

For Cohere, use the two bullets above: they emphasize agent infrastructure, reproducible evals,
matched controls, and statistical honesty without claiming that ContextRepair outperformed.
