from __future__ import annotations
import hashlib
import os
from pathlib import Path
import pandas as pd

def _safe_repo_id(repo_path: str, branch: str | None) -> str:
    p = os.path.abspath(os.path.expanduser(repo_path))
    b = branch or "HEAD"
    payload = f"{p}|{b}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

def cache_dir() -> Path:
    base = Path(os.path.expanduser("~/.cache/git-pulse"))
    base.mkdir(parents=True, exist_ok=True)
    return base

def cache_path_for(repo_path: str, branch: str | None) -> Path:
    return cache_dir() / f"{_safe_repo_id(repo_path, branch)}.pkl"

def load_cached(repo_path: str, branch: str | None) -> pd.DataFrame | None:
    p = cache_path_for(repo_path, branch)
    if p.exists():
        try:
            return pd.read_pickle(p)
        except Exception:
            return None
    return None

def save_cached(repo_path: str, branch: str | None, df: pd.DataFrame) -> None:
    p = cache_path_for(repo_path, branch)
    df.to_pickle(p)
