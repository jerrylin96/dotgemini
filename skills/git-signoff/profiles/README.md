# Designing Interview Profiles for Scientific & Computational Research

> The goal of a signoff interview is preventing cognitive surrender. In software engineering, code fails **loudly** (crashes, type errors, 500s). In science, code fails **plausibly**: an atmospheric emulator that silently leaks mass, uncorrected multiple testing claiming false genetic associations, unit slips between hPa and Pa, or numerical cancellation in an ill-conditioned solver.

This guide explains how to author custom interview profiles for scientific, mathematical, and computational codebases.

---

## 1. Why Generic Software Questions Fail Scientists

A generic software engineering interview asks about:
- Algorithmic time complexity ($O(N \log N)$)
- Data structure invariants (hash collisions, tree balancing)
- Backward-compatible API endpoints

These questions **miss the silent, non-crashing bugs unique to scientific computing**. Research code rarely crashes on a bad map lookup; it produces **plausible-but-unphysical results** that get published, cited, and incorporated into downstream models before anyone notices.

A scientific interview profile shifts the probe weight to:
1. **Conservation & Physical Invariants:** Does the computation violate exact laws (energy, mass, momentum, charge)?
2. **Numerical Stability & Precision:** Does the algorithm degrade in edge regimes (cancellation, ill-conditioning, CFL timestep limits)?
3. **Statistical Validity & Leakage:** Do train/test splits share spatial/temporal correlations? Are multiple hypotheses corrected?
4. **Units & Coordinate Conventions:** Are units explicit and verified? Are coordinate transformations staggered or centered correctly?
5. **Surrogate Boundaries:** Where does an ML surrogate or parametric approximation become non-physical?

---

## 2. Quickstart: 30-Second Setup

### Option A: Zero-Touch CLI Initialization
To initialize a repository with the built-in scientific profile, pass `--profile domain-science`:

```bash
curl -fsSL https://raw.githubusercontent.com/jerrylin96/git-signoff/init-v10/init.py -o /tmp/signoff-init.py && python3 /tmp/signoff-init.py --profile domain-science
```

This automatically writes `.git-signoff/profile.md` configured for scientific computing, vendors the skill, and sets up CI verification.

### Option B: Commit `.git-signoff/profile.md` Manually
In any existing repository using `/git-signoff`, create `.git-signoff/profile.md` at the repository root and paste the canonical profile block from [`domain-science.md`](domain-science.md) (or copy verbatim below):

```markdown
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: domain-science
Profile-ID: domain-science

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Unit & dimensional validity:** units, coordinate conventions, and
  physical-constant provenance for every computed quantity the diff touches
  (e.g. hPa vs. Pa, mixing ratio vs. specific humidity, model-level vs.
  pressure-level coordinates).
- **Surrogate vs. ground truth:** where approximations knowingly violate
  exact domain laws (e.g. an ML parameterization that leaks energy or
  moisture); the parameter regimes where the surrogate is valid and what
  detects drift outside them.
- **Numerical stability:** conditioning of the chosen formulation,
  catastrophic cancellation, tolerance and convergence-criterion choices,
  and the regimes (e.g. CFL-limited timesteps, near-saturation moist
  thermodynamics) where the algorithm degrades before it visibly fails.
- **Statistical validity:** sampling assumptions, leakage between
  train/validation/test splits (e.g. temporally or spatially overlapping
  reanalysis periods), and multiple-comparison risks behind any reported
  improvement.
- **Uncertainty quantification:** how uncertainty is estimated and
  propagated into every reported quantity; which error sources the reported
  intervals (e.g. ensemble spread) include and which they silently exclude.
- **Reproducibility:** seeds, environment pinning, and data provenance
  required to regenerate the results the diff claims.
<!-- INTERVIEW-PROFILE:END -->
```

Every collaborator running `/git-signoff` in that repository will now be interviewed against these scientific emphases.

---

## 3. How Profiles Work: The 4 Universal Axes

The four axes of Git Signoff Attestation (GSA) are **universal and immutable**:
1. **Mechanics & Intent**
2. **Deviations, Trade-offs & Edge Cases**
3. **Boundary Conditions & Failure Loudness**
4. **Ownership**

Profiles **cannot** remove axes or lower pass criteria. Instead, your profile provides **domain emphases** that guide the AI interviewer on *what concrete scenarios to probe* within those axes.

| Universal Axis | Generic Software Probe | Scientific / Mathematical Probe |
|---|---|---|
| **1. Mechanics** | "What classes changed and why?" | "What governing equations or statistical estimators were changed, and why this discretization/solver over alternatives?" |
| **2. Trade-offs** | "Why an in-memory cache over Redis?" | "Where does this approximation violate exact conservation or asymptotic convergence, and what error magnitude was accepted?" |
| **3. Boundaries** | "What happens when the socket times out?" | "At what CFL number or condition number does this diverge, and does it fail loudly with an exception or produce silent NaN drift?" |
| **4. Ownership** | "Do you take responsibility for deploy risks?" | "Do you explicitly attest that validity regimes and uncertainty bounds were verified for these published results?" |

