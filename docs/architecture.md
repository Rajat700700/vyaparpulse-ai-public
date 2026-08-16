# Architecture and Decision Controls

## System flow

The React interface sends authenticated requests to a FastAPI application. FastAPI validates and normalises imported order-line files, persists tenant-scoped records in MongoDB, runs deterministic opportunity logic and exposes decision records to the command centre, recovery radar, outlet view, action board and impact ledger.

## Decision services

- **Ingestion and mapping:** validates required fields, dates, quantities and values; prevents duplicate imports and rows.
- **Recovery engine:** evaluates lapsed activity, decline, missed cadence and SKU whitespace using explicit thresholds and stored calculation provenance.
- **Priority scoring:** combines value, confidence, urgency and strategic components into an explainable score.
- **Action workflow:** controls assignment and valid state transitions.
- **Attribution:** links subsequent invoice evidence to completed actions inside a defined window and prevents duplicate recovery claims.

## Applied AI

AI-assisted functionality is deliberately bounded. It may suggest column mappings and turn pre-calculated facts into an English or Hindi/Hinglish brief. It does not calculate monetary values, determine tenant access or bypass workflow rules. Grounding validation compares narrative values with supplied deterministic facts and falls back to a deterministic template when validation fails.

## Security boundaries

- Secrets are provided through environment variables.
- Passwords are hashed with bcrypt.
- JWT access and refresh tokens are validated by the backend.
- Queries are scoped by enterprise/tenant identifiers.
- Role checks guard privileged operations.
- Demo users cannot mutate persistent production data.
- Brute-force attempts are rate-limited using expiring records.

## Synthetic-data boundary

All public examples are fictional synthetic scenarios generated for demonstration. They are not sourced from Rajat Kumar Mahajan's employer, customers or distributors. No real PCC, sales, growth, volume or outlet-execution data belongs in this repository.

## Development disclosure

Rajat Kumar Mahajan defined the FMCG business problem, product workflows, domain rules, decision and AI guardrails, stakeholder experience and validation criteria. Implementation was developed with AI-assisted tooling and Emergent. This transparent AI-assisted approach is part of the proof of work: converting domain knowledge into a testable product system.
