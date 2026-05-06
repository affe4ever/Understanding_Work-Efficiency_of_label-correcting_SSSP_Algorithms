# %% [markdown]
# # Rank Error & Delay Distribution Analysis
#
# Memory strategy
# ───────────────
# • The script operates in a strict ONE-PASS read architecture.
# • Raw data (20M+ rows) is loaded exactly once. While in memory:
#   1. All Histogram charts are generated immediately.
#   2. Global extremes (min, max, mean) are extracted to a JSON.
#   3. A simplified binned `_summary.csv` (200 rows) is generated.
#   4. The raw DataFrame is immediately freed from memory.

# %%
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"]      = "1"

import re
import gc
import json
import matplotlib
import matplotlib.ticker as ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
import seaborn as sns
from pathlib import Path
from collections import defaultdict

# ── tunables ──────────────────────────────────────────────────────────────────
RANK_ERROR_PERCENTILE = 99.5
DELAY_PERCENTILE      = 99.5
PQ_SIZE_PERCENTILE    = 99.5
NUM_BINS              = 200
PCTILE_QUANTILES      = [5, 25, 50, 75, 95]
SHORT_NAME_LEN        = 50

Y_BOTTOM_MARGIN = 0.02
Y_TOP_MARGIN    = 0.08

LOG_FLOOR      = 0.1
LOG_FLOOR_FRAC = 1e-3
LOG_FLOOR_CNT  = 0.5

# ── paths ─────────────────────────────────────────────────────────────────────
import argparse

# Parse CLI arguments
parser = argparse.ArgumentParser(description="Generate summaries and histograms from CSV files")
parser.add_argument("--data-dir", type=str, default="out", help="Input data directory with CSV files")
parser.add_argument("--summaries-dir", type=str, default="histogram_out/summaries", help="Summaries output directory")
parser.add_argument("--histogram-dir", type=str, default="histogram_out", help="Histogram output directory")
args = parser.parse_args()

DATA_DIR      = Path(args.data_dir)
SUMMARIES_DIR = Path(args.summaries_dir)
OUTPUT_DIR    = Path(args.histogram_dir)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

HIST_PERCENTILES = {
    "rank_error": RANK_ERROR_PERCENTILE,
    "delay":      DELAY_PERCENTILE,
    "pq_size":    PQ_SIZE_PERCENTILE,
}

print(f"Output directory : {OUTPUT_DIR.resolve()}")
print(f"Summaries dir    : {SUMMARIES_DIR.resolve()}")
print(f"Data directory   : {DATA_DIR.resolve()}")

# ── consistent visual language ─────────────────────────────────────────────────
C_RANK_ERROR     = "#4C72B0"
C_DELAY          = "#DD8452"
C_PQ_SIZE        = "#2ecc71"
C_EXTRA_WORK     = "#e74c3c"
C_EXTRA_WORK_GEN = "#9b59b6"

# ── helpers ───────────────────────────────────────────────────────────────────
def short(name: str) -> str:
    s = name if len(name) <= SHORT_NAME_LEN else name[:SHORT_NAME_LEN] + "…"
    return s.replace("_", " ")

def make_fig(*args, **kwargs) -> Figure:
    fig = Figure(*args, **kwargs)
    FigureCanvasAgg(fig)
    return fig

def save_fig(fig: Figure, path, dpi: int = 150):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    except (ZeroDivisionError, ValueError):
        fig.set_constrained_layout(False)
        try:
            fig.tight_layout(rect=[0, 0, 1, 0.95])
        except Exception:
            pass
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.clf()
    del fig
    gc.collect()

def _set_plain_ticks(ax, axis='both'):
    """Force non-scientific notation and disable LaTeX-style math text."""
    for get_lim, set_lim in [(ax.get_xlim, ax.get_xlim), (ax.get_ylim, ax.get_ylim)]:
        try:
            lo, hi = get_lim()
            if lo == hi:
                set_lim(lo - 0.1, hi + 0.1)
        except: pass

    fmt = ticker.ScalarFormatter(useOffset=False)
    fmt.set_scientific(False)
    if hasattr(fmt, 'set_useMathText'):
        fmt.set_useMathText(False)
    elif hasattr(fmt, '_set_use_math_text'):
        fmt._set_use_math_text(False)

    if axis in ['x', 'both']:
        ax.xaxis.set_major_formatter(fmt)
        ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    if axis in ['y', 'both']:
        ax.yaxis.set_major_formatter(fmt)
        ax.yaxis.set_minor_formatter(ticker.NullFormatter())

def _apply_log_y(ax, floor: float = LOG_FLOOR):
    ax.set_yscale("log")
    lo, hi = ax.get_ylim()
    new_lo = max(lo, floor) if lo > 0 else floor
    new_hi = max(hi, new_lo * 10.0)
    ax.set_ylim(new_lo, new_hi)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())

# %% [markdown]
# ## 1 — Data Discovery

# %%
ALGO_TOKENS = sorted(["capq", "dijkstra", "drpq", "klsm", "mq", "smq"], key=len, reverse=True)

