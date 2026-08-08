# Interview Profile: domain-science

Ready-to-paste INTERVIEW PROFILE block for research and scientific-computing
reviews, where the primary risk is producing plausible-but-invalid results
rather than crashing. To install, replace everything from
`<!-- INTERVIEW-PROFILE:BEGIN` through `<!-- INTERVIEW-PROFILE:END -->` in
[../SKILL.md](../SKILL.md) with the block below.

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
