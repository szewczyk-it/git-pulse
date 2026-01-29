from __future__ import annotations
import pandas as pd
import numpy as np

def _norm_email(email) -> str:
    if email is None or (isinstance(email, float) and pd.isna(email)):
        return ""
    s = str(email).strip().lower()
    return "" if s == "nan" else s

def _author_key(email) -> str:
    e = _norm_email(email)
    return f"email:{e}"

def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()

    # base time fields
    dt = out["date"]
    if dt.dt.tz is None:
        dt = dt.dt.tz_localize("UTC")
    else:
        dt = dt.dt.tz_convert("UTC")

    out["day"] = dt.dt.date
    out["week"] = dt.dt.tz_localize(None).dt.to_period("W").dt.start_time.dt.tz_localize("UTC")
    out["month"] = dt.dt.tz_localize(None).dt.to_period("M").dt.start_time.dt.tz_localize("UTC")
    out["weekday"] = dt.dt.weekday  # 0=Mon

    # "substance" flags
    out["is_small"] = out["churn"] <= 0
    out["is_tiny"] = out["churn"] <= 2
    out["is_big"] = out["churn"] >= 300

    # --- identity key + display ---
    out["author_key"] = [_author_key(e) for e in out["email"]]

    # UI label: email only
    def _label(row) -> str:
        return _norm_email(row.get("email"))

    out["author_label"] = out.apply(_label, axis=1)

    return out

def leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    # group by author_key (email only)
    g = df.groupby("author_key", dropna=False)

    agg = g.agg(
        commits=("hash", "count"),
        churn=("churn", "sum"),
        net=("net", "sum"),
        added=("added", "sum"),
        deleted=("deleted", "sum"),
        files=("files", "sum"),
        avg_churn=("churn", "mean"),
        med_churn=("churn", "median"),
        small_ratio=("is_small", "mean"),
        tiny_ratio=("is_tiny", "mean"),
        big_ratio=("is_big", "mean"),
        active_days=("day", "nunique"),
        first_commit=("date", "min"),
        last_commit=("date", "max"),
    ).reset_index()

    # use most common label for display per key
    top_label = (
        df.groupby("author_key")["author_label"]
        .agg(lambda s: s.value_counts().index[0] if len(s) else "")
        .reset_index()
        .rename(columns={"author_label": "author"})
    )

    agg = agg.merge(top_label, on="author_key", how="left")

    # score: substance + regularity - tiny spam
    agg["score"] = (
        np.log1p(agg["churn"]) * 0.55
        + np.log1p(agg["commits"]) * 0.25
        + np.log1p(agg["active_days"]) * 0.20
        - (agg["tiny_ratio"] * 0.40)
    )

    # percenty
    for c in ["small_ratio", "tiny_ratio", "big_ratio"]:
        agg[c] = (agg[c] * 100.0).round(1)

    # columns: author first
    cols = ["author", "author_key"] + [c for c in agg.columns if c not in ("author", "author_key")]
    agg = agg[cols].sort_values("score", ascending=False)

    return agg

def weekly_series(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    base = df.copy()
    if value_col == "commits":
        base["v"] = 1
    else:
        base["v"] = base[value_col]
    s = base.groupby(["week", "author_key"], dropna=False)["v"].sum().reset_index()
    # use label for legend
    lbl = (
        base.groupby("author_key")["author_label"]
        .agg(lambda x: x.value_counts().index[0])
        .reset_index()
    )
    s = s.merge(lbl, on="author_key", how="left")
    return s.sort_values("week")

def calendar_heatmap_df(df: pd.DataFrame, author_key: str, mode: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    dfa = df[df["author_key"] == author_key].copy()
    if dfa.empty:
        return pd.DataFrame()

    if mode == "commits":
        dfa["v"] = 1
    else:
        dfa["v"] = dfa[mode]

    day = pd.to_datetime(dfa["date"].dt.date)
    dfa["day_ts"] = day
    daily = dfa.groupby("day_ts")["v"].sum().reset_index()

    daily["weekday"] = daily["day_ts"].dt.weekday
    daily["week_start"] = (daily["day_ts"] - pd.to_timedelta(daily["weekday"], unit="D"))
    minw = daily["week_start"].min()
    daily["week_i"] = ((daily["week_start"] - minw).dt.days // 7).astype(int)

    return daily
