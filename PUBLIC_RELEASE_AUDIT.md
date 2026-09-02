# Public Release Audit

Audit date: 2026-09-02

## Scope checks

- Fresh benchmark task directories: 15
- Fresh benchmark full-trace final results: 45
- Held-out benchmark task directories: 40
- Held-out benchmark final results: 120
- Held-out benchmark partial results: 0
- Included local workspaces or repository mirrors: 0
- Included credential files: only `.env.example`
- Largest file: below 1 MB

## Validation

- All included JSON files parsed successfully.
- Held-out final results contain exactly 40 tasks × 3 conditions.
- Paired statistics reproduce 22 Single, 21 Retry, and 22 ContextRepair resolutions.
- The complete deterministic test suite passed; the opt-in real-provider integration test was
  skipped as designed.
- Ruff passed with no findings.
- Searches for common API-key, bearer-token, and assigned-secret patterns found no matches.
- Machine-specific user-directory paths were replaced with public placeholders in the release copy.

## Publication boundary

This release contains completed pilot, fresh-15, and held-out-40 evidence. Fresh-15 retains full
public model/evaluator traces. Held-out-40 publishes final results, paired statistics, condition
summaries, and recovery-analysis artifacts while omitting duplicate large model transcripts and
test logs. The complete held-out trace archive remains local. All referenced SWE-bench tasks and
repositories are public.
