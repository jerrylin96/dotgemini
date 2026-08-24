# Codebase Audit Scorecard: [Target Name / Branch / Date]

**Audit Mode:** [Diff Comparison (`base_ref...head_ref`) | Whole-Repository Sweep]  
**Audited Target:** `[target_ref or repo_path]`  
**Total Volume:** `[N]` files, `[M]` lines across `[K]` functional clusters  
**Audit Date:** [YYYY-MM-DD]  
**Overall Health Verdict:** `[APPROVE | NEEDS_REVISION | REJECT]`

---

## 1. Executive Summary & Cluster Breakdown

| Cluster ID | Domain Name | Files | Lines | Test Suite Target | Subagent Verdict |
|---|---|---|---|---|---|
| `cluster_1` | [e.g. Core Physics & Training] | `[N1]` | `[L1]` | `pytest tests/physics/` | `[APPROVE/NEEDS_REVISION]` |
| `cluster_2` | [e.g. IO & Storage Pipeline] | `[N2]` | `[L2]` | `pytest tests/io/` | `[APPROVE/NEEDS_REVISION]` |
| `cluster_3` | [e.g. Transforms & Preprocessing] | `[N3]` | `[L3]` | `pytest tests/transforms/` | `[APPROVE/NEEDS_REVISION]` |

---

## 2. Prioritized Findings Scorecard

### P0 Blockers (Critical: Data Corruption, Divergence, Crashes)
*Issues that compromise trained weights, produce invalid scientific outputs, corrupt storage, or cause runtime panics.*

- **[P0-1] `[path/to/file.py:L123-L145]` — [Title of Critical Bug]**
  - **Empirical Evidence / Test Trace:**
    ```text
    [Paste exact test failure or line citation]
    ```
  - **Impact Mechanism:** [Explain how this corrupts state/results]
  - **Remediation / Suggested Patch:**
    ```diff
    -[old broken line]
    +[fixed line]
    ```

---

### P1 High Priority (Silent Semantic Drift, Interface Bugs, Untested Failure Modes)
*Logic flaws that degrade performance, violate invariants, or silently fail under boundary conditions.*

- **[P1-1] `[path/to/file.py:L45-L60]` — [Title of High Issue]**
  - **Empirical Evidence:** [Exact file:line citation]
  - **Impact Mechanism:** [Explain consequence]
  - **Remediation:** [Suggested fix]

---

### P2 Polish (Defensive Improvements, Documentation & Type Accuracy)
*Readability improvements, missing docstrings, or type hint mismatches.*

- **[P2-1] `[path/to/file.py:L10-L15]` — [Title of Polish Item]**
  - **Description:** [Concise note]

---

## 3. Cross-Boundary Contract Matrix

*Reconciles public interfaces, data schemas, and shared types between decoupled clusters.*

| Producer Cluster | Exported Symbol / API | Consumer Cluster | Contract Status | Notes / Breaking Changes |
|---|---|---|---|---|
| `cluster_1` | `function_or_class_name()` | `cluster_2` | `[VERIFIED / BROKEN]` | [Signature / invariant notes] |
| `cluster_2` | `DataSchema / Config` | `cluster_3` | `[VERIFIED / BROKEN]` | [Data schema notes] |

---

## 4. Blast Radius & Downstream Artifact Impact Assessment

| Downstream Asset | Status | Blast Radius / Potential Compromise | Action Required |
|---|---|---|---|
| **Model Checkpoints** | `[SAFE / COMPROMISED / UNVERIFIED]` | [e.g. Weights trained before commit X may have suffered from gradient scaling bug] | [e.g. Retrain from checkpoint #N] |
| **Processed Datasets** | `[CLEAN / CORRUPTED]` | [e.g. Coordinate transform was inverted in cache] | [e.g. Invalidate cache `data/processed_v1`] |
| **Experiment Metrics** | `[ACCURATE / SKEWED]` | [e.g. Loss calculation did not normalize batch dimension] | [e.g. Re-evaluate test split] |
| **Production API / Pipeline** | `[READY / BLOCKED]` | [e.g. Backward-incompatible response key] | [e.g. Bump API minor version] |

---

## 5. Human Signoff & Merge Action Plan

- [ ] Remediate P0 Blockers before proceeding.
- [ ] Review and patch P1 High issues.
- [ ] Confirm dataset/checkpoint blast radius and invalidate stale caches if needed.
- [ ] Trigger final regression tests: `pytest`
