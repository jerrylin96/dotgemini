---
name: adversarial-review
description: Adversarial review and diff explanation of two git worktrees.
---

# Adversarial Review and Diff Explanation

Automatically resolve context, create/update feature branch worktree, and perform adversarial diff review.

## Context Resolution

1. Run the helper branch resolution script to discover branches and manage worktree:
   ```bash
   python3 ~/.gemini/skills/adversarial-review/scripts/resolve_branches.py [optional_target_branch]
   ```
2. If the script output contains `"ambiguous": true`:
   - Present the candidate list to the user.
   - Ask the user to clarify which branch is the intended feature branch.
3. If no candidate feature branch is found (e.g., `"feature_branch": null`):
   - Report that no feature branch is available to review, and ask the user to specify one.

## Execution Steps

1. Get the diff using the resolved branches:
   - Run `git diff <reference_branch>...<feature_branch>` to extract changes introduced by the feature branch.
2. Perform adversarial review on the diff, emphasizing:
   - **HPC Constraints**: Do not expect intermediate compute files from HPC jobs or attempt running scripts requiring HPC-level resources.
   - **Technical Bugs**: Logical errors, performance issues, security vulnerabilities, regression risks, and code design.
   - **Scientific & Interpretation Errors**: Formula correctness, numerical stability, incorrect statistical assumptions, data leakage, and misinterpretation of data/metrics.
   - **Writing Quality**: Clarity and accuracy of documentation, comments, markdown, and precision of language.
3. Output the final review report directly into the chat. Do not save to file unless requested.
