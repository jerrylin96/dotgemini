---
name: math-proof-audit
description: Verify mathematical/statistical code implementations against formal LaTeX specifications, audit for numerical/algorithmic bugs via an isolated red-teaming subagent, and export persistent proof reference notes. Triggerable via /showproof.
---

# Math Proof Audit (`/showproof`)

Verify mathematical and statistical implementations in code against formal LaTeX derivations, red-team for subtle numerical/dimensional bugs, confirm trade-offs with the user, and export durable proof reference notes.

## When to Use

* **Explicit Trigger:** `/showproof`
* **Domain Use:** Verifying code that implements mathematical derivations, statistical estimators, loss functions, probability distributions, tensor/matrix algebra, PDE/ODE solvers, or numerical methods.

---

## Workflow

### Phase 1: Draft Formal Derivation & Code Alignment (Parent Agent)

Write `<appDataDir>/brain/<conversation-id>/scratch/draft_proof_<concept>.md` containing:
1. **Formal LaTeX Derivations**: Target equations, objective/density definitions, and step-by-step derivation to computational form.
2. **Variable-to-Symbol Mapping**: Map every code variable (`x`, `w`, `eps`, etc.) to its LaTeX symbol, shape/domain, and constraints.
3. **Line-by-Line Code Alignment**: Exact `file:Lstart-Lend` snippets paired with corresponding equations and any deliberate approximations.

### Phase 2: Empirical Red Teaming (Fresh-Context Subagent)

Invoke `invoke_subagent` (`TypeName: self`, `Workspace: inherit`), passing the target source file paths, `draft_proof_<concept>.md` path, and `<appDataDir>/brain/<conversation-id>/scratch/temp_math_audit_<concept>.py` path.

The subagent:
1. **Runs Empirical Checks**: Writes and executes `temp_math_audit_<concept>.py` via:
   ```bash
   python3 ~/.gemini/scripts/run_in_env.py <workspace_path> python3 <appDataDir>/brain/<conversation-id>/scratch/temp_math_audit_<concept>.py
   ```
   Uses `sympy`/`numpy`/`scipy` when installed, falling back to stdlib `math`/`cmath` with an explicit `[PREFLIGHT WARNING]` rather than failing silently. Tests finite-difference/symbolic parity, extreme scales ($10^{-15}, 10^{15}$), and degenerate inputs.
2. **Audits 5 Discrepancy Axes**:
   * **Scale & Normalization**: Missing $1/N$, $1/\sqrt{d_k}$, $2\pi$, Bessel correction ($N-1$ vs $N$), or temperature factors.
   * **Indexing & Bounds**: 0-vs-1 indexing shifts, inclusive/exclusive summation bounds, off-by-one slices.
   * **Dimensions & Transposition**: $XW$ vs $WX$, broadcasting traps, `axis` reductions.
   * **Numerical Stability**: Unstabilized $\log$/$\exp$, missing `log1p`/log-sum-exp/`x - max(x)`, division-by-zero epsilons.
   * **Boundary Guards**: Singular matrices, non-PD covariances, `NaN`/`Inf` propagation, empty/zero-variance inputs.

### Phase 3: Human Review & Trade-off Confirmation

Synthesize the derivation, 5-axis audit findings, and any intentional approximations or boundary assumptions for the user. Fix any uncovered bugs or silent failure paths first. *(If formal Socratic signoff attestation is desired for a shared repository, optionally invoke `@skill:git-signoff` or `@skill:explain-diff` on request.)*

### Phase 4: Export Proof Reference Note

Once confirmed by the user, save a self-contained proof note (embedding empirical verification output directly rather than linking ephemeral `scratch/` paths) to `Projects/<project_name>/Proofs/<concept>.md` in the resolved Obsidian Vault (`ANTIGRAVITY_OBSIDIAN_VAULT` -> `obsidian_vault_path` in `~/.gemini/antigravity-cli/settings.json` -> `~/Desktop/antigravity_vault` / `~/Documents/antigravity_vault` -> fallback `artifacts/Projects/<project_name>/Proofs/<concept>.md`).
