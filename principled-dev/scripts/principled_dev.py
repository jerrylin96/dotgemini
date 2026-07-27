#!/usr/bin/env python3
import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from principled_dev.lifecycle import Lifecycle
from principled_dev.resolver import Resolver
from principled_dev.review import ReviewRecord
from principled_dev.signoff import create_attestation, export_session_digest
from principled_dev.state import StateStore
from principled_dev.worktrees import WorktreeManager


def roots():
    cache = Path(
        os.environ.get(
            "PRINCIPLED_DEV_WORKTREE_ROOT",
            Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "principled-dev"
            / "worktrees",
        )
    ).expanduser()
    state = Path(
        os.environ.get(
            "PRINCIPLED_DEV_STATE_ROOT",
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
            / "principled-dev",
        )
    ).expanduser()
    return cache, state


def output(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def lifecycle(args):
    cache, state_root = roots()
    store = StateStore(state_root / "lifecycle.json")
    return Lifecycle(
        args.repo,
        cache,
        store,
        feature_branch=args.feature,
        base_branch=args.base,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="principled-dev lifecycle helper")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve")
    resolve.add_argument("target", nargs="?")
    resolve.add_argument("--reference")

    feature = sub.add_parser("feature")
    feature.add_argument("feature")
    feature.add_argument("--base", default="main")

    review = sub.add_parser("review-worktree")
    review.add_argument("commit")

    signoff = sub.add_parser("signoff")
    signoff.add_argument("review_json")
    signoff.add_argument("--identity", required=True)
    signoff.add_argument("--human-reviewed", action="store_true")
    signoff.add_argument("--remote-sha")
    signoff.add_argument("--session-id")
    signoff.add_argument("--digest-session", action="store_true")

    args = parser.parse_args(argv)
    cache, _ = roots()

    if args.command == "resolve":
        output(dataclasses.asdict(Resolver(args.repo, cache).resolve(args.target, reference=args.reference)))
    elif args.command == "review-worktree":
        manager = WorktreeManager(args.repo, cache)
        output({"worktree_path": manager.create_review(args.commit)})
    elif args.command == "feature":
        item = lifecycle(args)
        output({"worktree_path": item.create_feature(args.base)})
    elif args.command == "signoff":
        review_data = json.loads(Path(args.review_json).read_text(encoding="utf-8"))
        review_record = ReviewRecord.from_dict(review_data)
        session_digest = "unavailable"
        if args.digest_session:
            session = export_session_digest(args.session_id or os.environ.get("AGENT_SESSION_ID"))
            session_digest = "sha256:" + session["sha256"]
        output(
            create_attestation(
                args.repo,
                review_record.to_dict(),
                human_reviewed=args.human_reviewed,
                identity=args.identity,
                remote_sha=args.remote_sha,
                session_id=args.session_id or os.environ.get("AGENT_SESSION_ID", "unavailable"),
                session_digest=session_digest,
            )
        )


if __name__ == "__main__":
    main()
