from __future__ import annotations
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

FIELD_SEP = "\x1f"
REC_SEP = "\x1e"   # record marker at the BEGINNING of a commit

@dataclass(frozen=True)
class GitLogOptions:
    include_merges: bool = True
    branch: str | None = None
    all_branches: bool = False

def _run_git(repo_path: str, args: list[str]) -> str:
    repo = os.path.abspath(os.path.expanduser(repo_path))
    cmd = ["git", "-C", repo] + args
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        msg = e.output.decode("utf-8", errors="replace")
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{msg}")
    return out.decode("utf-8", errors="replace")

def _is_git_repo(repo_path: str) -> bool:
    repo = os.path.abspath(os.path.expanduser(repo_path))
    try:
        _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
        return True
    except Exception:
        return False

def list_branches(repo_path: str) -> list[str]:
    if not _is_git_repo(repo_path):
        return []
    out = _run_git(repo_path, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    return [line.strip() for line in out.splitlines() if line.strip()]

def current_branch(repo_path: str) -> str | None:
    if not _is_git_repo(repo_path):
        return None
    try:
        out = _run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        return out or None
    except Exception:
        return None

def is_git_repo(repo_path: str) -> bool:
    return _is_git_repo(repo_path)

def scan_commits(repo_path: str, opts: GitLogOptions | None = None) -> pd.DataFrame:
    if opts is None:
        opts = GitLogOptions()

    if not _is_git_repo(repo_path):
        raise RuntimeError(f"Not a git repo: {repo_path}")

    # Record marker at the BEGINNING of a commit (key for correct --numstat parsing)
    # First record line: <hash><FS><an><FS><ae><FS><ad><FS><s>
    pretty = f"{REC_SEP}%H{FIELD_SEP}%an{FIELD_SEP}%ae{FIELD_SEP}%ad{FIELD_SEP}%s"

    args = ["log"]
    if not opts.include_merges:
        args.append("--no-merges")
    if opts.all_branches:
        args.append("--all")
    elif opts.branch:
        args.append(opts.branch)
    args += [
        "--date=iso-strict",
        f"--pretty=format:{pretty}",
        "--numstat",
        "--no-color",
    ]

    raw = _run_git(repo_path, args)

    # split by marker; the first element before the first marker is empty
    records = raw.split(REC_SEP)
    rows = []

    for rec in records:
        rec = rec.strip("\n")
        if not rec.strip():
            continue

        lines = rec.splitlines()
        header = lines[0]
        parts = header.split(FIELD_SEP)
        if len(parts) < 5:
            continue

        commit_hash, author_name, author_email, date_s, subject = parts[:5]

        try:
            dt = datetime.fromisoformat(date_s.replace("Z", "+00:00"))
        except Exception:
            dt = None

        added = 0
        deleted = 0
        files = 0
        binary_files = 0

        # subsequent lines are --numstat (or empty)
        for l in lines[1:]:
            if not l.strip():
                continue

            # numstat: <added>\t<deleted>\t<path>
            # path can contain tabs? rare, but split max 2 to be safe
            cols = l.split("\t", 2)
            if len(cols) < 3:
                continue

            a, d, _path = cols[0], cols[1], cols[2]
            files += 1

            # binary changes: "-" in numstat
            if a == "-" or d == "-":
                binary_files += 1
                continue

            try:
                added += int(a)
                deleted += int(d)
            except ValueError:
                # skip any weird lines
                pass

        churn = added + deleted
        net = added - deleted

        rows.append(
            {
                "hash": commit_hash,
                "author": author_name,
                "email": author_email,
                "date": dt,
                "subject": subject,
                "added": added,
                "deleted": deleted,
                "churn": churn,
                "net": net,
                "files": files,
                "binary_files": binary_files,
                "has_numstat": files > 0,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        df = df.sort_values("date")
    return df
