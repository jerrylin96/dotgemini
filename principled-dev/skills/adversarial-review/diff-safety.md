# Diff Safety

- Resolve refs to immutable SHAs and use merge-base range `<base>...<target>`.
- Redirect large `git diff`, `--stat`, and `--name-status -z` output to session-isolated scratch files to prevent terminal truncation.
- Quote paths. Enumerate paths with null delimiters. Report binary, rename, mode, and missing-newline changes without corrupting content.
- Read complete output in bounded chunks. Never infer EOF from one short or truncated tool response.
- Delete only exact scratch files created by this workflow.
- Scratch and disposable review worktrees may be created; primary checkout and durable feature worktree remain untouched.
