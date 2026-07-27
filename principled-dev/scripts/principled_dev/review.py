from dataclasses import asdict, dataclass, field


SEVERITIES = ("CRITICAL", "IMPORTANT", "SUGGESTION", "FYI")
VERDICTS = ("APPROVE", "REQUEST_CHANGES", "BLOCKED")


@dataclass(frozen=True)
class Finding:
    severity: str
    path: str
    line: int
    evidence: str
    consequence: str
    remediation: str

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")
        if not self.path:
            raise ValueError("path is required")
        if self.line < 1:
            raise ValueError("line must be positive")
        for name in ("evidence", "consequence", "remediation"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")


@dataclass(frozen=True)
class ReviewRecord:
    verdict: str
    base_sha: str
    commit_sha: str
    tree_sha: str
    findings: tuple[Finding, ...] = ()
    validations: dict[str, str] = field(default_factory=dict)
    unverified_checks: tuple[str, ...] = ()
    blocked_reason: str = ""

    def __post_init__(self):
        if self.verdict not in VERDICTS:
            raise ValueError(f"invalid verdict: {self.verdict}")
        if self.verdict == "APPROVE" and any(
            item.severity in ("CRITICAL", "IMPORTANT") for item in self.findings
        ):
            raise ValueError("APPROVE cannot contain blocking findings")

    def is_fresh(self, base_sha, commit_sha, tree_sha):
        return (self.base_sha, self.commit_sha, self.tree_sha) == (
            base_sha,
            commit_sha,
            tree_sha,
        )

    def to_dict(self):
        data = asdict(self)
        data["findings"] = [asdict(item) for item in self.findings]
        data["unverified_checks"] = list(self.unverified_checks)
        return data

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        values["findings"] = tuple(Finding(**item) for item in values.get("findings", ()))
        values["unverified_checks"] = tuple(values.get("unverified_checks", ()))
        return cls(**values)

    def to_markdown(self):
        lines = [
            f"Verdict: {self.verdict}",
            f"Base-SHA: {self.base_sha}",
            f"Reviewed-Commit-SHA: {self.commit_sha}",
            f"Reviewed-Tree-SHA: {self.tree_sha}",
            "Freshness: exact SHA binding",
            "Validation:",
        ]
        lines.extend(f"- {name}: {result}" for name, result in sorted(self.validations.items()))
        lines.append("Unverified-Checks: " + (", ".join(self.unverified_checks) or "none"))
        if self.blocked_reason:
            lines.append(f"Blocked-Reason: {self.blocked_reason}")
        for severity in SEVERITIES:
            lines.append(f"{severity.title()}-Findings:")
            selected = [item for item in self.findings if item.severity == severity]
            if not selected:
                lines.append("- none")
            for item in selected:
                lines.append(
                    f"- {item.path}:{item.line} — `{item.evidence}`; "
                    f"consequence: {item.consequence}; remediation: {item.remediation}"
                )
        return "\n".join(lines) + "\n"


def record_review(
    base_sha,
    commit_sha,
    tree_sha,
    *,
    findings=(),
    validations=None,
    required_checks=(),
    blocked_reason="",
    builder_worktree=None,
    reviewer_worktree=None,
):
    if (
        builder_worktree is not None
        and reviewer_worktree is not None
        and builder_worktree == reviewer_worktree
    ):
        raise ValueError("builder and reviewer require separate worktrees")
    findings = tuple(findings)
    validations = dict(validations or {})
    unverified = tuple(sorted(set(required_checks) - set(validations)))
    if blocked_reason:
        verdict = "BLOCKED"
    elif any(item.severity in ("CRITICAL", "IMPORTANT") for item in findings):
        verdict = "REQUEST_CHANGES"
    else:
        verdict = "APPROVE"
    return ReviewRecord(
        verdict,
        base_sha,
        commit_sha,
        tree_sha,
        findings,
        validations,
        unverified,
        blocked_reason,
    )
