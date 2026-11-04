# Development guidance

Before changing this project, read [AGENTS.md](AGENTS.md) and follow its product priorities, safety boundaries, documentation requirements and verification rules. Deception and attacker delay are the two primary outcomes; assess both for changes to generated artifacts and workflows.

## Quality checks

When investigating a failed GitHub Actions quality run, inspect the complete failing test output and workflow definition, reproduce the relevant steps locally, and fix the underlying issue. Keep tests aligned with the current product settings and behavior; do not restore removed features or weaken meaningful assertions just to pass CI. Before reporting the failure fixed, run the verification commands required by AGENTS.md and state any environment-specific steps that could not run. Treat `.github/workflows/quality.yml` as the source of truth for supported Python and operating-system combinations.
