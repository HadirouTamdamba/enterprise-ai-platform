# ADR-005: Governance as first-class platform resources

**Status:** Accepted · **Date:** 2026-07-16

## Context
EU AI Act, GDPR, DORA and ISO 42001 require technical documentation, risk management, logging and
human oversight. Bolting compliance on afterwards (spreadsheets, wikis) always drifts from reality.

## Decision
Model cards, prompt cards, dataset cards, risk register entries, approval workflows and audit
events are database-backed API resources generated from live registry metadata. Deploying a
high-risk asset requires an `approval` record (human-in-the-loop) enforced in the application
layer. The audit log is append-only and hash-chained for tamper evidence.

## Consequences
+ Compliance artifacts are always in sync with what actually runs.
+ Auditors get exportable, verifiable evidence.
− Slight friction on deployment flows for high-risk assets — intended and configurable per org.
