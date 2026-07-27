# Principled Development Guardrails

- Require separate explicit human approval of specification and plan before repository edits.
- Modify repository files only inside configured durable feature worktree.
- Use a separate detached disposable worktree for independent review.
- Bind manifests, review verdicts, publication, and signoff to exact Git SHAs.
- Never claim tests, builds, or checks passed without current empirical output.
- Never create a PR or merge/push into integration branch; human owns integration.
- Never force-remove a dirty feature worktree.
