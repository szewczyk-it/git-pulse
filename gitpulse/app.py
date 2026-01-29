from __future__ import annotations
import argparse
import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from gitpulse.cache import load_cached, save_cached
from gitpulse.gitlog import scan_commits, GitLogOptions, list_branches, current_branch, is_git_repo
from gitpulse.metrics import add_derived, leaderboard, weekly_series, calendar_heatmap_df

def parse_args():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--no-merges", action="store_true")
    ap.add_argument("--branch", default="")
    return ap.parse_known_args()[0]

def ensure_derived(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cache can have old columns. Always recompute author_key/label + time fields.
    """
    if df is None or df.empty:
        return df
    # Always enforce date type and recompute derived fields (key/label logic changes)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return add_derived(df)

def load_or_scan(repo: str, branch: str | None, include_merges: bool) -> pd.DataFrame:
    df = load_cached(repo, branch)
    if df is not None and not df.empty:
        df = ensure_derived(df)
        return df

    df = scan_commits(repo, GitLogOptions(include_merges=include_merges, branch=branch))
    df = add_derived(df)
    save_cached(repo, branch, df)
    return df

def main():
    args = parse_args()

    st.set_page_config(page_title="GitPulse", layout="wide")
    st.title("GitPulse — commits vs substance")

    with st.sidebar:
        repo = st.text_input("Repo path", value=os.path.expanduser(args.repo))
        if not is_git_repo(repo):
            st.error("Not a git repository. Please provide a valid repo path.")
            st.stop()

        current = current_branch(repo)
        branches = list_branches(repo)
        branch_options = []
        if current:
            branch_options.append(("HEAD", f"Current (HEAD: {current})"))
        else:
            branch_options.append(("HEAD", "Current (HEAD)"))
        for b in branches:
            if b and b != current:
                branch_options.append((b, b))

        default_branch = args.branch.strip() if args.branch else "HEAD"
        default_idx = 0
        for i, (key, _label) in enumerate(branch_options):
            if key == default_branch:
                default_idx = i
                break

        sel_branch = st.selectbox(
            "Branch",
            options=branch_options,
            format_func=lambda x: x[1],
            index=default_idx,
        )
        branch = None if sel_branch[0] == "HEAD" else sel_branch[0]

        include_merges = st.checkbox("Include merge commits", value=not args.no_merges)

        if st.button("Scan / Refresh cache", width="stretch"):
            try:
                df_new = scan_commits(repo, GitLogOptions(include_merges=include_merges, branch=branch))
                df_new = add_derived(df_new)
                save_cached(repo, branch, df_new)
                st.success(f"Scanned {len(df_new)} commits")
            except Exception as e:
                st.error(str(e))
                st.stop()

        st.divider()

    try:
        df = load_or_scan(repo, branch=branch, include_merges=include_merges)
    except Exception as e:
        st.error(str(e))
        return
    if df is None or df.empty:
        st.warning("No commits parsed.")
        return

    # Sidebar filters
    with st.sidebar:
        # unique people by author_key, show author_label in UI
        people = (
            df[["author_key", "author_label"]]
            .dropna()
            .drop_duplicates()
            .sort_values("author_label")
            .reset_index(drop=True)
        )

        label_options = people["author_label"].tolist()

        sel_labels = st.multiselect("Authors", options=label_options, default=label_options)

        #min_date = df["date"].min().date()
        #max_date = df["date"].max().date()
        #dr = st.date_input("Date range", value=(min_date, max_date))
        min_date = df["date"].min().date()
        max_date = df["date"].max().date()

        range_mode = st.selectbox("Range", ["Last N months", "Custom (from–to)"], index=0)

        if range_mode == "Last N months":
            months_span = (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month) + 1
            months_max = max(1, months_span)
            months_default = months_max
            months = st.slider("Months back", 1, months_max, months_default)
            end = max_date
            start = (pd.Timestamp(end) - pd.DateOffset(months=months)).date()
            if start < min_date:
                start = min_date
        else:
            dr = st.date_input("Date range", value=(min_date, max_date))
            if isinstance(dr, (list, tuple)) and len(dr) == 2:
                start, end = dr[0], dr[1]
            else:
                start, end = min_date, max_date


        churn_max = int(df["churn"].quantile(0.99)) if len(df) > 10 else int(df["churn"].max())
        churn_thr_small = st.slider("Small-commit threshold (churn)", 0, max(50, churn_max), 0)

        hide_zero_files = st.checkbox("Hide commits with 0 files (e.g. merges)", value=False)

        metric_mode = st.selectbox("Heatmap mode", ["commits", "churn", "net"], index=0)

    # author filter -> author_key
    sel_keys = people[people["author_label"].isin(sel_labels)]["author_key"].tolist()

    # date input can return a single date or a tuple
#    if isinstance(dr, (list, tuple)) and len(dr) == 2:
#        start, end = dr[0], dr[1]
#    else:
#        start, end = min_date, max_date

    dff = df.copy()

    # substance thresholds at runtime
    dff["is_small"] = dff["churn"] <= churn_thr_small
    dff["is_tiny"] = dff["churn"] <= 2
    dff["is_big"] = dff["churn"] >= 300

    dff = dff[dff["author_key"].isin(sel_keys)]
    dff = dff[(dff["date"].dt.date >= start) & (dff["date"].dt.date <= end)]
    if hide_zero_files:
        dff = dff[dff["files"] > 0]

    if dff.empty:
        st.warning("No data after filters.")
        return

    # KPI
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Commits", f"{len(dff):,}")
    c2.metric("Authors", f"{dff['author_key'].nunique():,}")
    c3.metric("Churn", f"{int(dff['churn'].sum()):,}")
    c4.metric("Net", f"{int(dff['net'].sum()):,}")
    c5.metric("Avg churn/commit", f"{dff['churn'].mean():.1f}")

    st.divider()

    # Leaderboard
    lb = leaderboard(add_derived(dff))

    left, right = st.columns([1.25, 1])
    lb_view = lb.drop(columns=["author_key","med_churn","small_ratio","tiny_ratio","big_ratio","first_commit","last_commit"], errors="ignore")

    with left:
        st.subheader("Leaderboard (score = substance + regularity - tiny spam)")
        st.dataframe(
            lb_view,
            width="stretch",
            height=500,
            column_config={
                "first_commit": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "last_commit": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
            },
        )
        csv1 = lb.to_csv(index=False).encode("utf-8")
        st.download_button("Download leaderboard CSV", csv1, "leaderboard.csv", "text/csv")

    with right:
        st.subheader("Top 30 — commits vs churn")

        top_commits = lb.sort_values("commits", ascending=False).head(30)
        fig = px.bar(top_commits, x="author", y="commits")
        fig.update_layout(xaxis_title="", yaxis_title="commits")
        st.plotly_chart(fig, width="stretch")

        top_churn = lb.sort_values("churn", ascending=False).head(30)
        fig2 = px.bar(top_churn, x="author", y="churn")
        fig2.update_layout(xaxis_title="", yaxis_title="churn (added+deleted)")
        st.plotly_chart(fig2, width="stretch")

    st.divider()

    # Timeline
    st.subheader("Timeline")
    mode = st.radio("Series", ["commits", "churn", "net"], horizontal=True, index=0)
    ws = weekly_series(add_derived(dff), mode)
    fig3 = px.line(ws, x="week", y="v", color="author_label")
    fig3.update_layout(xaxis_title="", yaxis_title=mode)
    st.plotly_chart(fig3, width="stretch")

    st.divider()

    # Scatter: spammer vs meat
    st.subheader("Spam vs substance (per-author)")
    scat = lb.copy()
    fig4 = px.scatter(
        scat,
        x="commits",
        y="churn",
        size="active_days",
        hover_name="author",
        color="tiny_ratio",
    )
    fig4.update_layout(xaxis_title="commits", yaxis_title="churn", legend_title="tiny_ratio %")
    st.plotly_chart(fig4, width="stretch")

    st.divider()

    # Calendar heatmap
    st.subheader("GitHub-like heatmap (per author)")

    hm_people = (
        dff[["author_key", "author_label"]]
        .drop_duplicates()
        .sort_values("author_label")
        .reset_index(drop=True)
    )
    pick_label = st.selectbox("Heatmap author", options=hm_people["author_label"].tolist())
    pick_key = hm_people[hm_people["author_label"] == pick_label]["author_key"].iloc[0]

    cal = calendar_heatmap_df(add_derived(dff), pick_key, metric_mode)

    if not cal.empty:
        max_week = int(cal["week_i"].max())
        grid = np.full((7, max_week + 1), np.nan)

        for _, r in cal.iterrows():
            wd = int(r["weekday"])
            wi = int(r["week_i"])
            grid[wd, wi] = r["v"] if np.isnan(grid[wd, wi]) else (grid[wd, wi] + r["v"])

        ylabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        xlabels = list(range(max_week + 1))

        fig5 = go.Figure(
            data=go.Heatmap(
                z=grid,
                x=xlabels,
                y=ylabels,
                hoverongaps=False,
            )
        )
        fig5.update_layout(
            xaxis_title="Weeks",
            yaxis_title="Weekday",
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig5, width="stretch")
    else:
        st.info("No heatmap data for this author in current filters.")

    st.divider()

    # commits table
    st.subheader("Commits table (filtered)")
    show_cols = ["date", "author_label", "churn", "net", "files", "subject", "hash"]
    out = dff.sort_values("date", ascending=False)[show_cols].copy()
    out = out.rename(columns={"author_label": "author"})

    st.dataframe(out, width="stretch", height=500)

    csv2 = out.to_csv(index=False).encode("utf-8")
    st.download_button("Download commits CSV", csv2, "commits.csv", "text/csv")

if __name__ == "__main__":
    main()
