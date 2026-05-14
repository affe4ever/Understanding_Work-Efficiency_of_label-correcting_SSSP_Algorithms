#!/usr/bin/env python3
"""
PQ Benchmark Visualizer
=======================
Light theme · scrollable left panel · Graph Config tree (family > size) ·
Algorithm tree (algorithm > tuning) below Seed/Area selector ·
Thread selector box (thread count > algo label) below Algorithm selector ·
Seed, Algorithm, and Thread selectors update dynamically from upstream selections ·
USA-road area codes parsed as `size` · "unseeded" for seed-less records ·
Algorithms without a specified thread count are counted as t1.

Requirements:
    pip install matplotlib

Optional hover tooltips:
    pip install mplcursors
"""

import os
import re
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.cm as _mpl_cm
import matplotlib.colors as _mpl_colors

try:
    import mplcursors
    HAS_MPLCURSORS = True
except ImportError:
    HAS_MPLCURSORS = False


# ─────────────────────────────────────────────────────────────────────────────
# Filename parser
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Export dimensions  (millimetres)
# ─────────────────────────────────────────────────────────────────────────────

EXPORT_WIDTH_MM  = 272
EXPORT_HEIGHT_MM = 188

# ─────────────────────────────────────────────────────────────────────────────

KNOWN_ALGOS = ["capq", "drpq", "klsm", "smq", "mq"]

NA       = "(none)"
UNSEEDED = "unseeded"


# Hard-coded per-algorithm marker shapes
ALGO_MARKERS = {
    "capq": "o",   # circle
    "drpq": "s",   # square
    "klsm": "^",   # triangle up
    "smq":  "D",   # diamond
    "mq":   "v",   # triangle down
}

_FALLBACK_MARKER = "o"


def algo_marker(algorithm: str) -> str:
    return ALGO_MARKERS.get((algorithm or "").lower(), _FALLBACK_MARKER)


def parse_filename(path: str) -> dict:
    """
    Parse benchmark filenames into structured metadata.
    """

    base = os.path.basename(path)
    base = re.sub(r"\.(json|csv)$", "", base)
    base = re.sub(r"_(globals|summary)$", "", base)

    info = dict(
        family=None,
        size=None,
        seed=None,
        algorithm=None,
        tuning=None,
        threads="t1",   # In order to default drpq or other algorithms
                        # that we didn't properly name the files for to
                        # show up as t1
        filepath=path,
        filename=os.path.basename(path),
    )

    rest = base

    # Dot-separated style
    dot_m = re.match(r"([A-Za-z0-9][A-Za-z0-9\-]*)\.([A-Za-z0-9]+)_(.*)", rest)

    if dot_m:
        info["family"] = dot_m.group(1)
        info["size"]   = dot_m.group(2)
        rest = dot_m.group(3)

    else:
        if rest.startswith("grid_graph_"):
            info["family"] = "grid_graph"
            rest = rest[len("grid_graph_"):]

            m = re.match(r"(X\d+_Y\d+)_(.*)", rest)

            if m:
                info["size"] = m.group(1)
                rest = m.group(2)

        else:
            m = re.match(r"([a-z][a-z0-9]*)_(\d+)_(.*)", rest)

            if m:
                info["family"], info["size"], rest = (
                    m.group(1),
                    m.group(2),
                    m.group(3),
                )

                if info["family"] == "rhg":
                    deg_m = re.match(r"(deg\d+)_(.*)", rest)

                    if deg_m:
                        info["size"] = info["size"] + "_" + deg_m.group(1)
                        rest = deg_m.group(2)

            else:
                m = re.match(r"([a-z][a-z0-9]*)_(.*)", rest)

                if m:
                    info["family"], rest = m.group(1), m.group(2)
                else:
                    return info

        m = re.match(r"(s\d+)_(.*)", rest)

        if m:
            info["seed"] = m.group(1)
            rest = m.group(2)

    for algo in KNOWN_ALGOS:
        m = re.match(rf"{re.escape(algo)}(\d+)?(?:_(.*)|$)", rest)

        if m:
            info["algorithm"] = algo

            digit_suffix = m.group(1) or ""
            after         = m.group(2) or ""

            tuning_parts = [digit_suffix] if digit_suffix else []

            for token in (after.split("_") if after else []):

                if re.match(r"^t\d+$", token):
                    info["threads"] = token
                else:
                    tuning_parts.append(token)

            tuning = "_".join(p for p in tuning_parts if p)
            info["tuning"] = tuning or None
            break

    return info


# ─────────────────────────────────────────────────────────────────────────────
# Directory scanner
# ─────────────────────────────────────────────────────────────────────────────

ALL_METRICS = [
    "rank_error_min",
    "rank_error_max",
    "rank_error_median",
    "rank_error_mean",
    "delay_min",
    "delay_max",
    "delay_median",
    "delay_mean",
    "pq_size_min",
    "pq_size_max",
    "pq_size_median",
    "pq_size_mean",
    "ignored_node_min",
    "ignored_node_max",
    "ignored_node_median",
    "ignored_node_mean",
    "extra_work_min",
    "extra_work_max",
    "extra_work_median",
    "extra_work_mean",
    "extra_work_generated_min",
    "extra_work_generated_max",
    "extra_work_generated_median",
    "extra_work_generated_mean",
]

METRIC_LABELS = {
    m: m.replace("_", " ").title()
    for m in ALL_METRICS
}


def scan_directory(directory: str) -> list:
    records = []

    for fname in sorted(os.listdir(directory)):

        if not fname.endswith("_globals.json"):
            continue

        path = os.path.join(directory, fname)

        meta = parse_filename(path)

        try:
            with open(path) as fh:
                data = json.load(fh)

            meta.update(data)
            records.append(meta)

        except Exception as exc:
            print(f"[WARN] Skipping {fname}: {exc}")

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────

