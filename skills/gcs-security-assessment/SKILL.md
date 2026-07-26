---
name: gcs-security-assessment
description: |
  Audit Google Cloud Storage (GCS) buckets for security configurations, baseline controls, toxic access combinations, SAIF risk factors, and telemetry log signals.
  Use when:
  - Auditing GCS bucket security configurations.
  - Identifying toxic access combinations or shadow access paths.
  - Evaluating baseline controls (UBLA, public access prevention, TLS, HTTP enforcement).
  - Reviewing SAIF risk factors for GCS data storage.
---

# GCS Security Assessment

Guidelines and reference procedures for evaluating Google Cloud Storage (GCS) security posture.

## Core Reference Modules

- **Baseline Security Controls**: See [baseline_security.md](references/baseline_security.md) for required per-bucket and project-level checks (UBLA, TLS, HTTP block, Audit logging).
- **Toxic Access Combinations**: See [toxic_combinations.md](references/toxic_combinations.md) for multi-parameter risk archetypes and shadow access paths.
- **Bucket Classification**: See [bucket_classification.md](references/bucket_classification.md) for data sensitivity tiering.
- **SAIF Risk Factors**: See [saif_risk_factors.md](references/saif_risk_factors.md) for AI risk framework alignment.
- **Telemetry Signals**: See [telemetry_signals.md](references/telemetry_signals.md) for log queries and signal detection.
