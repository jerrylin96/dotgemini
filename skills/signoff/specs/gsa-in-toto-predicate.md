# Draft: GSA as an in-toto Attestation Predicate Type

**Document Version:** 0.1.0  
**Status:** Draft / Informative (open-standard milestone 4, ecosystem interop) — not yet submitted to the in-toto attestation registry.  
**Canonical Location:** `skills/signoff/specs/gsa-in-toto-predicate.md`  
**License:** [Community Specification License 1.0](https://github.com/jerrylin96/signoff/blob/main/LICENSE-SPEC)  

## Purpose

The OpenSSF attestation ecosystem — [in-toto](https://in-toto.io),
SLSA, Sigstore — attests **builds, provenance, and signatures**. Nothing in
it attests **human comprehension**: no existing predicate states that a
named human demonstrated understanding of a change and accepted
accountability for its risks. GSA is complementary, not competing, and this
document drafts the mapping that lets GSA attestations travel through
in-toto tooling (bundles, Rekor transparency logs, policy engines) as a
first-class predicate — the concrete interop vehicle named in the project's
open-standard path, and a candidate donation artifact.

The git-native record (empty commit + `refs/notes/signoff`, per
[gsa-core.md](gsa-core.md)) remains canonical. The in-toto statement is a
**projection**: generated from the git record, verifiable against it, never
a substitute for it.

## Predicate type

```
https://jerrylin96.github.io/signoff/predicates/gsa/v1
```

*Provisional identifier.* It moves to a project-owned domain or a neutral
foundation namespace before any registry submission; per in-toto
conventions the URI is an identifier, resolvability is a courtesy.

## Statement layout

Subjects bind the statement to the exact reviewed code state using both GSA
anchors: the reviewed commit and — because it survives squash merges and
rebases (gsa-core §5) — the reviewed tree.

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    { "name": "git:commit", "digest": { "gitCommit": "453c633078ecdd82d93c33eefac4d5f4cbe2ef55" } },
    { "name": "git:tree",   "digest": { "gitTree":   "83679c5222ef2c7a7b8e5c83bc56c526d7f95567" } }
  ],
  "predicateType": "https://jerrylin96.github.io/signoff/predicates/gsa/v1",
  "predicate": {
    "specVersion": "1.0",
    "status": "VERIFIED_BY_HUMAN",
    "timestamp": "2026-08-04T19:40:30Z",
    "baseSha": "f31907acf1bca6e6f9decf5c7c7b07601b96f060",
    "harnessId": "antigravity-cli",
    "conversationId": "d079fa80-516d-41d5-8e76-8b6d79dbd3c9",
    "transcriptDigest": "sha256:1675b639de65cab2ef732bf418f37d9583023ffe77a166a835ca1828e1a3738e",
    "transcriptBytes": 121474,
    "tradeoffs": [
      "Accumulate repeat attestations via git notes append",
      "Defer MCP server implementation to Phase 2"
    ],
    "risks": [],
    "verifiedBy": "jerrylin247365@gmail.com",
    "agent": "Antigravity /signoff v1.0",
    "attestationCommitSha": "<sha-of-the-empty-attestation-commit, when known>"
  }
}
```

## Mapping rules

1. Trailer keys map to lowerCamelCase predicate fields; the repeated-key
   trailers (`Signoff-Tradeoff`, `Signoff-Risk`) become arrays, with the
   `none` sentinel mapping to `[]`.
2. `unavailable` sentinels map to JSON `null` (`conversationId`,
   `transcriptDigest`, `transcriptBytes`); a `null` transcript digest
   corresponds exactly to `VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST`.
3. `Signoff-Agent` is carried as the opaque string it is defined to be
   (gsa-core §2.3 backward compatibility); consumers MAY parse the token
   grammar but MUST NOT reject on it.
4. Reviewed commit and tree SHAs appear only as subjects, not duplicated in
   the predicate; `baseSha` stays in the predicate (it contextualizes the
   review range but does not identify the attested artifact).
5. Signing: the projection SHOULD be DSSE-enveloped and signed by the
   reviewer's identity (Sigstore keyless with the same email as
   `verifiedBy` is the natural fit), independently of whether the git
   attestation commit was GPG/SSH-signed.
6. Verification: a consumer holding the git repository MUST be able to
   reconstruct the predicate from the attestation commit/note and compare
   field-for-field; a mismatch invalidates the projection, never the git
   record.

## Open questions before registry submission

- Final predicate-type namespace (project domain vs. foundation namespace —
  tied to the governance milestone in `docs/productionization.md`).
- Whether `attestationCommitSha` belongs in the predicate or a
  `resourceDescriptor` annotation.
- Interaction with SLSA provenance when the same commit carries both
  predicates (human comprehension ∧ build provenance as a combined policy).
