from __future__ import annotations
import argparse
import os
import pandas as pd
from gitpulse.gitlog import scan_commits, GitLogOptions
from gitpulse.cache import load_cached, save_cached
from gitpulse.metrics import add_derived, leaderboard

def cmd_scan(args: argparse.Namespace) -> int:
    repo = os.path.expanduser(args.repo)
    branch = args.branch or None
    df = scan_commits(repo, GitLogOptions(include_merges=not args.no_merges, branch=branch))
    df = add_derived(df)
    save_cached(repo, branch, df)
    print(f"OK: scanned {len(df)} commits, cached.")
    return 0

def cmd_summary(args: argparse.Namespace) -> int:
    repo = os.path.expanduser(args.repo)
    branch = args.branch or None
    df = load_cached(repo, branch)
    if df is None:
        df = add_derived(scan_commits(repo, GitLogOptions(include_merges=not args.no_merges, branch=branch)))
        save_cached(repo, branch, df)
    lb = leaderboard(df)
    print(lb.head(15).to_string(index=False))
    return 0

def main() -> int:
    p = argparse.ArgumentParser(prog="git-pulse")
    sub = p.add_subparsers(dest="cmd", required=True)

    pscan = sub.add_parser("scan", help="Scan repo and cache results")
    pscan.add_argument("--repo", required=True)
    pscan.add_argument("--no-merges", action="store_true")
    pscan.add_argument("--branch", default="")
    pscan.set_defaults(func=cmd_scan)

    psum = sub.add_parser("summary", help="Quick leaderboard summary")
    psum.add_argument("--repo", required=True)
    psum.add_argument("--no-merges", action="store_true")
    psum.add_argument("--branch", default="")
    psum.set_defaults(func=cmd_summary)

    args = p.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
