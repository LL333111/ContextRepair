# Public Release Audit

Audit date: 2026-09-02

## Scope checks

- Fresh benchmark task directories: 15
- Fresh benchmark final results: 45
- Fresh benchmark partial results: 0
- Included local workspaces: 0
- Included held-out-40 paths: 0
- Included credential files: only `.env.example`
- Largest file: below 1 MB

## Validation

- All included JSON files parsed successfully.
- The complete deterministic test suite passed; the opt-in real-provider integration test was
  skipped as designed.
- Ruff passed with no findings.
- Searches for common API-key, bearer-token, and assigned-secret patterns found no matches.
- Machine-specific user-directory paths were replaced with public placeholders in the release copy.

## Publication boundary

This release contains completed pilot and fresh-15 evidence only. It excludes unfinished
held-out results and local preparation state. Raw model/evaluator artifacts are retained because
the referenced SWE-bench tasks and repositories are public and the audit trail is part of the
research artifact.
