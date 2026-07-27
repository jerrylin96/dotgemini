---
name: ponytail
description: Apply YAGNI, reuse-first, standard-library-first code minimization to implementation and refactoring.
---

# Ponytail

Understand the requested behavior and existing code before writing anything. Then stop at the first option that works:

1. Do not build speculative requirements.
2. Reuse an existing helper or pattern.
3. Prefer the standard library.
4. Prefer a native platform feature.
5. Use an already-installed dependency.
6. Write the minimum new code.

For bugs, trace callers and fix the shared root cause rather than patching one symptom. Prefer deletion over addition, boring code over clever abstractions, and the shortest diff that preserves tested behavior.
