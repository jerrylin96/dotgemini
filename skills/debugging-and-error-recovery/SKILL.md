---
name: debugging-and-error-recovery
description: Guides systematic root-cause debugging. Use when tests fail, builds break, or behavior doesn't match expectations.
---

# Debugging and Error Recovery

## Overview

Systematic debugging with structured triage. When something breaks, stop adding features, preserve evidence, and follow a structured process to find and fix the root cause. Guessing wastes time. The triage checklist works for test failures, build errors, runtime bugs, and production incidents.

## When to Use

- Tests fail after a code change
- The build breaks
- Runtime behavior doesn't match expectations
- A bug report arrives
- An error appears in logs or console
- Something worked before and stopped working

## The Stop-the-Line Rule

When anything unexpected happens:

```
1. STOP adding features or making changes
2. PRESERVE evidence (error output, logs, repro steps)
3. DIAGNOSE using the triage checklist
4. FIX the root cause
5. GUARD against recurrence
6. RESUME only after verification passes
```

**Don't push past a failing test or broken build to work on the next feature.** Errors compound. A bug in Step 3 that goes unfixed makes Steps 4-6 wrong.

## The Triage Checklist

Work through these steps in order. Do not skip steps.

> [!TIP]
> **Subagent Delegation (Antigravity Only)**: Steps 1 to 3 (reproducing, localizing, and reducing bugs) often involve executing numerous diagnostic shell commands, reading long logs, and writing repro scripts. To prevent context window bloat, invoke the built-in `self` subagent (or `research` for read-only static analysis) to perform these steps. Instruct the subagent to use virtual environment wrappers (`setup_review_env.py` and `run_in_env.py`) for all runs/tests. This delegation contract is Antigravity-only; in other runtimes (e.g. Gemini CLI), the main agent performs these steps directly.

### Step 1: Reproduce

Make the failure happen reliably. If you can't reproduce it, you can't fix it with confidence.

### Step 2: Localize

Narrow down WHERE the failure happens:
- UI/Frontend
- API/Backend
- Database
- Build tooling
- External service
- Test itself

### Step 3: Reduce

Create the minimal failing case:
- Remove unrelated code/config until only the bug remains
- Simplify the input to the smallest example that triggers the failure
- Strip the test to the bare minimum that reproduces the issue

A minimal reproduction makes the root cause obvious and prevents fixing symptoms instead of causes.

### Step 4: Fix the Root Cause

Fix the underlying issue, not the symptom.
- For example, if database queries yield duplicates, do not filter them in UI code; instead, fix the SQL JOIN query that generates duplicates.
