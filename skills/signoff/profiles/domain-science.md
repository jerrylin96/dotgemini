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
  physical-constant provenance for every computed quantity the diff touches.
- **Surrogate vs. ground truth:** where approximations knowingly violate
  exact domain laws; the parameter regimes where the surrogate is valid and
  what detects drift outside them.
- **Statistical validity:** sampling assumptions, leakage between
  train/validation/test splits, and multiple-comparison risks behind any
  reported improvement.
- **Reproducibility:** seeds, environment pinning, and data provenance
  required to regenerate the results the diff claims.
<!-- INTERVIEW-PROFILE:END -->
