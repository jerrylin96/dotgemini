"""MCP layer for the GSA engine (spec §4). Only module importing `mcp`.

Run from the repository to attest: `signoff-mcp` (stdio transport).
Socratic interviewing stays in the agent prompt; these tools are
deterministic Git mechanics only.
"""

import os
from dataclasses import asdict

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from signoff_mcp import core


def create_server(repo_path: str | None = None) -> MCPServer:
    repo = core.GitRepo(repo_path or os.getcwd())
    state: dict[str, core.PrepareState | None] = {"prepare": None}
    server = MCPServer(
        "signoff",
        instructions=(
            "Deterministic GSA v1.0 attestation mechanics. Run signoff_prepare, conduct the "
            "Socratic interview agent-side, obtain explicit user approval, then signoff_commit. "
            "Push notes with signoff_push_notes."
        ),
    )

    @server.tool()
    def signoff_prepare(target_ref: str = "HEAD", reference_ref: str | None = None) -> dict:
        """Resolve reviewed/base/tree SHAs, range diff, file list, and transcript status.

        Also reports the resolved interview profile (source, path, id, digest
        per SKILL.md Section 1 step 5 — announce it before the first probe;
        a set fallback_reason means a malformed file-sourced profile was
        ignored for the embedded default) and the science-guard signal
        categories detected in the range diff (non-empty means the
        domain-science emphases apply additively and cursory must be
        refused). reference_ref defaults to the target's configured upstream;
        pass it explicitly when no upstream exists.
        """
        try:
            prep = core.prepare(repo, target_ref, reference_ref)
        except core.SignoffError as e:
            raise ToolError(str(e)) from e
        state["prepare"] = prep
        return asdict(prep)

    @server.tool()
    def signoff_commit(
        tradeoffs: list[str],
        risks: list[str],
        user_email: str,
        sign_commit: bool = True,
        ack_no_transcript: bool = False,
        agent: str = "unknown",
        summary: str | None = None,
    ) -> dict:
        """Create the attestation commit + git notes after explicit user approval.

        Status is derived server-side from transcript availability (§2.2):
        if the transcript is unavailable and ack_no_transcript=False the
        commit aborts; set ack_no_transcript=True only after the user
        explicitly confirms the downgraded status.
        """
        prep = state["prepare"]
        if prep is None:
            raise ToolError("No prepared signoff state: run signoff_prepare first.")
        try:
            result = core.commit(
                repo,
                prep,
                tradeoffs=tradeoffs,
                risks=risks,
                user_email=user_email,
                sign_commit=sign_commit,
                ack_no_transcript=ack_no_transcript,
                agent=agent,
                summary=summary,
            )
        except core.SignoffError as e:
            raise ToolError(str(e)) from e
        state["prepare"] = None
        return asdict(result)

    @server.tool()
    def signoff_push_notes(remote: str = "origin") -> dict:
        """Push refs/notes/signoff using the §2.5 tracking-ref cat_sort_uniq merge."""
        try:
            return core.push_notes(repo, remote)
        except core.SignoffError as e:
            raise ToolError(str(e)) from e

    return server


def main() -> None:
    create_server().run("stdio")


if __name__ == "__main__":
    main()