def detect_graph_and_algo(stem: str) -> tuple[str, str]:
    base  = stem[:-5] if stem.endswith("_rank") else stem
    parts = base.split("_")
    for i, tok in enumerate(parts):
        stripped = re.sub(r"\d+$", "", tok)
        if stripped in ALGO_TOKENS and i > 0:
            return "_".join(parts[:i]), "_".join(parts[i:])
    return "_".join(parts[:-1]), parts[-1]

def algo_family(algo_name: str) -> str:
    first = algo_name.split("_")[0]
    return re.sub(r"\d+$", "", first)

def discover_files(data_dir: Path) -> dict[str, Path]:
    data_dir  = Path(data_dir)
    if not data_dir.exists(): raise FileNotFoundError(f"DATA_DIR '{data_dir.resolve()}' does not exist.")
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files: raise FileNotFoundError(f"No CSV files found in '{data_dir.resolve()}'.")
    return {p.stem: p for p in csv_files}

stem_paths: dict[str, Path] = discover_files(DATA_DIR)
stem_info: dict[str, tuple[str, str]] = {s: detect_graph_and_algo(s) for s in stem_paths}
graph_file_groups: dict[str, dict[str, Path]] = defaultdict(dict)
for stem, (graph, algo) in stem_info.items():
    graph_file_groups[graph][algo] = stem_paths[stem]

print(f"Discovered {len(stem_paths)} CSV file(s) across {len(graph_file_groups)} graph group(s).")


# %% [markdown]
# ## 2 — Data Loading & Processing

# %%
def load_one_raw(path: Path) -> pd.DataFrame | None:
    wanted = {"rank_error", "delay", "pq_size", "node_id", "extra_work", "extra_work_generated", "ignored_node"}
    try:
        df = pd.read_csv(path, usecols=lambda c: c in wanted, engine="c", low_memory=False)
    except Exception as exc:
        print(f"⚠️  Could not read {path.name}: {exc} — skipping")
        return None
    if not {"rank_error", "delay"}.issubset(df.columns): return None
    for col in df.select_dtypes("float64").columns: df[col] = df[col].astype("float32")
    for col in df.select_dtypes("int64").columns:   df[col] = pd.to_numeric(df[col], downcast="integer")
    return df

def extract_summary_and_globals(df: pd.DataFrame, n_bins: int) -> tuple[pd.DataFrame, dict]:
    """Generates binned summary and exact global extremes/averages."""
    n = len(df)
    bin_size = n / n_bins
    summary = {"bin_center": []}
    cols = [c for c in df.columns if c in ["rank_error", "delay", "pq_size", "extra_work", "extra_work_generated", "ignored_node"]]

    globals_dict = {}

    for c in cols:
        globals_dict[f"{c}_min"]  = float(df[c].min(skipna=True))
        globals_dict[f"{c}_max"]  = float(df[c].max(skipna=True))
        globals_dict[f"{c}_mean"] = float(df[c].mean(skipna=True))

        summary[f"{c}_mean"]  = []
        summary[f"{c}_sum"]   = []
        summary[f"{c}_count"] = []
        for q in PCTILE_QUANTILES: summary[f"{c}_p{q}"] = []

    for i in range(n_bins):
        s = int(i * bin_size)
        e = min(int((i + 1) * bin_size), n)
        summary["bin_center"].append((s + e) / 2.0)

        for c in cols:
            chunk = df[c].values[s:e]
            chunk = chunk[~np.isnan(chunk)]
            if len(chunk) > 0:
                summary[f"{c}_mean"].append(chunk.mean())
                summary[f"{c}_sum"].append(chunk.sum())
                summary[f"{c}_count"].append(len(chunk))
                pcts = np.percentile(chunk, PCTILE_QUANTILES)
                for q, val in zip(PCTILE_QUANTILES, pcts): summary[f"{c}_p{q}"].append(val)
            else:
                summary[f"{c}_mean"].append(np.nan)
                summary[f"{c}_sum"].append(0)
                summary[f"{c}_count"].append(0)
                for q in PCTILE_QUANTILES: summary[f"{c}_p{q}"].append(np.nan)

    return pd.DataFrame(summary), globals_dict


# %% [markdown]
# ## 3 — Histogram Plotting