---

## 4. Discipline-Specific Profile Templates

Copy the template that best matches your lab's domain, rename `Profile-ID:`, and paste into `.git-signoff/profile.md`.

### Template A: Physical & Geophysical Simulation (Climate, Fluids, Astrophysics)
```markdown
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: fluid-climate-sim
Profile-ID: fluid-climate-sim

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Conservation laws:** exact conservation of mass, energy, tracer mass, and
  vorticity across flux boundaries; explicit accounting for non-conservative dissipation.
- **Grid & coordinate conventions:** staggering (Arakawa grids), vertical coordinate
  definitions (hybrid sigma-pressure vs. z-levels), and metric terms in curvilinear grids.
- **Numerical stability & CFL:** advective and diffusive Courant-Friedrichs-Lewy limits;
  timestep sensitivity and damping schemes for gravity/acoustic wave modes.
- **Dimensional consistency:** SI/MKS consistency, standard gravity/gas constant provenance,
  and dimensionless numbers (Reynolds, Rossby, Froude).
- **Subgrid parameterization limits:** validity boundaries where turbulence, convection,
  or cloud microphysics closures break down or yield unphysical negative values.
<!-- INTERVIEW-PROFILE:END -->
```

### Template B: Bioinformatics, Genomics & Clinical Data
```markdown
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: genomics-bioinformatics
Profile-ID: genomics-bioinformatics

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Batch effects & confounders:** technical artifacts across sequencing lanes, dates,
  operators, or study sites; normalization strategies and residual confounding.
- **Multiple hypothesis correction:** False Discovery Rate (FDR) / Benjamini-Hochberg,
  Bonferroni adjustments, and genomic control factors ($\lambda_{GC}$) on p-value distributions.
- **Patient/sample independence:** data leakage across longitudinal patient visits,
  cryptic relatedness, or duplicate cell barcodes in single-cell assays.
- **Genome build & annotation provenance:** reference assembly alignment (GRCh38 vs. CHM13 vs. hg19),
  liftover coordinate integrity, and transcript/gene version pinning.
- **Quality filtering thresholds:** read depth cutoffs, minor allele frequency (MAF) limits,
  and mapping quality boundaries that bias downstream variant calling.
<!-- INTERVIEW-PROFILE:END -->
```

### Template C: AI for Science (ML Surrogates, Physics-Informed NNs, Emulators)
```markdown
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: ai4science-surrogates
Profile-ID: ai4science-surrogates

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Manifold extrapolation & drift:** behavior when input features fall outside
  the physical training distribution; detection guards for out-of-distribution inputs.
- **Physical admissibility:** enforcement or soft-penalty bounds on non-negativity
  (e.g. chemical concentrations), divergence-free velocity fields, or energy conservation.
- **Data split leakage:** temporal autocorrelation (evaluating on adjacent timesteps),
  spatial autocorrelation (evaluating on nearby grid cells), or weather regime overlap.
- **Metric alignment:** verification that aggregate loss (e.g. MSE, $R^2$) is not masking
  catastrophic errors in extreme values, high-gradient fronts, or spectral power density.
- **Inference latency vs. fidelity trade-off:** quantified speedup relative to ground-truth
  numerical solvers and the acceptable error tolerance across benchmark test cases.
<!-- INTERVIEW-PROFILE:END -->
```

### Template D: Pure Math, Statistics & Numerical Analysis
```markdown
<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: numerical-analysis
Profile-ID: numerical-analysis

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Conditioning & perturbation bounds:** condition number $\kappa(A)$ of linear systems,
  sensitivity to matrix perturbations, and regularization strategies for ill-posed problems.
- **Floating-point errors:** catastrophic cancellation in differences of near-equal values,
  underflow/overflow scaling, and single- vs. double-precision accumulation.
- **Convergence properties:** theoretical vs. empirical convergence orders ($O(h^p)$),
  stopping tolerance criteria (relative vs. absolute residuals), and stagnation detection.
- **Symmetry & spectral preservation:** preservation of positive definiteness,
  orthogonality, symplectic geometry, or Hamiltonian invariants.
- **Reproducibility & RNG:** determinism across hardware backends (CPU vs. GPU),
  thread count invariants in parallel reductions, and master RNG seed management.
<!-- INTERVIEW-PROFILE:END -->
```

---

## 5. Audit Trail & Provenance

When you customize `.git-signoff/profile.md`, signoff computes a SHA-256 digest of your profile block and records it directly into the immutable git attestation trailer:

```text
Signoff-Agent: ... interview=standard/fluid-climate-sim/sha256:7b9a4c12f08e
```

This guarantees:
1. **Auditable Peer Review:** Reviewers, lab PIs, and journal editors can inspect the exact question set used during signoff.
2. **Dilution Detection:** If someone weakens the profile to make signoff easier, the digest changes, creating an indelible tamper-evident trail in git history.
3. **Survives Updates:** Repo-local `.git-signoff/profile.md` files survive skill updates, harness migrations, and git worktrees.