C = dict(
    bg       = "#f8f9fa",
    panel    = "#ffffff",
    surface0 = "#f1f3f5",
    surface1 = "#e9ecef",
    surface2 = "#dee2e6",
    border   = "#ced4da",
    text     = "#212529",
    subtext  = "#868e96",
    muted    = "#adb5bd",
    blue     = "#1971c2",
    accent   = "#228be6",
    blue_lt  = "#dbe4ff",
)

SCATTER_PALETTE = [
    "#228be6",
    "#f76707",
    "#2f9e44",
    "#ae3ec9",
    "#f59f00",
    "#c92a2a",
    "#0c8599",
    "#d6336c",
    "#74b816",
    "#5c7cfa",
    "#3bc9db",
    "#ff6b6b",
    "#51cf66",
    "#cc5de8",
    "#fcc419",
]

COLOR_BY_OPTIONS = [
    ("family",    "Graph Family"),
    ("algorithm", "Algorithm"),
    ("size",      "Size / Area"),
    ("seed",      "Seed"),
    ("tuning",    "Tuning"),
    ("threads",   "Threads"),
    ("metric",    "Metric Scale"),
]

# Colormaps available in the metric-scale mode.
# Each entry is (matplotlib_name, display_label).
CMAP_OPTIONS = [
    ("plasma",     "Plasma  (purple → yellow)"),
    ("viridis",    "Viridis  (blue → green → yellow)"),
    ("inferno",    "Inferno  (black → orange → white)"),
    ("RdYlBu_r",  "Red → Yellow → Blue"),
    ("coolwarm",   "Cool → Warm  (blue ↔ red)"),
    ("YlOrRd",    "Yellow → Orange → Red"),
    ("Spectral_r", "Spectral  (blue → red)"),
    ("magma",      "Magma  (dark → pink → white)"),
]

CMAP_NAMES   = [c[0] for c in CMAP_OPTIONS]
CMAP_LABELS  = [c[1] for c in CMAP_OPTIONS]


def get_color_key(record: dict, color_by: str) -> str:

    family  = str(record.get("family") or NA)
    size    = str(record.get("size") or NA)
    seed    = str(record.get("seed") or "").strip()
    algo    = str(record.get("algorithm") or NA)
    tuning  = str(record.get("tuning") or NA)
    threads = str(record.get("threads") or NA)

    seed_display = seed if seed else UNSEEDED

    if color_by == "seed":
        ctx = " / ".join(p for p in [family, size] if p != NA)
        return f"{ctx}  ·  {seed_display}" if ctx else seed_display

    elif color_by == "size":
        return f"{family} / {size}"

    elif color_by == "tuning":
        return f"{algo}  ·  {tuning}"

    elif color_by == "family":
        return family

    elif color_by == "algorithm":
        return algo

    elif color_by == "threads":
        return threads

    return str(record.get(color_by) or NA)


# ─────────────────────────────────────────────────────────────────────────────
# Selection tree
# ─────────────────────────────────────────────────────────────────────────────