# %%
def plot_histograms_immediate(graph, algo, family, raw_df, log_scale=False):
    scale_tag = "log" if log_scale else "linear"
    d = OUTPUT_DIR / graph / family / "histograms"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{algo}_{scale_tag}.png"

    if out.exists(): return

    plot_cols = [c for c in ["rank_error", "delay", "pq_size", "extra_work", "extra_work_generated"] if c in raw_df.columns]
    HIST_COLORS = {
        "rank_error":          C_RANK_ERROR,
        "delay":               C_DELAY,
        "pq_size":             C_PQ_SIZE,
        "extra_work":          C_EXTRA_WORK,
        "extra_work_generated": C_EXTRA_WORK_GEN,
    }

    fig  = make_fig(figsize=(6.5 * len(plot_cols), 4))
    axes = fig.subplots(1, len(plot_cols))
    if len(plot_cols) == 1: axes = [axes]

    fig.suptitle(f"Distributions ({scale_tag}) — {short(graph)} / {short(algo)}", fontsize=12, fontweight="bold", y=0.98)

    for col, ax in zip(plot_cols, axes):
        raw = raw_df[col].dropna()

        # 1. Categorical/Binary columns
        if col in ["extra_work", "extra_work_generated"]:
            counts = raw.astype(int).value_counts().sort_index()
            ax.bar(counts.index.astype(str), counts.values, color=HIST_COLORS[col], edgecolor="white", lw=0.8, alpha=0.9)
            ax.set_ylim(0, counts.values.max() * (1 + Y_TOP_MARGIN))
            if col == "extra_work":
                ax.set_xlabel("0 = necessary  /  1 = unnecessary", fontsize=8)
                ax.set_title("Extra Work Distribution", fontsize=10)
            else:
                ax.set_xlabel(col.replace("_", " ").title(), fontsize=10)
                ax.set_title(col.replace("_", " ").title() + " Distribution", fontsize=10)

        # 2. Continuous columns
        else:
            vals = raw
            val_min   = vals.min()
            val_max   = vals.max()
            val_range = int(val_max) - int(val_min) + 1

            if val_range <= 200:
                bins = np.arange(int(val_min), int(val_max) + 2) - 0.5
            else:
                num_bins = min(80, max(30, val_range // 50))
                bins = np.linspace(val_min, val_max, num_bins + 1)

            counts, _ = np.histogram(vals, bins=bins)
            ax.hist(vals, bins=bins, color=HIST_COLORS[col], edgecolor="white", lw=0.8, alpha=0.9)

            cap = float(np.percentile(vals, HIST_PERCENTILES.get(col, 100)))
            ax.set_xlim(bins[0], cap)

            mask_visible    = bins[1:] <= cap
            visible_counts  = counts[mask_visible] if mask_visible.any() else counts
            max_visible     = visible_counts.max() if visible_counts.size > 0 else 1
            ax.set_ylim(0, max_visible * (1 + Y_TOP_MARGIN))

            title   = col.replace("_", " ").title()
            dropped = (raw > cap).sum()
            if dropped:
                title += f"\n({dropped:,} rows > p{HIST_PERCENTILES.get(col)}={cap:.0f} not shown)"
            ax.set_title(title, fontsize=10)
            ax.set_xlabel(col.replace("_", " ").title(), fontsize=10)

        # 3. Formatting
        ax.set_ylabel("Count", fontsize=10)

        if log_scale:
            _apply_log_y(ax, floor=LOG_FLOOR_CNT)
            _set_plain_ticks(ax, axis='x')
        else:
            _set_plain_ticks(ax, axis='both')
            fmt = ticker.ScalarFormatter(useOffset=False)
            fmt.set_scientific(False)
            ax.xaxis.set_major_formatter(fmt)
            ax.yaxis.set_major_formatter(fmt)

        sns.despine(ax=ax)

    fig.set_constrained_layout(False)
    save_fig(fig, out)


# %% [markdown]
# ## 4 — Single-Pass Execution (Read → Histogram → Summarize → Free)

# %%
def find_baseline_path(graph_name: str) -> tuple[str, Path] | None:
    for algo_name, p in graph_file_groups.get(graph_name, {}).items():
        if algo_family(algo_name) == "dijkstra": return algo_name, p
    return None

print("\nProcessing: Reading Raw Data, Generating Histograms, Summaries & Globals...")

for graph_name, algo_paths in sorted(graph_file_groups.items()):
    for algo_name, csv_path in sorted(algo_paths.items()):
        fam      = algo_family(algo_name)
        sum_path = SUMMARIES_DIR / f"{csv_path.stem}_summary.csv"
        glo_path = SUMMARIES_DIR / f"{csv_path.stem}_globals.json"

        hists_done = all(
            (OUTPUT_DIR / graph_name / fam / "histograms" / f"{algo_name}_{'log' if ls else 'linear'}.png").exists()
            for ls in (True, False)
        )

        if sum_path.exists() and glo_path.exists() and hists_done:
            print(f"  ✓  {algo_name} — already processed, skipping")
            continue

        print(f"  Processing {csv_path.name}...")
        raw_df = load_one_raw(csv_path)
        if raw_df is None: continue

        # 1. Histograms
        for log_scale in (True, False):
            plot_histograms_immediate(graph_name, algo_name, fam, raw_df, log_scale=log_scale)

        # 2. Summary CSV + Globals JSON
        if not sum_path.exists() or not glo_path.exists():
            sum_df, globals_dict = extract_summary_and_globals(raw_df, NUM_BINS)
            sum_df.to_csv(sum_path, index=False)
            with open(glo_path, "w") as f: json.dump(globals_dict, f, indent=2)

        # 3. Free memory immediately
        del raw_df
        gc.collect()

print("\n✅  Done.")