# Interview Profile: software-general (default)

Ready-to-paste INTERVIEW PROFILE block for general software engineering
reviews. This is the default profile embedded in [../SKILL.md](../SKILL.md);
the block below and the embedded block are kept byte-identical
(test-enforced). To install, replace everything from
`<!-- INTERVIEW-PROFILE:BEGIN` through `<!-- INTERVIEW-PROFILE:END -->` in
`SKILL.md` with the block below.

<!-- INTERVIEW-PROFILE:BEGIN (sole customization point — replace only this block) -->
### Interview Profile: software-general
Profile-ID: software-general

Domain emphases — weight probes within the universal axes; never remove axes
or lower pass criteria:
- **Efficiency:** algorithmic complexity and hot-path cost of the chosen
  design; what input scale breaks the current approach.
- **Data structures:** invariants of the chosen structures, which operations
  can corrupt them, and why this representation over alternatives.
- **API contracts:** caller-visible behavior changes, error contracts, and
  backward compatibility of interfaces the diff touches.
<!-- INTERVIEW-PROFILE:END -->