class SelectionTree(tk.Frame):

    ICONS = {
        2: "☑ ",
        1: "■ ",
        0: "☐ ",
    }

    def __init__(
        self,
        parent,
        hierarchy_keys: list,
        on_change=None,
        restore_scroll=None,
        tree_height: int = 7,
        **kw,
    ):
        super().__init__(parent, bg=C["panel"], **kw)

        self.hierarchy_keys  = hierarchy_keys
        self.on_change       = on_change
        self._restore_scroll = restore_scroll

        self.nodes = {}

        self.tree = ttk.Treeview(
            self,
            selectmode="none",
            show="tree",
            height=tree_height,
        )

        vsb = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.tree.yview,
        )

        hsb = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self.tree.xview,
        )

        self.tree.configure(
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
        )

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Enter>", self._on_tree_enter)
        self.tree.bind("<Leave>", self._on_tree_leave)

    def populate(
        self,
        records: list,
        index_map: list = None,
        default_state: int = 2,
    ) -> None:

        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()

        for pos, r in enumerate(records):

            global_idx = index_map[pos] if index_map is not None else pos

            node_id_parts = []
            display_parts = []

            for k in self.hierarchy_keys:

                v = r.get(k)
                v_str = str(v).strip() if v is not None else ""

                if v_str and v_str.lower() not in ("none", "(none)"):

                    node_id_parts.append(f"{k}:{v_str}")
                    display_parts.append(v_str)

            if not node_id_parts:
                node_id_parts = ["unknown:Unknown"]
                display_parts = ["Unknown"]

            parent = ""

            for depth in range(len(node_id_parts)):

                nid = "\x00".join(node_id_parts[:depth + 1])

                if nid not in self.nodes:

                    self.tree.insert(parent, "end", iid=nid, open=False)

                    self.nodes[nid] = dict(
                        state=default_state,
                        text=display_parts[depth],
                        is_leaf=False,
                        record_indices=[],
                    )

                parent = nid

            self.nodes[parent]["is_leaf"] = True
            self.nodes[parent]["record_indices"].append(global_idx)

        self._refresh_icons()

    def check_all(self) -> None:
        for child in self.tree.get_children(""):
            self._set_subtree(child, 2)

        self._refresh_icons()

        if self.on_change:
            self.after_idle(self.on_change)

    def uncheck_all(self) -> None:
        for child in self.tree.get_children(""):
            self._set_subtree(child, 0)

        self._refresh_icons()

        if self.on_change:
            self.after_idle(self.on_change)

    def expand_all(self) -> None:
        for nid in self.nodes:
            self.tree.item(nid, open=True)

    def collapse_all(self) -> None:
        for nid in self.nodes:
            self.tree.item(nid, open=False)

    def get_selected_indices(self) -> set:

        result = set()

        for nid, data in self.nodes.items():

            if data["is_leaf"] and data["state"] == 2:
                result.update(data["record_indices"])

        return result

    def _on_tree_enter(self, _e) -> None:
        self.tree.bind_all("<MouseWheel>", self._on_scroll)

    def _on_tree_leave(self, _e) -> None:
        self.tree.unbind_all("<MouseWheel>")

        if self._restore_scroll:
            self._restore_scroll()

    def _on_scroll(self, event) -> None:
        self.tree.yview_scroll(-int(event.delta / 120), "units")

    def _on_click(self, event) -> None:

        item = self.tree.identify_row(event.y)

        if not item:
            return

        if "indicator" in self.tree.identify_element(event.x, event.y):
            return

        new_state = 2 if self.nodes[item]["state"] in (0, 1) else 0

        self._set_subtree(item, new_state)
        self._bubble_up(item)
        self._refresh_icons()

        if self.on_change:
            self.after_idle(self.on_change)

    def _set_subtree(self, nid: str, state: int) -> None:

        self.nodes[nid]["state"] = state

        for child in self.tree.get_children(nid):
            self._set_subtree(child, state)

    def _bubble_up(self, nid: str) -> None:

        parent = self.tree.parent(nid)

        if not parent:
            return

        child_states = [
            self.nodes[c]["state"]
            for c in self.tree.get_children(parent)
        ]

        if all(s == 2 for s in child_states):
            new = 2
        elif all(s == 0 for s in child_states):
            new = 0
        else:
            new = 1

        self.nodes[parent]["state"] = new

        self._bubble_up(parent)

    def _refresh_icons(self) -> None:

        for nid, data in self.nodes.items():

            text = self.ICONS[data["state"]] + data["text"]

            if self.tree.item(nid, "text") != text:
                self.tree.item(nid, text=text)


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("PQ Benchmark Visualizer")
        self.geometry("1540x920")
        self.minsize(960, 640)

        self.configure(bg=C["bg"])

        self._records = []
        self._scatter_collections = []

        self._seed_vars = {}

        self._config_tree  = None
        self._algo_tree    = None
        self._thread_tree  = None

        self._restore_canvas_scroll = None

        # Colorbar instance managed across plot calls.
        self._colorbar = None

        self._setup_style()
        self._build_ui()

    # ---------------------------------------------------------------------

    def _setup_style(self) -> None:

        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(
            ".",
            background=C["bg"],
            foreground=C["text"],
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
        )

        s.configure("TFrame", background=C["bg"])

        s.configure(
            "TLabel",
            background=C["bg"],
            foreground=C["text"],
        )

        s.configure(
            "TButton",
            background=C["surface1"],
            foreground=C["text"],
            padding=(8, 4),
            borderwidth=1,
            relief="flat",
        )

        s.map(
            "TButton",
            background=[
                ("active", C["accent"]),
                ("pressed", C["blue"]),
            ],
            foreground=[
                ("active", "white"),
            ],
        )

        s.configure(
            "Accent.TButton",
            background=C["accent"],
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )

        s.map(
            "Accent.TButton",
            background=[
                ("active", C["blue"]),
                ("pressed", C["blue"]),
            ],
            foreground=[
                ("active", "white"),
            ],
        )

        s.configure(
            "TCombobox",
            fieldbackground=C["panel"],
            background=C["surface1"],
            foreground=C["text"],
            arrowcolor=C["blue"],
            padding=4,
        )

        s.configure(
            "Treeview",
            background=C["panel"],
            fieldbackground=C["panel"],
            foreground=C["text"],
            rowheight=24,
            borderwidth=0,
        )

    # ---------------------------------------------------------------------

    def _build_ui(self) -> None:

        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left  = ttk.Frame(pane, width=430)
        right = ttk.Frame(pane)

        pane.add(left, weight=0)
        pane.add(right, weight=1)

        self._build_left(left)
        self._build_right(right)

    # ---------------------------------------------------------------------

    def _build_left(self, parent: ttk.Frame) -> None:

        parent.pack_propagate(False)

        scroll_canvas = tk.Canvas(
            parent,
            bg=C["bg"],
            highlightthickness=0,
        )

        vsb = ttk.Scrollbar(
            parent,
            orient="vertical",
            command=scroll_canvas.yview,
        )

        scroll_canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(scroll_canvas, bg=C["bg"])

        cwin = scroll_canvas.create_window(
            (0, 0),
            window=inner,
            anchor="nw",
        )

        inner.bind(
            "<Configure>",
            lambda _e: scroll_canvas.configure(
                scrollregion=scroll_canvas.bbox("all")
            ),
        )

        scroll_canvas.bind(
            "<Configure>",
            lambda e: scroll_canvas.itemconfig(cwin, width=e.width),
        )

        def _canvas_scroll(e):
            scroll_canvas.yview_scroll(-int(e.delta / 120), "units")

        def restore_canvas_scroll():
            scroll_canvas.bind_all("<MouseWheel>", _canvas_scroll)

        scroll_canvas.bind("<Enter>", lambda _: restore_canvas_scroll())

        scroll_canvas.bind(
            "<Leave>",
            lambda _: scroll_canvas.unbind_all("<MouseWheel>"),
        )

        self._restore_canvas_scroll = restore_canvas_scroll

        self._build_left_content(inner)

    # ---------------------------------------------------------------------

    def _build_left_content(self, parent: tk.Frame) -> None:

        # ── Data Directory ────────────────────────────────────────────────
        dir_sec = ttk.LabelFrame(parent, text="Data Directory")
        dir_sec.pack(fill=tk.X, pady=(0, 5), ipady=2)

        self._dir_label = ttk.Label(
            dir_sec,
            text="(none selected)",
            foreground=C["subtext"],
            wraplength=370,
        )

        self._dir_label.pack(padx=8, pady=(4, 0))

        ttk.Button(
            dir_sec,
            text="Browse…",
            command=self._browse_dir,
        ).pack(padx=8, pady=6)

        # ── Graph Config ──────────────────────────────────────────────────
        cfg_lf = ttk.LabelFrame(parent, text="Graph Config")
        cfg_lf.pack(fill=tk.X, pady=(0, 5))

        self._config_tree = self._make_tree_widget(
            cfg_lf,
            hierarchy_keys=["family", "size"],
            on_change=self._update_dependent_filters,
        )

        # ── Seed / Area ───────────────────────────────────────────────────
        seed_lf = ttk.LabelFrame(parent, text="Seed / Area")
        seed_lf.pack(fill=tk.X, pady=(0, 5))

        seed_ctrl = tk.Frame(seed_lf, bg=C["bg"])
        seed_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        ttk.Button(
            seed_ctrl,
            text="All",
            width=5,
            command=self._check_all_seeds,
        ).pack(side=tk.LEFT, padx=(0, 2))

        ttk.Button(
            seed_ctrl,
            text="None",
            width=5,
            command=self._uncheck_all_seeds,
        ).pack(side=tk.LEFT)

        self._seed_container = tk.Frame(seed_lf, bg=C["bg"])
        self._seed_container.pack(fill=tk.X, padx=4, pady=(0, 4))

        # ── Algorithm (algorithm > tuning; threads split out below) ───────
        algo_lf = ttk.LabelFrame(parent, text="Algorithm")
        algo_lf.pack(fill=tk.X, pady=(0, 5))

        self._algo_tree = self._make_tree_widget(
            algo_lf,
            hierarchy_keys=["algorithm", "tuning"],
            on_change=self._update_thread_filter,
        )

        # ── Threads ───────────────────────────────────────────────────────
        thread_lf = ttk.LabelFrame(parent, text="Threads")
        thread_lf.pack(fill=tk.X, pady=(0, 5))

        self._thread_tree = self._make_tree_widget(
            thread_lf,
            hierarchy_keys=["_thread_display", "_algo_label"],
            on_change=None,
        )

        # ── Axes ──────────────────────────────────────────────────────────
        ax_sec = ttk.LabelFrame(parent, text="Axes")
        ax_sec.pack(fill=tk.X, pady=(0, 5))

        ax_sec.columnconfigure(1, weight=1)

        self._x_var = tk.StringVar(value="rank_error_mean")
        self._y_var = tk.StringVar(value="extra_work_mean")

        for row, lbl, var in [
            (0, "X axis:", self._x_var),
            (1, "Y axis:", self._y_var),
        ]:

            ttk.Label(ax_sec, text=lbl).grid(
                row=row,
                column=0,
                padx=(8, 4),
                pady=(6 if row == 0 else 2, 2),
                sticky="w",
            )

            ttk.Combobox(
                ax_sec,
                textvariable=var,
                values=ALL_METRICS,
                state="readonly",
            ).grid(
                row=row,
                column=1,
                padx=(0, 8),
                pady=(6 if row == 0 else 2, 2),
                sticky="ew",
            )

        scale_row = ttk.Frame(ax_sec)

        scale_row.grid(
            row=2,
            column=0,
            columnspan=2,
            padx=8,
            pady=(0, 6),
            sticky="w",
        )

        self._logx_var = tk.BooleanVar()
        self._logy_var = tk.BooleanVar()

        ttk.Checkbutton(
            scale_row,
            text="Log X",
            variable=self._logx_var,
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Checkbutton(
            scale_row,
            text="Log Y",
            variable=self._logy_var,
        ).pack(side=tk.LEFT)

        # ── Color By ──────────────────────────────────────────────────────
        col_sec = ttk.LabelFrame(parent, text="Color By")
        col_sec.pack(fill=tk.X, pady=(0, 5))

        self._color_var = tk.StringVar(value="algorithm")

        # Radio buttons: 3 per row
        n_opts = len(COLOR_BY_OPTIONS)
        n_rows = (n_opts + 2) // 3

        for idx, (val, lbl) in enumerate(COLOR_BY_OPTIONS):
            ttk.Radiobutton(
                col_sec,
                text=lbl,
                variable=self._color_var,
                value=val,
                command=self._on_color_by_change,
            ).grid(
                row=idx // 3,
                column=idx % 3,
                padx=6,
                pady=4,
                sticky="w",
            )

        # ── Metric-scale sub-controls (shown only when "Metric Scale" picked) ──
        self._metric_options_frame = ttk.Frame(col_sec)
        self._metric_options_frame.grid(
            row=n_rows,
            column=0,
            columnspan=3,
            padx=4,
            pady=(0, 6),
            sticky="ew",
        )

        col_sec.columnconfigure(0, weight=1)
        col_sec.columnconfigure(1, weight=1)
        col_sec.columnconfigure(2, weight=1)
        self._metric_options_frame.columnconfigure(1, weight=1)

        ttk.Label(self._metric_options_frame, text="Metric:").grid(
            row=0, column=0, padx=(4, 4), pady=(2, 2), sticky="w",
        )

        self._metric_color_var = tk.StringVar(value="extra_work_mean")
        ttk.Combobox(
            self._metric_options_frame,
            textvariable=self._metric_color_var,
            values=ALL_METRICS,
            state="readonly",
        ).grid(row=0, column=1, columnspan=2, padx=(0, 4), pady=(2, 2), sticky="ew")

        ttk.Label(self._metric_options_frame, text="Colormap:").grid(
            row=1, column=0, padx=(4, 4), pady=(2, 4), sticky="w",
        )

        self._cmap_var = tk.StringVar(value=CMAP_NAMES[0])
        self._cmap_combo = ttk.Combobox(
            self._metric_options_frame,
            textvariable=self._cmap_var,
            values=CMAP_LABELS,
            state="readonly",
        )
        self._cmap_combo.current(0)
        self._cmap_combo.grid(
            row=1, column=1, columnspan=2, padx=(0, 4), pady=(2, 4), sticky="ew",
        )

        # Keep cmap display labels in sync with internal name
        self._cmap_combo.bind(
            "<<ComboboxSelected>>",
            self._on_cmap_selected,
        )

        # Initially hide the metric sub-controls
        self._metric_options_frame.grid_remove()

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = ttk.Frame(parent)

        btn_row.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        ttk.Button(
            btn_row,
            text="⤓  Export PDF",
            command=self._export_pdf,
        ).grid(row=0, column=0, sticky="nsew", padx=(0, 1), pady=2)

        ttk.Button(
            btn_row,
            text="⤓  Export PNG",
            command=self._export_png,
        ).grid(row=0, column=1, sticky="nsew", padx=(1, 0), pady=2)

        ttk.Button(
            btn_row,
            text="⟳  Plot",
            style="Accent.TButton",
            command=self._plot,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=0,
            pady=2,
        )

    # ---------------------------------------------------------------------

    def _on_color_by_change(self) -> None:
        """Show or hide the metric sub-controls based on the Color By selection."""
        if self._color_var.get() == "metric":
            self._metric_options_frame.grid()
        else:
            self._metric_options_frame.grid_remove()

    def _on_cmap_selected(self, _event=None) -> None:
        """Sync the internal cmap name when the user picks a display label."""
        idx = CMAP_LABELS.index(self._cmap_combo.get())
        self._cmap_var.set(CMAP_NAMES[idx])

    # ---------------------------------------------------------------------

    def _make_tree_widget(
        self,
        parent_lf: ttk.LabelFrame,
        hierarchy_keys: list,
        on_change=None,
    ):

        ctrl = tk.Frame(parent_lf, bg=C["bg"])
        ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        tree = SelectionTree(
            parent_lf,
            hierarchy_keys=hierarchy_keys,
            on_change=on_change,
            restore_scroll=self._restore_canvas_scroll,
            tree_height=7,
        )

        tree.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(ctrl, text="All", width=5, command=tree.check_all).pack(
            side=tk.LEFT,
            padx=(0, 2),
        )

        ttk.Button(ctrl, text="None", width=5, command=tree.uncheck_all).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )

        ttk.Button(ctrl, text="Expand", width=8, command=tree.expand_all).pack(
            side=tk.LEFT,
            padx=(0, 2),
        )

        ttk.Button(ctrl, text="Collapse", width=8, command=tree.collapse_all).pack(
            side=tk.LEFT
        )

        return tree

    # ---------------------------------------------------------------------

    @staticmethod
    def _seed_label(r: dict) -> str:
        seed = str(r.get("seed") or "").strip()
        return seed if seed else UNSEEDED

    # ---------------------------------------------------------------------

    @staticmethod
    def _thread_display(r: dict) -> str:
        """Canonical thread label for a record; falls back to 't1'."""
        threads = str(r.get("threads") or "").strip()
        return threads if threads else "t1"

    @staticmethod
    def _algo_label(r: dict) -> str:
        """Display label combining algorithm and tuning for the thread tree."""
        algo   = str(r.get("algorithm") or NA)
        tuning = str(r.get("tuning") or "").strip()
        if tuning and tuning.lower() not in ("none", "(none)"):
            return f"{algo} · {tuning}"
        return algo

    def _augment_for_thread_tree(self, records: list) -> list:
        """
        Return records with two extra keys injected:
          _thread_display  –  e.g. "t1", "t4", "t32"
          _algo_label      –  e.g. "klsm", "klsm · lsm4"
        These drive the two-level hierarchy in the Thread tree.
        """
        augmented = []
        for r in records:
            a = dict(r)
            a["_thread_display"] = self._thread_display(r)
            a["_algo_label"]     = self._algo_label(r)
            augmented.append(a)
        return augmented

    # ---------------------------------------------------------------------

    def _populate_seeds(self, records: list, preserve: set = None) -> None:

        for w in self._seed_container.winfo_children():
            w.destroy()

        self._seed_vars.clear()

        for i in range(4):
            self._seed_container.columnconfigure(
                i,
                weight=1,
                uniform="seed_cols",
            )

        seeds = sorted({
            self._seed_label(r)
            for r in records
        })

        if UNSEEDED in seeds and len(seeds) > 1:
            seeds = [s for s in seeds if s != UNSEEDED] + [UNSEEDED]

        for idx, seed_val in enumerate(seeds):

            checked = True if preserve is None else (seed_val in preserve)

            var = tk.BooleanVar(value=checked)

            self._seed_vars[seed_val] = var

            cb = ttk.Checkbutton(
                self._seed_container,
                text=seed_val,
                variable=var,
            )

            cb.grid(
                row=idx // 4,
                column=idx % 4,
                padx=4,
                pady=2,
                sticky="w",
            )

    # ---------------------------------------------------------------------

    def _check_all_seeds(self) -> None:
        for v in self._seed_vars.values():
            v.set(True)

    def _uncheck_all_seeds(self) -> None:
        for v in self._seed_vars.values():
            v.set(False)

    # ---------------------------------------------------------------------

    def _update_dependent_filters(self) -> None:
        """Called when the Graph Config tree changes."""

        if not self._records:
            return

        config_selected = sorted(
            self._config_tree.get_selected_indices()
        )

        config_records = [
            self._records[i]
            for i in config_selected
        ]

        prev_seeds = {
            s
            for s, var in self._seed_vars.items()
            if var.get()
        }

        self._populate_seeds(config_records, preserve=prev_seeds)

        self._algo_tree.populate(
            config_records,
            index_map=config_selected,
            default_state=0,
        )

        self._update_thread_filter()

    # ---------------------------------------------------------------------

    def _update_thread_filter(self) -> None:
        """Called when the Algorithm tree changes."""

        if not self._records or self._thread_tree is None:
            return

        algo_selected = sorted(
            self._algo_tree.get_selected_indices()
        )

        algo_records = [
            self._records[i]
            for i in algo_selected
        ]

        augmented = self._augment_for_thread_tree(algo_records)

        self._thread_tree.populate(
            augmented,
            index_map=algo_selected,
            default_state=2,
        )

    # ---------------------------------------------------------------------

    def _build_right(self, parent: ttk.Frame) -> None:

        self._fig = Figure(facecolor=C["bg"])

        self._ax = self._fig.add_subplot(
            111,
            facecolor=C["panel"],
        )

        self._style_axes(self._ax)

        self._mpl_canvas = FigureCanvasTkAgg(
            self._fig,
            master=parent,
        )

        self._mpl_canvas.get_tk_widget().pack(
            fill=tk.BOTH,
            expand=True,
        )

        self._status_var = tk.StringVar(
            value="Load a directory to begin."
        )

        ttk.Label(
            parent,
            textvariable=self._status_var,
            foreground=C["subtext"],
        ).pack(anchor="w", padx=4, pady=(4, 0))

    # ---------------------------------------------------------------------

    def _style_axes(self, ax) -> None:

        ax.tick_params(colors=C["text"], labelsize=9)

        for spine in ax.spines.values():
            spine.set_edgecolor(C["border"])

        ax.grid(
            True,
            color=C["surface1"],
            linestyle="--",
            linewidth=0.6,
            zorder=0,
        )

        ax.set_facecolor(C["panel"])

    # ---------------------------------------------------------------------

    def _browse_dir(self) -> None:

        directory = filedialog.askdirectory(
            title="Select benchmark output directory"
        )

        if not directory:
            return

        self._dir_label.configure(
            text=directory,
            foreground=C["text"],
        )

        self._records = scan_directory(directory)

        if not self._records:

            messagebox.showwarning(
                "No Files Found",
                "No *_globals.json files were found in the selected directory.",
            )

            return

        self._config_tree.populate(self._records)
        self._algo_tree.populate(self._records, default_state=0)
        self._thread_tree.populate([], default_state=2)
        self._populate_seeds(self._records)

        self._status_var.set(
            f"Loaded {len(self._records)} files."
        )

    # ---------------------------------------------------------------------

    def _filtered_records(self) -> list:

        if not self._records:
            return []

        config_idx = self._config_tree.get_selected_indices()
        algo_idx   = self._algo_tree.get_selected_indices()
        thread_idx = (
            self._thread_tree.get_selected_indices()
            if self._thread_tree is not None
            else set()
        )

        both = config_idx & algo_idx & thread_idx

        selected_seeds = {
            s
            for s, var in self._seed_vars.items()
            if var.get()
        }

        result = []

        for i in sorted(both):

            r = self._records[i]

            if self._seed_label(r) in selected_seeds:
                result.append(r)

        return result

    # ---------------------------------------------------------------------

    def _active_families_str(self, records: list) -> str:

        fams = sorted({
            str(r.get("family") or NA)
            for r in records
        })

        if not fams:
            return "None"

        if len(fams) == 1:
            return fams[0]

        if len(fams) <= 3:
            return ", ".join(fams)

        return f"Multiple ({len(fams)})"

    # ---------------------------------------------------------------------

    def _default_export_stem(self) -> str:

        records = self._filtered_records()

        x_key = self._x_var.get()
        y_key = self._y_var.get()

        color_by = self._color_var.get()

        fam_str = (
            self._active_families_str(records)
            .replace(" ", "_")
            .replace(",", "")
        )

        return f"{fam_str}_{x_key}_vs_{y_key}_by_{color_by}"

    # ---------------------------------------------------------------------

    def _export_png(self) -> None:

        path = filedialog.asksaveasfilename(
            title="Export plot as PNG",
            initialfile=self._default_export_stem() + ".png",
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            orig_size = self._fig.get_size_inches()
            self._fig.set_size_inches(
                EXPORT_WIDTH_MM / 25.4,
                EXPORT_HEIGHT_MM / 25.4,
            )

            self._fig.savefig(
                path,
                dpi=200,
                bbox_inches="tight",
                facecolor="white",
            )

            self._fig.set_size_inches(*orig_size)
            self._mpl_canvas.draw()

            self._status_var.set(f"Exported → {path}")

        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ---------------------------------------------------------------------

    def _export_pdf(self) -> None:

        path = filedialog.asksaveasfilename(
            title="Export plot as PDF",
            initialfile=self._default_export_stem() + ".pdf",
            defaultextension=".pdf",
            filetypes=[
                ("PDF document", "*.pdf"),
                ("All files", "*.*"),
            ],
        )

        if not path:
            return

        try:
            from matplotlib.backends.backend_pdf import PdfPages

            orig_size = self._fig.get_size_inches()
            self._fig.set_size_inches(
                EXPORT_WIDTH_MM / 25.4,
                EXPORT_HEIGHT_MM / 25.4,
            )

            with PdfPages(path) as pdf:

                pdf.savefig(
                    self._fig,
                    bbox_inches="tight",
                    facecolor="white",
                )

                d = pdf.infodict()

                d["Title"]   = self._ax.get_title() or "PQ Benchmark Plot"
                d["Creator"] = "PQ Benchmark Visualizer"

            self._fig.set_size_inches(*orig_size)
            self._mpl_canvas.draw()

            self._status_var.set(f"Exported → {path}")

        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ---------------------------------------------------------------------

    def auto_linthresh(self, values, default=1.0):

        nonzero = [abs(v) for v in values if v != 0]

        if not nonzero:
            return default

        return min(nonzero) * 0.5

    # ---------------------------------------------------------------------

    def _remove_colorbar(self) -> None:
        """Remove the colorbar if one is currently displayed."""
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None

    # ---------------------------------------------------------------------

    def _plot_metric_color(
        self,
        ax,
        records: list,
        x_key: str,
        y_key: str,
    ) -> None:
        """
        Render a scatter plot where point color encodes a continuous metric
        value (selected via the Metric dropdown) on a scientific colormap.
        Marker shape still encodes algorithm.  A colorbar is added to the
        figure and a shape legend for algorithms is drawn on the axes.
        """

        metric_key = self._metric_color_var.get()
        cmap_name  = self._cmap_var.get()

        # ------------------------------------------------------------------
        # Collect metric values; treat missing / None as NaN so we can
        # still plot the point (it will appear grey via set_bad).
        # ------------------------------------------------------------------
        import math

        metric_values = []
        for r in records:
            v = r.get(metric_key)
            metric_values.append(float(v) if v is not None else float("nan"))

        finite = [v for v in metric_values if not math.isnan(v)]

        if finite:
            vmin, vmax = min(finite), max(finite)
            # Give a tiny range if all values are identical
            if vmin == vmax:
                vmin -= 0.5
                vmax += 0.5
        else:
            vmin, vmax = 0.0, 1.0

        norm = _mpl_colors.Normalize(vmin=vmin, vmax=vmax)

        try:
            cmap = _mpl_cm.get_cmap(cmap_name)
        except Exception:
            cmap = _mpl_cm.get_cmap("plasma")

        cmap.set_bad(color=C["muted"])   # NaN → muted grey

        # ------------------------------------------------------------------
        # Group by algorithm so each gets its own marker shape.
        # ------------------------------------------------------------------

        algo_buckets: dict[str, list] = {}
        algo_metric:  dict[str, list] = {}

        for rec, mv in zip(records, metric_values):
            algo = str(rec.get("algorithm") or "").lower()
            algo_buckets.setdefault(algo, []).append(rec)
            algo_metric.setdefault(algo, []).append(mv)

        last_sc = None  # used to attach the colorbar

        for algo in sorted(algo_buckets):

            subset = algo_buckets[algo]
            vals   = algo_metric[algo]

            xs = [r[x_key] for r in subset]
            ys = [r[y_key] for r in subset]

            marker = algo_marker(algo)

            sc = ax.scatter(
                xs,
                ys,
                c=vals,
                cmap=cmap,
                norm=norm,
                marker=marker,
                s=72,
                alpha=0.88,
                edgecolors="white",
                linewidths=0.5,
                zorder=3,
            )

            sc._pq_records = subset
            self._scatter_collections.append(sc)
            last_sc = sc

        # ------------------------------------------------------------------
        # Colorbar
        # ------------------------------------------------------------------

        if last_sc is not None:
            self._colorbar = self._fig.colorbar(
                last_sc,
                ax=ax,
                fraction=0.035,
                pad=0.02,
            )

            cb_label = METRIC_LABELS.get(metric_key, metric_key)
            self._colorbar.set_label(
                cb_label,
                color=C["text"],
                fontsize=10,
            )

            self._colorbar.ax.tick_params(
                colors=C["text"],
                labelsize=8,
            )

            self._colorbar.outline.set_edgecolor(C["border"])

        # ------------------------------------------------------------------
        # Shape legend (algorithm → marker)
        # ------------------------------------------------------------------

        shape_handles = {}

        for algo in sorted(algo_buckets):
            shape_handles[algo] = Line2D(
                [0], [0],
                marker=algo_marker(algo),
                linestyle="",
                color=C["subtext"],
                markeredgecolor="white",
                markersize=8,
                label=algo if algo else NA,
            )

        if shape_handles:
            leg = ax.legend(
                handles=list(shape_handles.values()),
                title="Algorithm",
                facecolor=C["panel"],
                edgecolor=C["border"],
                labelcolor=C["text"],
                title_fontsize=9,
                fontsize=9,
                framealpha=0.95,
                loc="best",
            )
            leg.get_title().set_color(C["blue"])
            leg.get_title().set_fontweight("bold")

    # ---------------------------------------------------------------------

    def _plot(self) -> None:

        records = self._filtered_records()

        x_key = self._x_var.get()
        y_key = self._y_var.get()

        color_by = self._color_var.get()

        records = [
            r
            for r in records
            if x_key in r and y_key in r
        ]

        if not records:

            messagebox.showwarning(
                "No Data",
                "No records match the current filters.",
            )

            return

        # Remove any existing colorbar first, then wipe the whole figure so
        # that the axes geometry is fully reset.  Using ax.clear() alone is
        # not enough: fig.colorbar() shrinks the axes via make_axes() and that
        # change persists across clear() calls, causing the plot to shrink a
        # little more on every re-plot.  Clearing the figure and re-adding the
        # subplot gives us a guaranteed clean slate every time.
        self._remove_colorbar()
        self._fig.clear()
        self._ax = self._fig.add_subplot(111, facecolor=C["panel"])
        ax = self._ax

        self._style_axes(ax)
        self._scatter_collections.clear()

        # ------------------------------------------------------------------
        # Axis scales
        # ------------------------------------------------------------------

        if self._logx_var.get():
            x_values = [r[x_key] for r in records]
            ax.set_xscale("symlog", linthresh=self.auto_linthresh(x_values))

        if self._logy_var.get():
            y_values = [r[y_key] for r in records]
            ax.set_yscale("symlog", linthresh=self.auto_linthresh(y_values))

        # ------------------------------------------------------------------
        # Branch: continuous metric coloring vs. categorical coloring
        # ------------------------------------------------------------------

        if color_by == "metric":
            self._plot_metric_color(ax, records, x_key, y_key)

            metric_key  = self._metric_color_var.get()
            cmap_name   = self._cmap_var.get()
            color_label = (
                f"metric scale  ·  {METRIC_LABELS.get(metric_key, metric_key)}"
                f"  ·  {cmap_name}"
            )

        else:
            # ── Categorical coloring (original behaviour) ─────────────────
            groups = sorted({
                get_color_key(r, color_by)
                for r in records
            })

            color_map = {
                g: SCATTER_PALETTE[i % len(SCATTER_PALETTE)]
                for i, g in enumerate(groups)
            }

            legend_color_handles = {}

            for group in groups:

                subset = [
                    r for r in records
                    if get_color_key(r, color_by) == group
                ]

                algos_in_group = {
                    str(r.get("algorithm") or "").lower()
                    for r in subset
                }

                group_marker = (
                    algo_marker(algos_in_group.pop())
                    if len(algos_in_group) == 1
                    else _FALLBACK_MARKER
                )

                algo_buckets: dict[str, list] = {}
                for r in subset:
                    algo = str(r.get("algorithm") or "").lower()
                    algo_buckets.setdefault(algo, []).append(r)

                for algo, algo_subset in algo_buckets.items():

                    xs = [r[x_key] for r in algo_subset]
                    ys = [r[y_key] for r in algo_subset]

                    sc = ax.scatter(
                        xs,
                        ys,
                        color=color_map[group],
                        marker=algo_marker(algo),
                        s=72,
                        alpha=0.85,
                        edgecolors="white",
                        linewidths=0.5,
                        zorder=3,
                    )

                    sc._pq_records = algo_subset
                    self._scatter_collections.append(sc)

                    if group not in legend_color_handles:
                        legend_color_handles[group] = Line2D(
                            [0], [0],
                            marker=group_marker,
                            linestyle="",
                            markerfacecolor=color_map[group],
                            markeredgecolor="white",
                            markersize=8,
                            label=group,
                        )

            color_by_label = dict(COLOR_BY_OPTIONS).get(
                color_by, color_by.capitalize()
            )

            leg1 = ax.legend(
                handles=list(legend_color_handles.values()),
                title=color_by_label,
                facecolor=C["panel"],
                edgecolor=C["border"],
                labelcolor=C["text"],
                title_fontsize=9,
                fontsize=9,
                framealpha=0.95,
                loc="best",
            )

            leg1.get_title().set_color(C["blue"])
            leg1.get_title().set_fontweight("bold")

            ax.add_artist(leg1)

            color_label = f"colored by {color_by_label}"

        # ------------------------------------------------------------------
        # Labels & title (shared)
        # ------------------------------------------------------------------

        ax.set_xlabel(
            METRIC_LABELS.get(x_key, x_key),
            color=C["text"],
            fontsize=11,
            labelpad=8,
        )

        ax.set_ylabel(
            METRIC_LABELS.get(y_key, y_key),
            color=C["text"],
            fontsize=11,
            labelpad=8,
        )

        fam_str = self._active_families_str(records)

        ax.set_title(
            f"Family: {fam_str}   ·   "
            f"{METRIC_LABELS.get(x_key, x_key)} vs "
            f"{METRIC_LABELS.get(y_key, y_key)}",
            color=C["text"],
            fontsize=11,
            pad=12,
            fontweight="bold",
        )

        # ------------------------------------------------------------------

        self._fig.tight_layout()
        self._mpl_canvas.draw()

        # ------------------------------------------------------------------
        # Hover tooltips
        # ------------------------------------------------------------------

        if HAS_MPLCURSORS:

            cursor = mplcursors.cursor(
                self._scatter_collections,
                hover=True,
            )

            @cursor.connect("add")
            def on_add(sel):

                rec = sel.artist._pq_records[sel.index]

                metric_key = self._metric_color_var.get()

                lines = [
                    f"File:      {rec.get('filename', '?')}",
                    f"Family:    {rec.get('family', NA)}",
                    f"Size/Area: {rec.get('size', NA)}",
                    f"Seed:      {self._seed_label(rec)}",
                    f"Algorithm: {rec.get('algorithm', NA)}",
                    f"Tuning:    {rec.get('tuning', NA)}",
                    f"Threads:   {self._thread_display(rec)}",
                    "",
                    f"{METRIC_LABELS.get(x_key, x_key)}: "
                    f"{rec.get(x_key, '?'):.4g}",
                    f"{METRIC_LABELS.get(y_key, y_key)}: "
                    f"{rec.get(y_key, '?'):.4g}",
                ]

                # Show the color metric when in metric-scale mode
                if color_by == "metric":
                    cv = rec.get(metric_key)
                    cv_str = f"{cv:.4g}" if cv is not None else "N/A"
                    lines.append(
                        f"{METRIC_LABELS.get(metric_key, metric_key)}: {cv_str}  ← color"
                    )

                sel.annotation.set_text("\n".join(lines))

                sel.annotation.get_bbox_patch().set(
                    facecolor=C["panel"],
                    edgecolor=C["accent"],
                    alpha=0.95,
                )

                sel.annotation.set_fontsize(8.5)
                sel.annotation.set_color(C["text"])

        self._status_var.set(
            f"{len(records)} points plotted  ·  "
            f"{color_label}  ·  "
            f"x = {x_key}  ·  y = {y_key}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()