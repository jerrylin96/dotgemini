# Specification: GSA Transcript Escrow (Cloud & User-Owned Storage)

**Document Version:** 1.0.0  
**Status:** Reviewed Draft (Phase 5 Gate 2) — normative for future escrow implementations; **nothing in this document is built yet**, and the GSA core protocol ([gsa-core.md](gsa-core.md)) remains complete without it.  
**Canonical Spec Location:** `skills/signoff/specs/gsa-escrow.md`  
**Supersedes:** `gsa-cloud-concept.md` (removed per its own lifecycle note)  
**License:** [Community Specification License 1.0](https://github.com/jerrylin96/signoff/blob/main/LICENSE-SPEC) (SPDX: `Community-Spec-1.0`)  
**Strategy record:** decisions and evidence gates behind this design live in `docs/productionization.md`.

---

## 1. Problem & Scope

The GSA core protocol operates 100% locally: attestation trailers, risks,
and the transcript digest live in git, and verification never requires a
network service. What git does NOT hold is the transcript itself — the
Socratic interview lives as an unmanaged file on the reviewer's machine
under harness-owned storage, one cleanup, disk failure, or departed team
member away from unrecoverable. When it vanishes,
`Signoff-Transcript-Digest` stops being re-verifiable and degrades from
"checkable evidence" to "recorded claim".

**Scope of this spec:** durable, access-controlled storage of transcript
snapshots such that (a) the digest re-verification loop keeps closing years
later, and (b) a PI, auditor, or compliance reviewer can retrieve the
conversation without the original reviewer or their laptop.

**Non-goals:** attestation creation and verification MUST NOT require
escrow; CI gates MUST NOT require any cloud service. An attestation without
escrow remains valid GSA.

## 2. Privacy Design (normative, decided first)

### 2.1 Data classification

A transcript is the **entire development conversation**, not just the
interview: it can contain secrets pasted during debugging, proprietary
code far beyond the reviewed diff, personal remarks, and text from
**non-consenting third parties** (PR comments, issue text, other agents'
output). It is the most sensitive data class in the GSA system — strictly
more sensitive than the repository it accompanies, because its contents
were never curated for sharing. A public repo with restricted transcripts
is the expected configuration, never the anomaly.

### 2.2 Threat model

| Threat | Addressed by |
|---|---|
| Storage provider breach or insider | client-side encryption: providers hold ciphertext only |
| Escrow operator compromise, subpoena scope creep | user-owned storage default (no operator exists); operated registries hold ciphertext only |
| Over-broad team access | recipient-key access control, role keys held by the team, not the service |
| Un-noticed secrets in transcripts | encryption limits exposure to key holders; retention/deletion via crypto-shredding |
| Tampering with escrowed bytes | digest re-verification against the in-repo trailer; append-only/versioned storage RECOMMENDED |
| Metadata/linkage leakage (who reviewed what, when) | minimal manifest; operated registries see opaque IDs and ciphertext |

### 2.3 Principles (MUST)

1. **Plaintext never leaves the reviewer's machine.** Transcripts are
   encrypted client-side before any write to storage not controlled by the
   reviewer's own account. An implementation that uploads plaintext — even
   to an operated registry over TLS, even "encrypted at rest" — does not
   conform.
2. **Keys belong to the user or their organization**, never to a storage
   or registry operator. Losing the keys loses the transcripts; that
   trade-off is accepted and MUST be documented to users at setup.
3. **Digest semantics are unchanged from gsa-core §2.3:** the digest is
   always computed over plaintext bytes; encryption is a storage concern
   invisible to verification. Verifiers decrypt, then recompute SHA-256
   over the first `Signoff-Transcript-Bytes` bytes.
4. **Deletion is honored by key destruction** (crypto-shredding): destroying
   the relevant recipient keys renders escrowed ciphertext unrecoverable
   without touching every replica.
5. **Escrow trailers are optional:** when unconfigured, no escrow trailer
   is written (never `none`), per the gsa-core §2.1 omission rule.

## 3. Null-Hypothesis Architecture: User-Owned Storage (baseline)

This is the architecture to beat. Any operated service must justify itself
against it with the evidence gates of §5 — not with convenience claims.

### 3.1 Encryption format

Implementations SHOULD use **age** (X25519 recipients; single-binary,
scriptable, no GPG UX debt) and MUST record the format used. The payload
encrypted is exactly the snapshot captured at commit time: the first
`Signoff-Transcript-Bytes` bytes whose SHA-256 is the trailer digest.

Encryption recipients: the reviewer's key plus zero or more **role keys**
(e.g. `pi@lab`, `auditor@org`) so retrieval authority is a key-management
decision owned by the team. Adding a reader later means re-encrypting (or
sharing a role key); revoking one means rotating the role key for future
escrows — historical exposure windows are accepted and documented.

### 3.2 Storage targets

Either of two targets satisfies the baseline; both are append-only in
practice and free-to-cheap at small scale:

- **A bucket the user/org owns** (S3, R2, GCS, MinIO): layout
  `<prefix>/<reviewed-commit-sha>/<attestation-sha>.age` plus
  `<...>.manifest.json`.
- **A private git repository or ref** the org controls (e.g.
  `refs/signoff/transcripts` in a dedicated private repo): reuses existing
  git auth and backup; blobs are the same `.age` payloads. Not the public
  code repo — transcript access must be controllable independently of code
  visibility (§2.1).

### 3.3 Manifest and trailers

The manifest is deliberately minimal (metadata is also leakage):

```json
{
  "attestation_sha": "…40-hex…",
  "reviewed_commit_sha": "…40-hex…",
  "transcript_digest": "sha256:…",
  "transcript_bytes": 121474,
  "encryption": "age",
  "recipients": ["age1…fingerprint-only…"]
}
```

The attestation MAY carry one optional trailer pointing at the escrow:

```text
Signoff-Transcript-Escrow: s3://lab-escrow/signoff/453c633…/…age
Signoff-Transcript-Escrow: git+ssh://…/lab-escrow.git#refs/signoff/transcripts
```

The trailer is a locator, not a proof; verification is always the §3.4
loop. Unreachable escrow does not invalidate the attestation — it returns
it to the un-escrowed state.

### 3.4 Verification loop

1. Locate ciphertext via the trailer (or out-of-band knowledge).
2. Decrypt with an authorized key.
3. Recompute SHA-256 over the first `Signoff-Transcript-Bytes` bytes of
   the plaintext.
4. Compare against `Signoff-Transcript-Digest` in the repository. Match ⇒
   the escrowed conversation is byte-identical to what the attestation
   committed to at signoff time.

### 3.5 Write timing

Escrow SHOULD happen in the same operation that captures the snapshot
(gsa-core §2.3 snapshot timing), i.e. inside `signoff_commit` or the
skill's Section 3 step — the only moment the exact attested bytes are
guaranteed present. Later escrow of a still-intact file is permitted but
MUST re-verify the digest before upload.

## 4. Operated Registry (conditional layer, not the default)

An operated registry adds, on top of the §3 baseline: independent
ingestion timestamps, a **transparency log** (append-only, signed
checkpoints, externally monitorable — Certificate-Transparency/Rekor
design, a day-one constraint because verifiability cannot be retrofitted),
retention SLAs, and RBAC UX. It also makes its operator a data processor
and cost sink — which is why it is gated, not assumed.

Constraints beyond the baseline, all MUST:

- Ingests **ciphertext only** (§2.3-1 applies unreduced; the registry is
  monitored, not trusted — and cannot leak what it cannot read). A
  `hash_only` mode (digest + metadata, no payload) remains valid for
  tamper-evidence without escrow.
- Git remains the source of truth for attestations; the registry is an
  index and witness, never custodian of the attestation layer.
- Exit guarantees before commercial operation: free export of all escrowed
  data forever, documented shutdown/escrow-transfer procedure.
- The free/paid line of the open-core model: anything required to CREATE
  or VERIFY an attestation is free and open-source forever; paid tiers
  cover storing, aggregating, and reporting at scale. Free for public
  repositories and academic use — structural, not promotional.

API shape (informative; final contract belongs to the implementation
phase): `POST /v1/attestations/ingest` accepting trailer metadata +
optional ciphertext payload, returning an opaque `attestation_id` and
transparency-log inclusion proof; `GET /v1/attestations/{id}/transcript`
returning ciphertext to authorized callers, who decrypt locally and run
the §3.4 loop.

## 5. Evidence Gates & Infrastructure Choices

The operated registry may be built only when recorded evidence (in
`docs/productionization.md`) shows the baseline failing real users:
teams asking for managed escrow they cannot self-host, auditors requiring
independent timestamps/monitoring, or cross-organization verification
where no shared storage trust exists.

Infrastructure decisions already reviewed (see strategy doc for the
analysis): object storage on S3 or Cloudflare R2 (zero egress fees suit a
verification-heavy read pattern); metadata in a small managed Postgres
(Neon/Supabase class) — the workload is append-only encrypted blobs plus a
tiny index, and boring is a feature; DBOS-class durable-execution
frameworks are the right category but the wrong stage — escrow has almost
no workflow to orchestrate — recorded here as the alternative considered.

**Cost model (required before any operated service ships).** Baseline
assumptions, to re-validate against real usage: observed snapshots run
0.1–1.1 MB raw (121 KB and 1.06 MB in the two production attestations
carrying byte counts); assume ~1 MB average escrowed payload (long agentic
sessions compress well, so ciphertext ≈ a few hundred KB is likely —
1 MB is the conservative bound) and ~5 attestations/seat/week.

| Scale | New storage/mo | Cumulative yr-1 | Infra cost/mo |
|---|---|---|---|
| 10 seats | ~0.2 GB | ~2.5 GB | ≪ $1 (R2 $0.015/GB-mo) |
| 100 seats | ~2 GB | ~25 GB | < $1 |
| 1000 seats | ~20 GB | ~250 GB | ~$4 + managed Postgres ~$20 |

Infra is never the cost driver; the fixed costs of operating at all —
legal entity, terms of service, support capacity, incident response for
the one data class whose loss is unrecoverable — dominate, and belong in
the go/no-go decision (productionization.md, Pricing & packaging).

## 6. Conformance Summary

An escrow implementation conforms iff it:

1. Encrypts client-side with user/org-owned keys before any write beyond
   the reviewer's control (§2.3-1, -2).
2. Escrows exactly the attested snapshot bytes and preserves the
   plaintext-digest verification loop (§2.3-3, §3.4).
3. Writes escrow trailers only when configured, as locators (§2.3-5, §3.3).
4. Never makes attestation creation, verification, or CI gating depend on
   escrow availability (§1 non-goals).
5. If operated as a service: ciphertext-only ingestion, transparency log,
   exit guarantees, and the free/paid line (§4).
