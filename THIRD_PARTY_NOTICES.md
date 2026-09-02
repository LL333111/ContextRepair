# Third-Party Notices

ContextRepair does not vendor an upstream coding-agent scaffold, full benchmark dataset,
container image, or source-repository checkout. Public release snapshots may include generated
model trajectories, patches, evaluator logs, aggregate results, and the public task statements
or code excerpts needed to audit those results.

Runtime dependencies retain their own licenses:

- PyYAML — MIT License.
- Optional Hugging Face `datasets` — Apache License 2.0.
- Optional development tools (`pytest`, `pytest-cov`, `ruff`) — see their distributions.

SWE-bench, SWE-bench Verified, the evaluated source repositories, model providers, and any
localization dataset remain third-party artifacts. Their names, task statements, code excerpts,
and generated evaluation records may appear in this repository for research reproducibility.
They remain subject to their respective licenses, terms, and citation requirements. No complete
third-party repository, benchmark image, or dataset distribution is included.
