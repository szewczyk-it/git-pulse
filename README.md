# GitPulse — local Git activity & code churn dashboard

GitPulse is a lightweight Streamlit dashboard that analyzes a **local Git repository** and generates clear, filterable insights about activity over time: commits, **code churn**, net change, active days, and simple anti-spam heuristics.

It uses only your local `.git` history (`git log --numstat`). No GitHub/GitLab API, no Jira, no network calls.

> **Important:** Git metrics measure repository activity, not “human value”. Treat these numbers as signals and always interpret them with context.

---

## What is “churn” here?

In this project, **churn** means **how many lines were touched** (changed) in commits.

For each commit we read:
- `added` = number of added lines
- `deleted` = number of deleted lines
- **`churn = added + deleted`**

Why it’s useful:
- `net` (added − deleted) can be near zero during heavy refactors (rewrite 200 lines, delete 200 lines → net = 0),
  but churn captures that real work happened (churn = 400).

Why the word “churn”:
- This is established engineering jargon: **code churn** = “turnover/rewriting” of code over time.
- Don’t confuse it with HR/marketing “customer churn” (people leaving) — different meaning.

---

## Features

- **Leaderboard per author (merged by email)**
    - commits, added, deleted, churn, net, files touched, active days
    - score = churn + regularity − tiny-commit spam penalty (transparent formula)
- **Top-N charts**
    - Top authors by commits
    - Top authors by churn
- **Time filtering**
    - date range from–to (UI)
    - (optional) “last N months” mode if enabled in the app
- **Branch selection**
    - current branch by default, selectable from a list
- **Identity merge**
    - authors are merged by email (`email:john@corp.com`)
- **Exports**
    - leaderboard CSV
    - commits CSV

---

## Quick start (Ubuntu)

### Requirements
- `python3` (3.10+ recommended)
- `git`
- a local repository to analyze

### Run
```bash
cd ~/git-pulse
./run.sh /path/to/repo main
```

The script creates a local virtualenv (`.venv`), installs dependencies, scans the repo (cached), and starts the Streamlit app.

---

## CLI usage

### Scan & cache
```bash
python -m gitpulse.cli scan --repo /path/to/repo --branch main
```

### Print leaderboard (terminal)
```bash
python -m gitpulse.cli summary --repo /path/to/repo --branch main
```

---

## Data source & calculations

### Data source (git commands)
GitPulse executes a command equivalent to:

- `git log --date=iso-strict --pretty=... --numstat`

For each commit we read:
- commit hash, author name, author email, commit date, subject
- `--numstat` lines in the form:
    - `added<TAB>deleted<TAB>path`
    - binary files are reported as `- - path` (counted as binary; not added/deleted)

### Identity (who is “the same person”)
We generate an internal key:
- `author_key = "email:" + email.lower()`

Display label:
- email only (lowercased)

### Per-commit metrics
For a single commit:
- `added` = sum of added lines from numstat (excluding binary)
- `deleted` = sum of deleted lines from numstat (excluding binary)
- `churn` = `added + deleted`
- `net` = `added - deleted`
- `files` = number of numstat rows (touched files)

### Leaderboard aggregation (per author_key)
Within the selected filters (authors + date range):
- `commits` = number of commits
- `added`, `deleted`, `churn`, `net`, `files` = sums across commits
- `avg_churn` = `churn / commits`
- `active_days` = number of unique dates with at least one commit
- `tiny_ratio` = share of commits where churn <= 2 (before formatting)

### Score formula
To reduce “commit spam” bias, the ranking score uses:

```
score =
  log(1 + churn)       * 0.55
+ log(1 + commits)     * 0.25
+ log(1 + active_days) * 0.20
- (tiny_ratio)         * 0.40
```

---

## Cache

Results are cached locally to speed up reloads:

- `~/.cache/git-pulse/<repo-hash>.pkl`
- cache is per repo + branch

To force a clean re-scan:
```bash
rm -f ~/.cache/git-pulse/*.pkl
```

---

## Interpretation notes / limitations

- Churn can be inflated by formatting, generated files, vendor imports, mass renames.
- Merge commits may have limited or zero numstat depending on history and merge strategy.
- Use this dashboard to compare patterns, not to judge individuals in isolation.

---

## Project structure

```
gitpulse/
  app.py        # Streamlit UI
  gitlog.py     # git log + numstat parsing
  metrics.py    # derived columns, aggregation, scoring
  cache.py      # filesystem cache (~/.cache/git-pulse)
  cli.py        # scan/summary helpers
run.sh
requirements.txt
```

---

## License

Recommended: **MIT** (simple, permissive).

---

## Contributing

PRs welcome:
- parsing edge cases (renames, binary changes, submodules)
- better heuristics (exclude generated files / per-path filters)
- new charts and exports

---

## Roadmap ideas (optional)
- exclude patterns (lockfiles, vendor/, dist/, generated) via config
- per-path leaderboards (frontend vs backend)
- static HTML report export (no Streamlit runtime needed)
