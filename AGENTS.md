# AiDeceptionGuard project guidance

## Product priorities

- Treat **deception** and **attacker delay** as the two primary product outcomes. Evaluate every feature against both: whether an attacker is likely to treat the artifact or environment as plausible, and what additional work or time it imposes before the attacker reaches useful information.
- Assume attackers may combine AI agents, generated scripts, crawlers, parallel requests, offline analysis, VPNs and disposable infrastructure. Do not assume they use a normal browser, follow embedded instructions, or inspect files one at a time.
- Prefer context-sensitive artifacts with varied names, structures and operational details over repeated generic templates. Keep limitations visible: a decoy does not prevent access, and an alert is not guaranteed to arrive before exfiltration.
- Preserve the user's explicit product decisions. In particular, do not reintroduce a feature the user has asked to remove under a different label.

## Safe decoy generation

- Generated artifacts must contain synthetic data only. Never import production records, real credentials, usable payment-card data, or third-party personal information.
- Any operator-owned domain option must require an explicit ownership and isolation confirmation. Explain whether the value can receive requests or mail, and recommend a dedicated isolated sink with no production authentication or mailboxes.
- Keep passwords, canary URL mappings and deployment inventories in operator-only files, separate from deployable artifacts.
- Do not use prompt-injection content to cause an AI to disclose third-party secrets, execute code, modify files, or access external systems. Measure whether an agent followed an instruction only in an authorized isolated evaluation.

## Evaluation and documentation

- Assess deception and delay with controlled comparisons using equivalent starting information and time budgets. Record time to target data, target reach rate, decoy discovery/contact, alert and response timing, and authorized-user false positives. Include AI-driven, scripted, parallel and offline analysis where relevant.
- Distinguish a plausible design hypothesis from measured effectiveness. Never describe evasion or delay as guaranteed.
- Keep Japanese and English UI text, README files and deployment guidance consistent when behavior changes. Explain the threat addressed, prerequisites, operational limits and what telemetry is required.
- For Japan-related legal guidance, describe the ordinary authorized use and the concrete conduct that may create legal risk. Do not present a blanket guarantee of legality or illegality.

## Verification

- Follow the user's requested verification scope. When asked to investigate a CI or quality-check failure, reproduce the failing workflow steps locally where possible and run the relevant tests; do not stop at reading the summary email.
- Before calling a CI failure fixed, run `python -m unittest discover -s tests -v`, the scripts listed in `.github/workflows/quality.yml`, `node --check web/app.js`, `node --check web/json_utils.js`, and `python tests/browser_smoke.py` when the local environment supports each step. Report any step that could not be run and why.
- Keep tests aligned with current product decisions and public setting schemas. Update stale tests when behavior intentionally changed; do not loosen assertions merely to make CI green. Preserve checks for safety limits, encrypted output, operator/deployment separation, and the absence of canary content where the product requires it.
- Use the workflow matrix as the source of truth for supported Python versions and operating systems. For cross-platform changes, consider path, encoding, archive, and shell differences explicitly.
- Check both deployment artifacts and operator-only companions whenever changing generator output or packaging behavior.
