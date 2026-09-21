# GSA v1.0 conformance test vectors

A small, executable seed suite for third-party implementations of the
[Git Signoff Attestation core spec](../skills/git-signoff/specs/gsa-core.md)
(licensed under the [Apache License 2.0](../skills/git-signoff/specs/LICENSE)).
If your verifier reaches the verdicts in [`expected.json`](expected.json)
on every payload in [`vectors/`](vectors/), it agrees with the reference
implementation on the structural layer of the protocol.

Most vectors are **real attestations** from this repository's history, not
synthetic examples:

| Vector | Provenance | Exercises |
|---|---|---|
| `valid-production.txt` | production attestation `[SIGNOFF 453c633]` | baseline v1.0 trailers, repeated `Signoff-Tradeoff` keys |
| `valid-profile-digest.txt` | production attestation `[SIGNOFF daf4939]` | repo-local profile provenance (`interview=…/sha256:…`, §2.3), repeated tradeoffs/risks |
| `valid-no-transcript-digest.txt` | synthetic | downgraded status with `unavailable` digest/bytes (§2.2) |
| `valid-note-cat-sort-uniq.txt` | the two production payloads merged via `cat_sort_uniq` (§2.5) | repeated-key-aware parsing of merged note blobs |
| `invalid-missing-spec-version.txt` | real pre-spec attestation `[SIGNOFF 1fb5e3b]` | missing required trailer |
| `invalid-wrong-spec-version.txt` | synthetic | spec-version value outside 1.0 (declared-version enforcement) |
| `invalid-missing-verified-by.txt` | synthetic | missing `Signoff-Verified-By` — the accountability field is required (§2.1) |
| `invalid-lowercase-keys.txt` | synthetic | trailer keys are case-sensitive (§2.3) — case-variant keys are not the mandatory trailers |
| `invalid-malformed-tree-sha.txt` | real attestation `[SIGNOFF 2c1c0b7]` | non-40-hex SHA rejection |
| `invalid-status.txt` | synthetic | status outside the §2.2 enum |
| `invalid-status-digest-mismatch.txt` | synthetic | `VERIFIED_BY_HUMAN` with `unavailable` digest (§2.2 cross-field enforcement) |
| `invalid-missing-transcript-digest.txt` | synthetic | `VERIFIED_BY_HUMAN` with omitted transcript digest (§2.2 enforcement) |
| `invalid-duplicate-reviewed-tree-sha.txt` | synthetic | a second `Signoff-Reviewed-Tree-SHA` following a trade-off — the shape a line break inside free text produces; one attestation carries each single-valued trailer exactly once (§2.3), so this must not anchor either tree |

Scope notes:

- Every vector is **one attestation payload** (a commit message or one note
  block) and is judged under the §2.3 single-valued rule, except
  `valid-note-cat-sort-uniq.txt`, flagged `merged_note` in `expected.json`:
  a `cat_sort_uniq`-merged note blob whose constituent attestations cannot be
  recovered, judged under the merge-aware rules of §5.1 (and, per §5.1,
  usable to anchor only the object the note is attached to).

- These vectors cover **structural validation and trailer parsing** —
  what a verifier can decide from a payload alone. Anchoring checks
  (does the reviewed commit/tree exist; does an attestation commit attest
  its parent; the §5.1 lookup order) require a repository and are
  exercised by the reference verifier's test suite
  (`scripts/tests/test_verify_signoff.py`).
- **Object integrity (§5.1, since gsa-core 3.8.0).** A conforming verifier
  that consults attestation *commits* (in the target's history or beyond it)
  MUST require the commit object to corroborate the trailers: exactly one
  parent, an empty commit, and the declared reviewed commit as that parent;
  the declared tree anchors only when it is the parent's actual tree. A
  payload-level vector cannot express this; the reference suite's
  `test_log_lookup_*` and `test_scan_refs_*` cases are the executable
  statement of it, and a third-party implementation should reproduce them.
- Per gsa-core §2.3, `Signoff-Agent` values that don't match the token
  grammar remain valid opaque strings; no vector may require rejecting on
  `Signoff-Agent` format.
- The reference verifier ([`skills/git-signoff/verify_signoff.py`](../skills/git-signoff/verify_signoff.py))
  is pinned against this suite in CI
  (`scripts/tests/test_conformance_vectors.py`), so the suite and the
  implementation cannot drift apart silently.
