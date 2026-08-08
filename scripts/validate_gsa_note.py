#!/usr/bin/env python3
"""GSA v1.0 Note Payload Validator.

Validates GSA attestation payloads attached to commits or trees, enforcing
mandatory trailers (including Signoff-Verified-By), valid 40-hex SHAs, spec
version 1.0, allowed statuses, and binding matching.

Usage:
    python3 scripts/validate_gsa_note.py <payload|filepath|-> [expected_tree] [expected_commit]
"""

import os
import re
import sys

VALID_STATUSES = {"VERIFIED_BY_HUMAN", "VERIFIED_BY_HUMAN_NO_TRANSCRIPT_DIGEST"}
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def parse_trailers(text: str) -> dict[str, list[str]]:
    """Extract Signoff-* trailers from text block."""
    trailers: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^(Signoff-[A-Za-z0-9-]+):\s*(.*)$", line, re.IGNORECASE)
        if m:
            key = m.group(1)
            # Normalize casing for canonical lookup
            canonical_key = "-".join(part.capitalize() for part in key.split("-"))
            trailers.setdefault(canonical_key, []).append(m.group(2).strip())
    return trailers


def check_block(text: str, expected_tree: str = "", expected_commit: str = "") -> bool:
    """Validate a single attestation block structural and binding compliance."""
    trailers = parse_trailers(text)

    specs = trailers.get("Signoff-Spec-Version", [])
    statuses = trailers.get("Signoff-Status", [])
    trees = trailers.get("Signoff-Reviewed-Tree-Sha", [])
    commits = trailers.get("Signoff-Reviewed-Commit-Sha", [])
    verified_bys = trailers.get("Signoff-Verified-By", [])

    # Mandatory trailers check (GSA §2.1 & §2.5)
    if not specs or not statuses or not trees or not commits or not verified_bys:
        return False

    # Check Signoff-Verified-By contains non-empty entries
    if not any(v for v in verified_bys):
        return False

    # Signoff-Spec-Version must be 1.0
    if any(s != "1.0" for s in specs):
        return False

    # Signoff-Status must be an allowed status
    if any(st not in VALID_STATUSES for st in statuses):
        return False

    # Reviewed tree and commit SHAs must be valid 40-hex strings
    if any(not SHA_RE.match(t) for t in trees):
        return False
    if any(not SHA_RE.match(c) for c in commits):
        return False

    # Binding checks
    if expected_tree and expected_tree not in trees:
        return False
    if expected_commit and expected_commit not in commits:
        return False

    return True


def validate_payload(payload: str, expected_tree: str = "", expected_commit: str = "") -> bool:
    """Validate payload against GSA v1.0 specifications."""
    if not payload or not payload.strip():
        return False

    # Normalize CRLF line endings
    payload = payload.replace("\r\n", "\n")

    # If payload contains multi-block [SIGNOFF ...] headers, evaluate blocks individually
    if "\n[SIGNOFF " in payload or payload.startswith("[SIGNOFF "):
        blocks = []
        raw_blocks = payload.split("[SIGNOFF ")
        for b in raw_blocks:
            b = b.strip()
            if b:
                blocks.append("[SIGNOFF " + b)
        for block in blocks:
            if check_block(block, expected_tree, expected_commit):
                return True

    # Fallback / single block / cat_sort_uniq sorted trailers check
    return check_block(payload, expected_tree, expected_commit)


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: validate_gsa_note.py <payload|filepath|-> [expected_tree] [expected_commit]\n")
        sys.exit(1)

    arg1 = sys.argv[1]
    expected_tree = sys.argv[2] if len(sys.argv) > 2 else ""
    expected_commit = sys.argv[3] if len(sys.argv) > 3 else ""

    if arg1 == "-":
        payload = sys.stdin.read()
    elif arg1.startswith("@") and os.path.exists(arg1[1:]):
        with open(arg1[1:], "r", encoding="utf-8") as f:
            payload = f.read()
    elif os.path.exists(arg1):
        with open(arg1, "r", encoding="utf-8") as f:
            payload = f.read()
    else:
        payload = arg1

    if validate_payload(payload, expected_tree, expected_commit):
        sys.exit(0)
    else:
        sys.stderr.write("GSA note validation failed: missing mandatory trailers or binding mismatch\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
