---
name: code-review-and-quality
description: Review changes for correctness, clarity, architecture, security, performance, and evidence before integration.
---

# Code Review and Quality

Every codebase change receives evidence-backed review before human integration. Review the changed lines, surrounding context, requirements, and verification results.

## Review Axes

### Correctness

- Does the change satisfy the approved specification and plan?
- Are edge cases, errors, concurrency, and state transitions handled?
- Do tests prove intended behavior rather than implementation details?

### Readability and Simplicity

- Is control flow clear and naming consistent with the project?
- Is new complexity necessary?
- Can existing code or standard facilities replace custom code?
- Are dead code and accidental files absent?

### Architecture

- Does the change preserve boundaries and existing patterns?
- Are coupling, dependencies, and public contracts appropriate?
- Does the fix address the shared root cause?

### Security

- Are inputs, authorization, secrets, sensitive data, and failure modes handled safely?
- Do dependency or configuration changes expand trust or attack surface?

### Performance

- Are time, memory, I/O, network, and blocking costs reasonable for expected scale?
- Does the change introduce repeated work or unbounded resource use?

## Evidence Review

Treat behavioral and static evidence separately:

- **Behavioral change:** require observed test evidence for new or changed behavior, including a prior RED failure when TDD applies, plus relevant regression results.
- **Static-only change:** require the appropriate parser, schema, lint, build, or focused inspection result. Static validation is not behavioral TDD.

Never infer that checks passed. If a required check was not run or its environment was unavailable, mark it unverified.

## Findings and Verdict

Label findings by impact: blocking, important, suggestion, or informational. Cite the affected location, explain the consequence, and propose the smallest sound correction.

Issue one verdict:

- **Approve:** no blocking findings; evidence supports integration.
- **Request changes:** correctness, safety, scope, or verification gaps remain.

After fixes, inspect the new diff and rerun affected verification before approving. Human review and integration remain the final gate.
