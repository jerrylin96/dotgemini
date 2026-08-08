# GSA v1.0 conformance test vectors

A small, executable seed suite for third-party implementations of the
[Git Signoff Attestation core spec](../skills/signoff/specs/gsa-core.md)
(licensed under the [Community Specification License 1.0](../LICENSE-SPEC)).
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
| `invalid-malformed-tree-sha.txt` | real attestation `[SIGNOFF 2c1c0b7]` | non-40-hex SHA rejection |
| `invalid-status.txt` | synthetic | status outside the §2.2 enum |

Scope notes:

- These vectors cover **structural validation and trailer parsing** —
  what a verifier can decide from a payload alone. Anchoring checks
  (does the reviewed commit/tree exist; does an attestation commit attest
  its parent; the §5.1 lookup order) require a repository and are
  exercised by the reference verifier's test suite
  (`scripts/tests/test_verify_signoff.py`).
- Per gsa-core §2.3, `Signoff-Agent` values that don't match the token
  grammar remain valid opaque strings; no vector may require rejecting on
  `Signoff-Agent` format.
- The reference verifier ([`verify/verify_signoff.py`](../verify/verify_signoff.py))
  is pinned against this suite in CI
  (`scripts/tests/test_conformance_vectors.py`), so the suite and the
  implementation cannot drift apart silently.
