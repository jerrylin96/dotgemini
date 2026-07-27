#!/usr/bin/env python3
import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from principled_dev.config import roots
from principled_dev.lifecycle import Lifecycle, PublicationPartialSuccess
from principled_dev.resolver import Resolver
from principled_dev.review import ReviewRecord
from principled_dev.signoff import export_session_digest
from principled_dev.state import StateStore


def output(value, path=None):
    text = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
    if path:
        Path(path).write_text(text, encoding="utf-8")
    print(text, end="")


def output_error(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str), file=sys.stderr)


def make_lifecycle(args):
    cache, state_root = roots()
    return Lifecycle(
        args.repo,
        cache,
        StateStore(state_root / "lifecycle.json"),
        feature_branch=args.feature,
        base_branch=args.base,
    )


def add_identity(parser):
    parser.add_argument("--feature", required=True)
    parser.add_argument("--base", default="main")


def main(argv=None):
    parser = argparse.ArgumentParser(description="principled-dev lifecycle helper")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--feature")
    parser.add_argument("--base", default="main")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("target", nargs="?")
    resolve.add_argument("--reference")

    record = sub.add_parser("record-artifact")
    record.add_argument("gate", choices=("spec", "plan", "build"))
    record.add_argument("file")

    approve = sub.add_parser("approve")
    approve.add_argument("gate", choices=("spec", "plan", "build"))

    feature = sub.add_parser("feature")
    feature.add_argument("feature_branch")
    feature.add_argument("--base", dest="feature_base", default="main")

    manifest = sub.add_parser("bind-manifest")
    manifest.add_argument("summary")
    manifest.add_argument("--output")

    approve_manifest = sub.add_parser("approve-manifest")
    approve_manifest.add_argument("manifest_json")

    sub.add_parser("review-worktree")

    publish = sub.add_parser("publish")
    publish.add_argument("review_json")
    publish.add_argument("--remote")

    signoff = sub.add_parser("signoff")
    signoff.add_argument("review_json")
    signoff.add_argument("--identity", required=True)
    signoff.add_argument("--human-reviewed", action="store_true")
    signoff.add_argument("--session-id")
    signoff.add_argument("--digest-session", action="store_true")

    args = parser.parse_args(argv)
    cache, _ = roots()

    if args.command == "resolve":
        output(dataclasses.asdict(Resolver(args.repo, cache).resolve(args.target, reference=args.reference)))
        return
    if args.command == "feature":
        args.feature = args.feature_branch
        args.base = args.feature_base
    if not args.feature:
        parser.error("--feature is required for lifecycle commands")
    item = make_lifecycle(args)

    if args.command == "record-artifact":
        output({"digest": item.record_artifact(args.gate, Path(args.file).read_bytes())})
    elif args.command == "approve":
        output({"digest": item.approve(args.gate), "gate": args.gate})
    elif args.command == "feature":
        output({"worktree_path": item.create_feature(args.base)})
    elif args.command == "bind-manifest":
        output(item.bind_manifest(args.summary), args.output)
    elif args.command == "approve-manifest":
        value = json.loads(Path(args.manifest_json).read_text(encoding="utf-8"))
        output({"digest": item.approve_manifest(value)})
    elif args.command == "review-worktree":
        if not item._manifest:
            parser.error("no bound manifest")
        output({"worktree_path": item.worktrees.create_review(item._manifest["commit_sha"])})
    elif args.command == "publish":
        review = ReviewRecord.from_dict(json.loads(Path(args.review_json).read_text(encoding="utf-8")))
        try:
            output(item.publish(review, remote=args.remote))
        except PublicationPartialSuccess as error:
            output_error(
                {
                    "error": "publication_partial_success",
                    "message": str(error),
                    "remote": error.remote,
                    "branch": error.branch,
                    "pushed_sha": error.pushed_sha,
                    "phase": error.phase,
                    "observed_sha": error.observed_sha,
                    "cause": error.cause,
                }
            )
            return 1
    elif args.command == "signoff":
        review = ReviewRecord.from_dict(json.loads(Path(args.review_json).read_text(encoding="utf-8")))
        if not item.feature_worktree or not Path(item.feature_worktree).is_dir():
            parser.error("persisted feature worktree is unavailable")
        feature_branch = item._feature_git().symbolic_branch()
        if feature_branch != f"refs/heads/{item.feature_branch}":
            parser.error("persisted feature worktree is not attached to expected branch")
        digest = "unavailable"
        if args.digest_session:
            session = export_session_digest(args.session_id or os.environ.get("AGENT_SESSION_ID"))
            digest = "sha256:" + session["sha256"]
        item.signoff(
            review,
            human_reviewed=args.human_reviewed,
            identity=args.identity,
            emitter=output,
            session_id=args.session_id or os.environ.get("AGENT_SESSION_ID", "unavailable"),
            session_digest=digest,
        )


if __name__ == "__main__":
    raise SystemExit(main())
