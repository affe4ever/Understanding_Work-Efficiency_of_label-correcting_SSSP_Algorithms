#!/usr/bin/env python3
"""
PQ Benchmark Visualizer
=======================
Light theme · scrollable left panel · Graph Config tree (family > size) ·
Algorithm tree (algorithm > tuning > threads) below Seed/Area selector ·
Seed and Algorithm selectors update dynamically from Graph Config selection ·
USA-road area codes parsed as `size` · "unseeded" for seed-less records.

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

try:
    import mplcursors
    HAS_MPLCURSORS = True
except ImportError:
    HAS_MPLCURSORS = False


# ─────────────────────────────────────────────────────────────────────────────
# Filename parser
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_ALGOS = ["capq", "drpq", "klsm", "smq", "mq"]
NA       = "(none)"
UNSEEDED = "unseeded"


def parse_filename(path: str) -> dict:
    """
    Parse a *_globals.json (or *_summary.csv) path into structured metadata.

    Patterns handled
    ----------------
    grid_graph_X{n}_Y{m}_s{seed}_{algo}{digits?}_{tuning?}_{threads?}_globals.json
    {family}_{size}_{algo}{digits?}_{tuning?}_{threads?}_globals.json
      For rhg: {family}_{size}[_deg{digits}]_s{seed}_{algo}...
    {Family}.{AREA}_{algo}_{tuning?}_{threads?}_globals.json   dot-separated (USA-road)
      → AREA is stored as `size` (not `seed`) so it appears in the Graph Config tree.
    Note: For rhg files, deg{digits} is included as part of the size (e.g., rhg_24_deg8_s1...).
    """
    base = os.path.basename(path)
    base = re.sub(r"\.(json|csv)$", "", base)
    base = re.sub(r"_(globals|summary)$", "", base)

    info = dict(family=None, size=None, seed=None,
                algorithm=None, tuning=None, threads=None,
                filepath=path, filename=os.path.basename(path))
    rest = base

    # Dot-separated: Family.AREA_... (e.g. USA-road.NY_capq_t4_globals.json)
    dot_m = re.match(r"([A-Za-z0-9][A-Za-z0-9\-]*)\.([A-Za-z0-9]+)_(.*)", rest)
    if dot_m:
        info["family"] = dot_m.group(1)
        info["size"]   = dot_m.group(2)   # area code goes to size, not seed
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
                info["family"], info["size"], rest = m.group(1), m.group(2), m.group(3)
                # For rhg files, also consume deg{digits} as part of the size
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
            tuning_parts: list = [digit_suffix] if digit_suffix else []
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
    "rank_error_min",           "rank_error_max",           "rank_error_mean",
    "delay_min",                "delay_max",                "delay_mean",
    "pq_size_min",              "pq_size_max",              "pq_size_mean",
    "ignored_node_min",         "ignored_node_max",         "ignored_node_mean",
    "extra_work_min",           "extra_work_max",           "extra_work_mean",
    "extra_work_generated_min", "extra_work_generated_max", "extra_work_generated_mean",
]
METRIC_LABELS = {m: m.replace("_", " ").title() for m in ALL_METRICS}


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
# Light colour palette
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
    "#228be6", "#f76707", "#2f9e44", "#ae3ec9", "#f59f00",
    "#c92a2a", "#0c8599", "#d6336c", "#74b816", "#5c7cfa",
    "#3bc9db", "#ff6b6b", "#51cf66", "#cc5de8", "#fcc419",
]

COLOR_BY_OPTIONS = [
    ("family",    "Graph Family"),
    ("algorithm", "Algorithm"),
    ("size",      "Size / Area"),
    ("seed",      "Seed"),
    ("tuning",    "Tuning"),
    ("threads",   "Threads"),
]


def get_color_key(record: dict, color_by: str) -> str:
    """
    Return a composite legend/grouping key that avoids ambiguity.
    Seed-less records show as 'unseeded'.
    """
    family  = str(record.get("family")    or NA)
    size    = str(record.get("size")      or NA)
    seed    = str(record.get("seed")      or "").strip()
    algo    = str(record.get("algorithm") or NA)
    tuning  = str(record.get("tuning")    or NA)
    threads = str(record.get("threads")   or NA)
    seed_display = seed if seed else UNSEEDED

    if color_by == "seed":
        ctx = " / ".join(p for p in [family, size] if p != NA)
        return f"{ctx}  \u00b7  {seed_display}" if ctx else seed_display
    elif color_by == "size":
        return f"{family} / {size}"
    elif color_by == "tuning":
        return f"{algo}  \u00b7  {tuning}"
    elif color_by == "family":    return family
    elif color_by == "algorithm": return algo
    elif color_by == "threads":   return threads
    else:
        return str(record.get(color_by) or NA)


# ─────────────────────────────────────────────────────────────────────────────
# Configurable nested selection tree
# ─────────────────────────────────────────────────────────────────────────────

class SelectionTree(tk.Frame):
    """
    Scrollable nested Treeview checklist with tri-state checkboxes.

    Parameters
    ----------
    hierarchy_keys : list of record keys defining nesting order.
    on_change      : optional callable fired (via after_idle) on any state change.
    restore_scroll : optional callable that re-binds MouseWheel to the outer
                     scrollable canvas after the tree releases focus.
    tree_height    : number of visible rows in the Treeview widget.

    populate(records, index_map=None)
        index_map: parallel list of *global* record indices so that
        get_selected_indices() always returns indices into App._records,
        even when the tree is repopulated with a filtered subset.
    """

    ICONS = {2: "\u2611 ", 1: "\u25a0 ", 0: "\u2610 "}

    def __init__(self, parent, hierarchy_keys: list,
                 on_change=None, restore_scroll=None, tree_height: int = 7, **kw):
        super().__init__(parent, bg=C["panel"], **kw)
        self.hierarchy_keys  = hierarchy_keys
        self.on_change       = on_change
        self._restore_scroll = restore_scroll
        self.nodes: dict     = {}

        self.tree = ttk.Treeview(self, selectmode="none", show="tree",
                                  height=tree_height)
        vsb = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Enter>",    self._on_tree_enter)
        self.tree.bind("<Leave>",    self._on_tree_leave)

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, records: list, index_map: list = None) -> None:
        """
        Rebuild the tree from *records*.

        index_map
            If given, index_map[i] is the global App._records index for
            records[i].  If None, local positions 0..N-1 are used as indices.
        """
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()

        for pos, r in enumerate(records):
            global_idx = index_map[pos] if index_map is not None else pos

            node_id_parts: list = []
            display_parts: list = []
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
                        state=2, text=display_parts[depth],
                        is_leaf=False, record_indices=[])
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
        """Return the set of global record indices that are fully checked."""
        result = set()
        for nid, data in self.nodes.items():
            if data["is_leaf"] and data["state"] == 2:
                result.update(data["record_indices"])
        return result

    # ── Scroll hand-off ───────────────────────────────────────────────────────

    def _on_tree_enter(self, _e) -> None:
        self.tree.bind_all("<MouseWheel>", self._on_scroll)

    def _on_tree_leave(self, _e) -> None:
        self.tree.unbind_all("<MouseWheel>")
        if self._restore_scroll:
            self._restore_scroll()

    def _on_scroll(self, event) -> None:
        self.tree.yview_scroll(-int(event.delta / 120), "units")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_click(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return   # let Treeview handle expand/collapse natively
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
        child_states = [self.nodes[c]["state"] for c in self.tree.get_children(parent)]
        if all(s == 2 for s in child_states):   new = 2
        elif all(s == 0 for s in child_states): new = 0
        else:                                    new = 1
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

        self._records: list              = []
        self._scatter_collections: list  = []
        self._seed_vars: dict            = {}
        self._config_tree: SelectionTree = None
        self._algo_tree:   SelectionTree = None
        self._restore_canvas_scroll      = None   # set in _build_left

        self._setup_style()
        self._build_ui()

    # ── Style ─────────────────────────────────────────────────────────────────

    def _setup_style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".",
                    background=C["bg"], foreground=C["text"],
                    font=("Segoe UI", 10), relief="flat", borderwidth=0)
        s.configure("TFrame",  background=C["bg"])
        s.configure("TLabel",  background=C["bg"], foreground=C["text"])

        s.configure("TButton",
                    background=C["surface1"], foreground=C["text"],
                    padding=(8, 4), borderwidth=1, relief="flat")
        s.map("TButton",
              background=[("active", C["accent"]), ("pressed", C["blue"])],
              foreground=[("active", "white")])

        s.configure("Accent.TButton",
                    background=C["accent"], foreground="white",
                    font=("Segoe UI", 10, "bold"), padding=(12, 6))
        s.map("Accent.TButton",
              background=[("active", C["blue"]), ("pressed", C["blue"])],
              foreground=[("active", "white")])

        s.configure("TCombobox",
                    fieldbackground=C["panel"], background=C["surface1"],
                    foreground=C["text"], arrowcolor=C["blue"], padding=4)
        s.map("TCombobox",
              fieldbackground=[("readonly", C["panel"])],
              foreground=[("readonly", C["text"])])

        s.configure("TCheckbutton", background=C["bg"], foreground=C["text"])
        s.map("TCheckbutton",
              background=[("active", C["bg"])],
              indicatorcolor=[("selected", C["accent"]), ("!selected", C["surface2"])])

        s.configure("TRadiobutton", background=C["bg"], foreground=C["text"])
        s.map("TRadiobutton",
              background=[("active", C["bg"])],
              indicatorcolor=[("selected", C["accent"])])

        s.configure("TLabelframe",
                    background=C["bg"], bordercolor=C["border"],
                    relief="groove", borderwidth=1)
        s.configure("TLabelframe.Label",
                    background=C["bg"], foreground=C["blue"],
                    font=("Segoe UI", 9, "bold"))

        s.configure("Treeview",
                    background=C["panel"], fieldbackground=C["panel"],
                    foreground=C["text"], rowheight=24, borderwidth=0)
        s.map("Treeview",
              background=[("selected", C["blue_lt"])],
              foreground=[("selected", C["text"])])

        s.configure("TScrollbar",
                    background=C["surface1"], troughcolor=C["bg"],
                    arrowcolor=C["subtext"], gripcount=0)

    # ── Top-level layout ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left  = ttk.Frame(pane, width=430)
        right = ttk.Frame(pane)
        pane.add(left,  weight=0)
        pane.add(right, weight=1)
        self._build_left(left)
        self._build_right(right)

    # ── Left panel — scrollable wrapper ───────────────────────────────────────

    def _build_left(self, parent: ttk.Frame) -> None:
        parent.pack_propagate(False)

        # Canvas + scrollbar that wraps all left-panel content
        scroll_canvas = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(scroll_canvas, bg=C["bg"])
        cwin  = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        # Keep scroll region and inner width in sync with canvas size
        inner.bind("<Configure>",
                   lambda _e: scroll_canvas.configure(
                       scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>",
                           lambda e: scroll_canvas.itemconfig(cwin, width=e.width))

        # MouseWheel: canvas handles it unless a tree has taken over
        def _canvas_scroll(e):
            scroll_canvas.yview_scroll(-int(e.delta / 120), "units")

        def restore_canvas_scroll():
            scroll_canvas.bind_all("<MouseWheel>", _canvas_scroll)

        scroll_canvas.bind("<Enter>", lambda _: restore_canvas_scroll())
        scroll_canvas.bind("<Leave>", lambda _: scroll_canvas.unbind_all("<MouseWheel>"))

        # Store so _make_tree_widget can pass it to SelectionTree instances
        self._restore_canvas_scroll = restore_canvas_scroll

        self._build_left_content(inner)

    # ── Left panel — content ───────────────────────────────────────────────────

    def _build_left_content(self, parent: tk.Frame) -> None:

        # ── Directory picker ───────────────────────────────────────────────────
        dir_sec = ttk.LabelFrame(parent, text="Data Directory")
        dir_sec.pack(fill=tk.X, pady=(0, 5), ipady=2)
        self._dir_label = ttk.Label(dir_sec, text="(none selected)",
                                    foreground=C["subtext"], wraplength=370)
        self._dir_label.pack(padx=8, pady=(4, 0))
        ttk.Button(dir_sec, text="Browse\u2026",
                   command=self._browse_dir).pack(padx=8, pady=6)

        # ── Graph Config tree  (family → size) ────────────────────────────────
        cfg_lf = ttk.LabelFrame(parent, text="Graph Config")
        cfg_lf.pack(fill=tk.X, pady=(0, 5))
        self._config_tree = self._make_tree_widget(
            cfg_lf,
            hierarchy_keys=["family", "size"],
            on_change=self._update_dependent_filters,
        )

        # ── Seed / Area checkboxes ─────────────────────────────────────────────
        seed_lf = ttk.LabelFrame(parent, text="Seed / Area")
        seed_lf.pack(fill=tk.X, pady=(0, 5))
        seed_ctrl = tk.Frame(seed_lf, bg=C["bg"])
        seed_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))
        ttk.Button(seed_ctrl, text="All",  width=5,
                   command=self._check_all_seeds).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(seed_ctrl, text="None", width=5,
                   command=self._uncheck_all_seeds).pack(side=tk.LEFT)
        self._seed_container = tk.Frame(seed_lf, bg=C["bg"])
        self._seed_container.pack(fill=tk.X, padx=4, pady=(0, 4))

        # ── Algorithm tree  (algorithm → tuning → threads) ────────────────────
        algo_lf = ttk.LabelFrame(parent, text="Algorithm")
        algo_lf.pack(fill=tk.X, pady=(0, 5))
        self._algo_tree = self._make_tree_widget(
            algo_lf,
            hierarchy_keys=["algorithm", "tuning", "threads"],
        )

        # ── Axes ───────────────────────────────────────────────────────────────
        ax_sec = ttk.LabelFrame(parent, text="Axes")
        ax_sec.pack(fill=tk.X, pady=(0, 5))
        ax_sec.columnconfigure(1, weight=1)
        self._x_var = tk.StringVar(value="rank_error_mean")
        self._y_var = tk.StringVar(value="extra_work_mean")
        for row, lbl, var in [(0, "X axis:", self._x_var), (1, "Y axis:", self._y_var)]:
            ttk.Label(ax_sec, text=lbl).grid(
                row=row, column=0, padx=(8, 4),
                pady=(6 if row == 0 else 2, 2), sticky="w")
            ttk.Combobox(ax_sec, textvariable=var, values=ALL_METRICS,
                         state="readonly").grid(
                row=row, column=1, padx=(0, 8),
                pady=(6 if row == 0 else 2, 2), sticky="ew")
        scale_row = ttk.Frame(ax_sec)
        scale_row.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")
        self._logx_var = tk.BooleanVar()
        self._logy_var = tk.BooleanVar()
        ttk.Checkbutton(scale_row, text="Log X", variable=self._logx_var).pack(
            side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(scale_row, text="Log Y", variable=self._logy_var).pack(
            side=tk.LEFT)

        # ── Color by ───────────────────────────────────────────────────────────
        col_sec = ttk.LabelFrame(parent, text="Color By")
        col_sec.pack(fill=tk.X, pady=(0, 5))
        self._color_var = tk.StringVar(value="algorithm")
        for idx, (val, lbl) in enumerate(COLOR_BY_OPTIONS):
            ttk.Radiobutton(col_sec, text=lbl, variable=self._color_var,
                            value=val).grid(row=idx // 3, column=idx % 3,
                                            padx=6, pady=4, sticky="w")

        # ── Action buttons ─────────────────────────────────────────────────────
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_row, text="\u27f3  Plot", style="Accent.TButton",
                   command=self._plot).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=2, padx=(0, 4))
        ttk.Button(btn_row, text="\u2913  Export PNG",
                   command=self._export_png).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

    # ── Helper: build a tree widget with its control row ──────────────────────

    def _make_tree_widget(self, parent_lf: ttk.LabelFrame,
                          hierarchy_keys: list,
                          on_change=None) -> SelectionTree:
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

        ttk.Button(ctrl, text="All",      width=5,  command=tree.check_all   ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(ctrl, text="None",     width=5,  command=tree.uncheck_all ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(ctrl, text="Expand",   width=8,  command=tree.expand_all  ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(ctrl, text="Collapse", width=8,  command=tree.collapse_all).pack(side=tk.LEFT)

        return tree

    # ── Seed helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _seed_label(r: dict) -> str:
        """Return the display label for a record's seed field."""
        seed = str(r.get("seed") or "").strip()
        return seed if seed else UNSEEDED

    def _populate_seeds(self, records: list, preserve: set = None) -> None:
        """
        Rebuild the seed checkbox grid with uniform column widths.
        """
        for w in self._seed_container.winfo_children():
            w.destroy()
        self._seed_vars.clear()

        # Configure 4 columns to be exactly the same width
        for i in range(4):
            self._seed_container.columnconfigure(i, weight=1, uniform="seed_cols")

        seeds = sorted({self._seed_label(r) for r in records})
        # Keep "unseeded" at the end when mixed with real seeds
        if UNSEEDED in seeds and len(seeds) > 1:
            seeds = [s for s in seeds if s != UNSEEDED] + [UNSEEDED]

        for idx, seed_val in enumerate(seeds):
            checked = True if preserve is None else (seed_val in preserve)
            var = tk.BooleanVar(value=checked)
            self._seed_vars[seed_val] = var
            # Use sticky="ew" so the widget area fills the uniform column width
            cb = ttk.Checkbutton(self._seed_container, text=seed_val, variable=var)
            cb.grid(row=idx // 4, column=idx % 4, padx=4, pady=2, sticky="w")

    def _check_all_seeds(self) -> None:
        for v in self._seed_vars.values():
            v.set(True)

    def _uncheck_all_seeds(self) -> None:
        for v in self._seed_vars.values():
            v.set(False)

    # ── Dynamic dependent-filter update ───────────────────────────────────────

    def _update_dependent_filters(self) -> None:
        """
        Called whenever the Graph Config tree changes.
        Repopulates the Seed/Area checkboxes and the Algorithm tree so that
        only options present in the currently selected graph configurations
        are shown.  Existing seed selections are preserved where possible.
        """
        if not self._records:
            return

        # Sorted list of global indices currently selected in the config tree
        config_selected = sorted(self._config_tree.get_selected_indices())
        config_records  = [self._records[i] for i in config_selected]

        # Preserve seed checkbox states across the repopulation
        prev_seeds = {s for s, var in self._seed_vars.items() if var.get()}
        self._populate_seeds(config_records, preserve=prev_seeds)

        # Repopulate algo tree — pass index_map so nodes store global indices,
        # keeping the config ∩ algo intersection in _filtered_records correct.
        self._algo_tree.populate(config_records, index_map=config_selected)

    # ── Right plot panel ───────────────────────────────────────────────────────

    def _build_right(self, parent: ttk.Frame) -> None:
        self._fig = Figure(facecolor=C["bg"])
        self._ax  = self._fig.add_subplot(111, facecolor=C["panel"])
        self._style_axes(self._ax)

        self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=parent)
        self._mpl_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._status_var = tk.StringVar(value="Load a directory to begin.")
        ttk.Label(parent, textvariable=self._status_var,
                  foreground=C["subtext"]).pack(anchor="w", padx=4, pady=(4, 0))

    def _style_axes(self, ax) -> None:
        ax.tick_params(colors=C["text"], labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(C["border"])
        ax.grid(True, color=C["surface1"], linestyle="--", linewidth=0.6, zorder=0)
        ax.set_facecolor(C["panel"])

    # ── Browse / load ──────────────────────────────────────────────────────────

    def _browse_dir(self) -> None:
        directory = filedialog.askdirectory(title="Select benchmark output directory")
        if not directory:
            return

        self._dir_label.configure(text=directory, foreground=C["text"])
        self._records = scan_directory(directory)

        if not self._records:
            messagebox.showwarning(
                "No Files Found",
                "No *_globals.json files were found in the selected directory.")
            return

        # Full initial population — index_map=None → indices are 0..N-1
        self._config_tree.populate(self._records)
        self._algo_tree.populate(self._records)
        self._populate_seeds(self._records)   # preserve=None → all checked
        self._status_var.set(f"Loaded {len(self._records)} files.")

    # ── Filtering ──────────────────────────────────────────────────────────────

    def _filtered_records(self) -> list:
        """
        Return the records that pass all three filters:
          1. Selected in Graph Config tree
          2. Selected in Algorithm tree
          3. Seed matches a checked seed checkbox
        Both trees store global indices, so the intersection is always valid.
        """
        if not self._records:
            return []
        config_idx     = self._config_tree.get_selected_indices()
        algo_idx       = self._algo_tree.get_selected_indices()
        both           = config_idx & algo_idx
        selected_seeds = {s for s, var in self._seed_vars.items() if var.get()}

        result = []
        for i in sorted(both):
            r = self._records[i]
            if self._seed_label(r) in selected_seeds:
                result.append(r)
        return result

    def _active_families_str(self, records: list) -> str:
        fams = sorted({str(r.get("family") or NA) for r in records})
        if not fams:       return "None"
        if len(fams) == 1: return fams[0]
        if len(fams) <= 3: return ", ".join(fams)
        return f"Multiple ({len(fams)})"

    # ── Export ─────────────────────────────────────────────────────────────────

    def _export_png(self) -> None:
        records  = self._filtered_records()
        x_key    = self._x_var.get()
        y_key    = self._y_var.get()
        color_by = self._color_var.get()
        fam_str  = self._active_families_str(records).replace(" ", "_").replace(",", "")
        default  = f"{fam_str}_{x_key}_vs_{y_key}_by_{color_by}.png"

        path = filedialog.asksaveasfilename(
            title="Export plot as PNG",
            initialfile=default,
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._fig.savefig(path, dpi=200, bbox_inches="tight",
                              facecolor="white")
            self._status_var.set(f"Exported \u2192 {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ── Plotting ───────────────────────────────────────────────────────────────
    
    def auto_linthresh(self, values, default=1.0):
        nonzero = [abs(v) for v in values if v != 0]

        if not nonzero:
            return default

        smallest = min(nonzero)

        return smallest * 0.5

    def _plot(self) -> None:
        records  = self._filtered_records()
        x_key    = self._x_var.get()
        y_key    = self._y_var.get()
        color_by = self._color_var.get()

        records = [r for r in records if x_key in r and y_key in r]
        if not records:
            messagebox.showwarning(
                "No Data",
                "No records match the current filters, or the selected "
                "metrics don't appear in the loaded files.")
            return

        groups    = sorted({get_color_key(r, color_by) for r in records})
        color_map = {g: SCATTER_PALETTE[i % len(SCATTER_PALETTE)]
                     for i, g in enumerate(groups)}

        ax = self._ax
        ax.clear()
        self._style_axes(ax)
        self._scatter_collections.clear()

        for group in groups:
            subset = [r for r in records if get_color_key(r, color_by) == group]
            xs = [r[x_key] for r in subset]
            ys = [r[y_key] for r in subset]
            sc = ax.scatter(
                xs, ys,
                label=group, color=color_map[group],
                s=72, alpha=0.85, edgecolors="white", linewidths=0.5, zorder=3,
            )
            sc._pq_records = subset
            self._scatter_collections.append(sc)

        if self._logx_var.get():
            x_values = [r[x_key] for r in records]
            ax.set_xscale("symlog", linthresh=self.auto_linthresh(x_values))
        if self._logy_var.get():
            y_values = [r[y_key] for r in records]
            ax.set_yscale("symlog", linthresh=self.auto_linthresh(y_values))

        ax.set_xlabel(METRIC_LABELS.get(x_key, x_key), color=C["text"],
                      fontsize=11, labelpad=8)
        ax.set_ylabel(METRIC_LABELS.get(y_key, y_key), color=C["text"],
                      fontsize=11, labelpad=8)

        color_by_label = dict(COLOR_BY_OPTIONS).get(color_by, color_by.capitalize())
        fam_str = self._active_families_str(records)
        ax.set_title(
            f"Family: {fam_str}   \u00b7   "
            f"{METRIC_LABELS.get(x_key, x_key)}  vs  "
            f"{METRIC_LABELS.get(y_key, y_key)}",
            color=C["text"], fontsize=11, pad=12, fontweight="bold",
        )

        leg = ax.legend(
            title=color_by_label,
            facecolor=C["panel"], edgecolor=C["border"],
            labelcolor=C["text"], title_fontsize=9, fontsize=9, framealpha=0.95,
        )
        leg.get_title().set_color(C["blue"])
        leg.get_title().set_fontweight("bold")

        self._fig.tight_layout()
        self._mpl_canvas.draw()

        if HAS_MPLCURSORS:
            cursor = mplcursors.cursor(self._scatter_collections, hover=True)

            @cursor.connect("add")
            def on_add(sel):
                rec = sel.artist._pq_records[sel.index]
                lines = [
                    f"File:      {rec.get('filename', '?')}",
                    f"Family:    {rec.get('family',    NA)}",
                    f"Size/Area:      {rec.get('size',      NA)}",
                    f"Seed: {self._seed_label(rec)}",
                    f"Algorithm: {rec.get('algorithm', NA)}",
                    f"Tuning:    {rec.get('tuning',    NA)}",
                    f"Threads:   {rec.get('threads',   NA)}",
                    "",
                    f"{METRIC_LABELS.get(x_key, x_key)}: {rec.get(x_key, '?'):.4g}",
                    f"{METRIC_LABELS.get(y_key, y_key)}: {rec.get(y_key, '?'):.4g}",
                ]
                sel.annotation.set_text("\n".join(lines))
                sel.annotation.get_bbox_patch().set(
                    facecolor=C["panel"], edgecolor=C["accent"], alpha=0.95)
                sel.annotation.set_fontsize(8.5)
                sel.annotation.set_color(C["text"])

        self._status_var.set(
            f"{len(records)} points plotted  \u00b7  colored by {color_by_label}  "
            f"\u00b7  x = {x_key}  \u00b7  y = {y_key}"
            + ("  \u00b7  hover for details" if HAS_MPLCURSORS
               else "  \u00b7  install mplcursors for hover tooltips")
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()