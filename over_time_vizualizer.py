#!/usr/bin/env python3
"""
PQ Benchmark Timeline Visualizer
=================================
Loads *_summary.csv files from a directory and plots metrics over time
(sequential bin indices as x-axis). Multiple metrics and/or graphs can be overlaid
simultaneously with flexible y-axis handling.

Requirements:
    pip install matplotlib

Optional hover tooltips:
    pip install mplcursors
"""

import os
import re
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches


# ─────────────────────────────────────────────────────────────────────────────
# Export dimensions  (millimetres)
# ─────────────────────────────────────────────────────────────────────────────

EXPORT_WIDTH_MM = 272
EXPORT_HEIGHT_MM = 188 

# ─────────────────────────────────────────────────────────────────────────────

KNOWN_ALGOS = ["capq", "drpq", "klsm", "smq", "mq"]
NA = "(none)"
UNSEEDED = "unseeded"

# ─────────────────────────────────────────────────────────────────────────────
# Metric families
# ─────────────────────────────────────────────────────────────────────────────

METRIC_FAMILIES = [
    ("rank_error", "Rank Error"),
    ("delay", "Delay"),
    ("pq_size", "PQ Size"),
    ("ignored_node", "Ignored Node"),
    ("extra_work", "Extra Work"),
    ("extra_work_generated", "Extra Work Gen."),
]

# Stat types: (csv_suffix, display_label, linewidth)
STAT_SPECS = [
    ("mean", "Mean", 2.0),
    ("p50", "Median", 1.5),
    ("p25", "P25", 1.1),
    ("p75", "P75", 1.1),
    ("p5", "P5", 0.9),
    ("p95", "P95", 0.9),
]

# Quick-lookup maps derived from STAT_SPECS
STAT_LINEWIDTH = {k: lw for k, _, lw in STAT_SPECS}
STAT_LABEL = {k: lbl for k, lbl, _ in STAT_SPECS}

# Stats that should use a lighter shade of the family color
LIGHTENED_STATS = {"p50"}  # Median gets a lighter color


# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────

C = dict(
    bg="#f8f9fa",
    panel="#ffffff",
    surface0="#f1f3f5",
    surface1="#e9ecef",
    surface2="#dee2e6",
    border="#ced4da",
    text="#212529",
    subtext="#868e96",
    muted="#adb5bd",
    blue="#1971c2",
    accent="#228be6",
    blue_lt="#dbe4ff",
)

FAMILY_COLORS = {
    "rank_error": "#228be6",
    "delay": "#f76707",
    "pq_size": "#2f9e44",
    "ignored_node": "#ae3ec9",
    "extra_work": "#c92a2a",
    "extra_work_generated": "#0c8599",
}

GRAPH_PALETTE = [
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
]

# Fixed colors per known algorithm so the same algo always gets the same hue
ALGO_COLORS = {
    "capq": "#228be6",   # blue
    "drpq": "#f76707",   # orange
    "klsm": "#2f9e44",   # green
    "smq":  "#ae3ec9",   # purple
    "mq":   "#f59f00",   # amber
}


# ─────────────────────────────────────────────────────────────────────────────
# Color utilities
# ─────────────────────────────────────────────────────────────────────────────

def lighten_color(hex_color: str, factor: float = 0.6) -> str:
    """Lighten a hex color by interpolating toward white.
    
    Args:
        hex_color: Color in #RRGGBB format
        factor: Blend factor (0.0 = white, 1.0 = original color)
    
    Returns:
        Lightened color in #RRGGBB format
    """
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r * factor + 255 * (1 - factor))
        g = int(g * factor + 255 * (1 - factor))
        b = int(b * factor + 255 * (1 - factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except (ValueError, IndexError):
        return hex_color  # Return original if parsing fails


# ─────────────────────────────────────────────────────────────────────────────
# Filename parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_filename(path: str) -> dict:
    """Parse benchmark filenames into structured metadata."""
    base = os.path.basename(path)
    base = re.sub(r"\.(json|csv)$", "", base)
    base = re.sub(r"_(globals|summary)$", "", base)

    info = dict(
        family=None,
        size=None,
        seed=None,
        algorithm=None,
        tuning=None,
        threads="t1",
        filepath=path,
        filename=os.path.basename(path),
    )
    rest = base

    dot_m = re.match(r"([A-Za-z0-9][A-Za-z0-9\-]*)\.([A-Za-z0-9]+)_(.*)", rest)
    if dot_m:
        info["family"] = dot_m.group(1)
        info["size"] = dot_m.group(2)
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
            after = m.group(2) or ""
            tuning_parts = [digit_suffix] if digit_suffix else []

            for token in after.split("_") if after else []:
                if re.match(r"^t\d+$", token):
                    info["threads"] = token
                else:
                    tuning_parts.append(token)

            tuning = "_".join(p for p in tuning_parts if p)
            info["tuning"] = tuning or None
            break

    return info


# ─────────────────────────────────────────────────────────────────────────────
# CSV loader & directory scanner
# ─────────────────────────────────────────────────────────────────────────────

def load_summary_csv(path: str) -> dict:
    """Load benchmark records from a CSV file.
    
    Returns {column_name: [float, ...]} for every column in a summary CSV.
    """
    data: dict[str, list] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for col, val in row.items():
                try:
                    data[col].append(float(val))
                except (ValueError, TypeError):
                    data[col].append(None)
    return dict(data)


def scan_directory(directory: str) -> list:
    """Load benchmark records from a directory of *_summary.csv files."""
    records = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith("_summary.csv"):
            continue
        path = os.path.join(directory, fname)
        meta = parse_filename(path)
        try:
            meta["csv_data"] = load_summary_csv(path)
            records.append(meta)
        except Exception as exc:
            print(f"[WARN] Skipping {fname}: {exc}")
    return records


# ─────────────────────────────────────────────────────────────────────────────
# Selection tree
# ─────────────────────────────────────────────────────────────────────────────

class SelectionTree(tk.Frame):
    """A tree widget for multi-select hierarchy selection."""
    ICONS = {2: "☑ ", 1: "■ ", 0: "☐ "}

    def __init__(
        self,
        parent,
        hierarchy_keys,
        on_change=None,
        restore_scroll=None,
        tree_height=7,
        **kw,
    ):
        super().__init__(parent, bg=C["panel"], **kw)
        self.hierarchy_keys = hierarchy_keys
        self.on_change = on_change
        self._restore_scroll = restore_scroll
        self.nodes = {}

        self.tree = ttk.Treeview(
            self, selectmode="none", show="tree", height=tree_height
        )
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Enter>", self._on_tree_enter)
        self.tree.bind("<Leave>", self._on_tree_leave)

    def populate(self, records, index_map=None, default_state=0) -> None:
        """Populate the tree with records organized by hierarchy keys."""
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()

        for pos, r in enumerate(records):
            global_idx = index_map[pos] if index_map is not None else pos
            node_id_parts, display_parts = [], []

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
                nid = "\x00".join(node_id_parts[: depth + 1])
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
        """Select all items in the tree."""
        for child in self.tree.get_children(""):
            self._set_subtree(child, 2)
        self._refresh_icons()
        if self.on_change:
            self.after_idle(self.on_change)

    def uncheck_all(self) -> None:
        """Deselect all items in the tree."""
        for child in self.tree.get_children(""):
            self._set_subtree(child, 0)
        self._refresh_icons()
        if self.on_change:
            self.after_idle(self.on_change)

    def expand_all(self) -> None:
        """Expand all tree nodes."""
        for nid in self.nodes:
            self.tree.item(nid, open=True)

    def collapse_all(self) -> None:
        """Collapse all tree nodes."""
        for nid in self.nodes:
            self.tree.item(nid, open=False)

    def get_selected_indices(self) -> set:
        """Return indices of all selected leaf records."""
        result = set()
        for nid, data in self.nodes.items():
            if data["is_leaf"] and data["state"] == 2:
                result.update(data["record_indices"])
        return result

    def _on_tree_enter(self, _e) -> None:
        """Enable mouse wheel scrolling when entering tree."""
        self.tree.bind_all("<MouseWheel>", self._on_scroll)

    def _on_tree_leave(self, _e) -> None:
        """Disable tree scrolling and restore parent scroll on exit."""
        self.tree.unbind_all("<MouseWheel>")
        if self._restore_scroll:
            self._restore_scroll()

    def _on_scroll(self, event) -> None:
        """Handle mouse wheel scrolling on tree."""
        self.tree.yview_scroll(-int(event.delta / 120), "units")

    def _on_click(self, event) -> None:
        """Handle tree node click: toggle selection state."""
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
        """Set selection state for a node and all children."""
        self.nodes[nid]["state"] = state
        for child in self.tree.get_children(nid):
            self._set_subtree(child, state)

    def _bubble_up(self, nid: str) -> None:
        """Update parent states based on children selection."""
        parent = self.tree.parent(nid)
        if not parent:
            return
        child_states = [self.nodes[c]["state"] for c in self.tree.get_children(parent)]
        if all(s == 2 for s in child_states):
            new = 2
        elif all(s == 0 for s in child_states):
            new = 0
        else:
            new = 1
        self.nodes[parent]["state"] = new
        self._bubble_up(parent)

    def _refresh_icons(self) -> None:
        """Refresh checkbox icons to match node selection states."""
        for nid, data in self.nodes.items():
            text = self.ICONS[data["state"]] + data["text"]
            if self.tree.item(nid, "text") != text:
                self.tree.item(nid, text=text)


# ─────────────────────────────────────────────────────────────────────────────
# Check list
# ─────────────────────────────────────────────────────────────────────────────

class CheckList(tk.Frame):
    """Flat checkbox list for flat selection with state preservation."""

    ICONS = {2: "☑ ", 0: "☐ "}

    def __init__(self, parent, on_change=None, height=4, restore_scroll=None, **kw) -> None:
        """Initialize a flat checkbox list."""
        super().__init__(parent, bg=C["panel"], **kw)
        self.on_change = on_change
        self._restore_scroll = restore_scroll
        self._nodes: dict[str, int] = {}  # value → state (0 or 2)

        self.tree = ttk.Treeview(self, selectmode="none", show="tree", height=height)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<Enter>", self._on_tree_enter)
        self.tree.bind("<Leave>", self._on_tree_leave)

    def populate(self, values: list) -> None:
        """Repopulate preserving check state for values that already existed.
        
        New values (not seen before) default to checked.
        """
        old_checked = {v for v, s in self._nodes.items() if s == 2}
        old_all = set(self._nodes.keys())

        self.tree.delete(*self.tree.get_children())
        self._nodes.clear()

        for val in values:
            if val in old_all:
                state = 2 if val in old_checked else 0
            else:
                state = 0  # new value → default unchecked
            # Use a safe iid (replace special chars)
            iid = val.replace("\x00", "_")
            self.tree.insert("", "end", iid=iid, text=self.ICONS[state] + val)
            self._nodes[val] = state

    def get_selected(self) -> set:
        """Return set of checked values."""
        return {v for v, s in self._nodes.items() if s == 2}

    def check_all(self) -> None:
        """Select all items in the list."""
        for val in list(self._nodes):
            self._nodes[val] = 2
            iid = val.replace("\x00", "_")
            self.tree.item(iid, text=self.ICONS[2] + val)
        if self.on_change:
            self.after_idle(self.on_change)

    def uncheck_all(self) -> None:
        """Deselect all items in the list."""
        for val in list(self._nodes):
            self._nodes[val] = 0
            iid = val.replace("\x00", "_")
            self.tree.item(iid, text=self.ICONS[0] + val)
        if self.on_change:
            self.after_idle(self.on_change)

    def _on_click(self, event) -> None:
        """Handle item click: toggle selection state."""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        # Reverse-map iid to value (values are stored directly)
        val = iid  # iid == val (with safe substitution, but values shouldn't have \x00)
        if val not in self._nodes:
            return
        new_state = 0 if self._nodes[val] == 2 else 2
        self._nodes[val] = new_state
        self.tree.item(iid, text=self.ICONS[new_state] + val)
        if self.on_change:
            self.after_idle(self.on_change)

    def _on_tree_enter(self, _e) -> None:
        """Enable mouse wheel scrolling when entering list."""
        self.tree.bind_all("<MouseWheel>", self._on_scroll)

    def _on_tree_leave(self, _e) -> None:
        """Disable scrolling and restore parent scroll on exit."""
        self.tree.unbind_all("<MouseWheel>")
        if self._restore_scroll:
            self._restore_scroll()

    def _on_scroll(self, event) -> None:
        """Handle mouse wheel scrolling on list."""
        self.tree.yview_scroll(-int(event.delta / 120), "units")


# ─────────────────────────────────────────────────────────────────────────────
# Metric grid
# ─────────────────────────────────────────────────────────────────────────────

class MetricGrid(tk.Frame):
    """Grid widget for selecting metric families and stat types.
    
    Rows represent metric families, columns represent stat types.
    """
    def __init__(self, parent, on_change=None, **kw) -> None:
        """Initialize the metric grid."""
        super().__init__(parent, bg=C["panel"], **kw)
        self.on_change = on_change
        self._vars: dict[tuple, tk.BooleanVar] = {}
        self._log_var = tk.BooleanVar(value=False)
        self._build()

    def _build(self) -> None:
        """Build the metric grid with rows and columns."""
        # Column headers (stat types)
        for col, (stat_key, stat_lbl, _) in enumerate(STAT_SPECS, start=1):
            tk.Label(
                self,
                text=stat_lbl,
                bg=C["panel"],
                fg=C["subtext"],
                font=("Segoe UI", 8, "bold"),
                anchor="center",
            ).grid(row=0, column=col, padx=3, pady=(6, 2), sticky="n")

        # Row per family
        for row, (fam_key, fam_lbl) in enumerate(METRIC_FAMILIES, start=1):
            color = FAMILY_COLORS.get(fam_key, C["muted"])

            # Family label cell: swatch + text
            cell = tk.Frame(self, bg=C["panel"])
            cell.grid(row=row, column=0, sticky="w", padx=(6, 8), pady=2)
            tk.Frame(cell, bg=color, width=7, height=13).pack(side=tk.LEFT, padx=(0, 5))
            tk.Label(
                cell,
                text=fam_lbl,
                bg=C["panel"],
                fg=C["text"],
                font=("Segoe UI", 9),
                width=14,
                anchor="w",
            ).pack(side=tk.LEFT)

            # One checkbox per stat
            for col, (stat_key, _, _) in enumerate(STAT_SPECS, start=1):
                var = tk.BooleanVar(value=False)
                self._vars[(fam_key, stat_key)] = var
                ttk.Checkbutton(self, variable=var, command=self._notify).grid(
                    row=row,
                    column=col,
                    padx=5,
                    pady=2,
                )

        # Add log Y checkbox below the metrics table
        log_row = len(METRIC_FAMILIES) + 1
        ttk.Checkbutton(
            self,
            text="Log Y",
            variable=self._log_var,
            command=self._notify,
        ).grid(row=log_row, column=0, columnspan=len(STAT_SPECS) + 1, sticky="w", padx=6, pady=(6, 0))

    def _notify(self) -> None:
        """Notify callback of selection change."""
        if self.on_change:
            self.after_idle(self.on_change)

    def get_selected(self) -> list:
        """Return checked (family_key, stat_key) pairs."""
        return [(fk, sk) for (fk, sk), v in self._vars.items() if v.get()]

    def uncheck_all(self) -> None:
        """Deselect all items in the grid."""
        for v in self._vars.values():
            v.set(False)
        self._notify()

    def set_means_only(self) -> None:
        """Select only mean statistics."""
        for (_, sk), v in self._vars.items():
            v.set(sk == "mean")
        self._notify()

    def get_log_enabled(self) -> bool:
        """Return whether log scale is enabled for this grid."""
        return self._log_var.get()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sort_key_numeric_suffix(s: str) -> tuple:
    """Sort strings by embedded integer, e.g. t1 < t8 < t16 < t32."""
    m = re.search(r"\d+", s)
    return (int(m.group()) if m else 0, s)


# ─────────────────────────────────────────────────────────────────────────────
# Main application
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    """Main application window for the PQ Benchmark Timeline Visualizer."""
    def __init__(self) -> None:
        super().__init__()
        self.title("PQ Timeline Visualizer")
        self.geometry("1540x920")
        self.minsize(960, 640)
        self.configure(bg=C["bg"])

        self._records: list = []
        self._graph_tree: SelectionTree | None = None
        self._algo_tree: SelectionTree | None = None
        self._thread_list: CheckList | None = None
        self._seed_list: CheckList | None = None
        self._metric_grid: MetricGrid | None = None
        self._metric_grid_2: MetricGrid | None = None
        self._metric_grid_3: MetricGrid | None = None
        self._colorbar = None
        self._restore_canvas_scroll = None

        self._setup_style()
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────────

    def _setup_style(self) -> None:
        """Configure ttk theme and styles."""
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
        s.configure("TLabel", background=C["bg"], foreground=C["text"])
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
            background=[("active", C["accent"]), ("pressed", C["blue"])],
            foreground=[("active", "white")],
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
            background=[("active", C["blue"]), ("pressed", C["blue"])],
            foreground=[("active", "white")],
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

    # ─────────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the main UI layout with left and right panels."""
        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left = ttk.Frame(pane, width=440)
        right = ttk.Frame(pane)
        pane.add(left, weight=0)
        pane.add(right, weight=1)
        self._build_left(left)
        self._build_right(right)

    def _build_left(self, parent: ttk.Frame) -> None:
        """Build the left control panel with scrollable content."""
        parent.pack_propagate(False)
        scroll_canvas = tk.Canvas(parent, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(scroll_canvas, bg=C["bg"])
        cwin = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind(
            "<Configure>",
            lambda _e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")),
        )
        scroll_canvas.bind(
            "<Configure>", lambda e: scroll_canvas.itemconfig(cwin, width=e.width)
        )

        def _canvas_scroll(e):
            scroll_canvas.yview_scroll(-int(e.delta / 120), "units")

        def restore_canvas_scroll():
            scroll_canvas.bind_all("<MouseWheel>", _canvas_scroll)

        scroll_canvas.bind("<Enter>", lambda _: restore_canvas_scroll())
        scroll_canvas.bind(
            "<Leave>", lambda _: scroll_canvas.unbind_all("<MouseWheel>")
        )
        self._restore_canvas_scroll = restore_canvas_scroll

        self._build_left_content(inner)

    def _build_left_content(self, parent: tk.Frame) -> None:
        """Build the content of the left control panel."""

        # ── Data Directory ────────────────────────────────────────────────
        dir_sec = ttk.LabelFrame(parent, text="Data Directory")
        dir_sec.pack(fill=tk.X, pady=(0, 5), ipady=2)

        self._dir_label = ttk.Label(
            dir_sec, text="(none selected)", foreground=C["subtext"], wraplength=400
        )
        self._dir_label.pack(padx=8, pady=(4, 0))
        ttk.Button(dir_sec, text="Browse…", command=self._browse_dir).pack(
            padx=8, pady=6
        )

        # ── Step 1: Graph (name + size) ───────────────────────────────────
        graph_lf = ttk.LabelFrame(parent, text="Graph")
        graph_lf.pack(fill=tk.X, pady=(0, 4))

        graph_ctrl = tk.Frame(graph_lf, bg=C["bg"])
        graph_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        self._graph_tree = SelectionTree(
            graph_lf,
            hierarchy_keys=["family", "size"],
            on_change=lambda: self._cascade_from(1),
            restore_scroll=self._restore_canvas_scroll,
            tree_height=6,
        )
        self._graph_tree.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(graph_ctrl, text="All", width=5,
                   command=self._graph_tree.check_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(graph_ctrl, text="None", width=5,
                   command=self._graph_tree.uncheck_all).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(graph_ctrl, text="Expand", width=8,
                   command=self._graph_tree.expand_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(graph_ctrl, text="Collapse", width=8,
                   command=self._graph_tree.collapse_all).pack(side=tk.LEFT)

        # ── Step 2: Algorithm + Tuning ────────────────────────────────────
        algo_lf = ttk.LabelFrame(parent, text="Algorithm")
        algo_lf.pack(fill=tk.X, pady=(0, 4))

        algo_ctrl = tk.Frame(algo_lf, bg=C["bg"])
        algo_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        self._algo_tree = SelectionTree(
            algo_lf,
            hierarchy_keys=["algorithm", "tuning"],
            on_change=lambda: self._cascade_from(2),
            restore_scroll=self._restore_canvas_scroll,
            tree_height=6,
        )
        self._algo_tree.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(algo_ctrl, text="All", width=5,
                   command=self._algo_tree.check_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(algo_ctrl, text="None", width=5,
                   command=self._algo_tree.uncheck_all).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(algo_ctrl, text="Expand", width=8,
                   command=self._algo_tree.expand_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(algo_ctrl, text="Collapse", width=8,
                   command=self._algo_tree.collapse_all).pack(side=tk.LEFT)

        # ── Step 3: Threads ───────────────────────────────────────────────
        thread_lf = ttk.LabelFrame(parent, text="Threads")
        thread_lf.pack(fill=tk.X, pady=(0, 4))

        thread_ctrl = tk.Frame(thread_lf, bg=C["bg"])
        thread_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        self._thread_list = CheckList(
            thread_lf,
            on_change=lambda: self._cascade_from(3),
            restore_scroll=self._restore_canvas_scroll,
            height=4,
        )
        self._thread_list.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(thread_ctrl, text="All", width=5,
                   command=self._thread_list.check_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(thread_ctrl, text="None", width=5,
                   command=self._thread_list.uncheck_all).pack(side=tk.LEFT)

        # ── Step 4: Seeds ─────────────────────────────────────────────────
        seed_lf = ttk.LabelFrame(parent, text="Seeds")
        seed_lf.pack(fill=tk.X, pady=(0, 4))

        seed_ctrl = tk.Frame(seed_lf, bg=C["bg"])
        seed_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        self._seed_list = CheckList(
            seed_lf,
            on_change=None,  # leaf – no further cascade
            restore_scroll=self._restore_canvas_scroll,
            height=4,
        )
        self._seed_list.pack(fill=tk.X, padx=4, pady=(0, 4))

        ttk.Button(seed_ctrl, text="All", width=5,
                   command=self._seed_list.check_all).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(seed_ctrl, text="None", width=5,
                   command=self._seed_list.uncheck_all).pack(side=tk.LEFT)

        # ── Metrics ───────────────────────────────────────────────────────
        metric_lf = ttk.LabelFrame(parent, text="Metrics")
        metric_lf.pack(fill=tk.X, pady=(0, 5))

        metric_ctrl = tk.Frame(metric_lf, bg=C["bg"])
        metric_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        # Create the metric grid first so buttons can reference it
        self._metric_grid = MetricGrid(metric_lf)

        ttk.Button(
            metric_ctrl,
            text="None",
            width=6,
            command=self._metric_grid.uncheck_all,
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            metric_ctrl,
            text="Means",
            width=6,
            command=self._metric_grid.set_means_only,
        ).pack(side=tk.LEFT, padx=(0, 2))

        self._metric_grid.pack(padx=6, pady=(0, 6))

        # ── Metrics (2nd axis) ───────────────────────────────────────────────
        metric2_lf = ttk.LabelFrame(parent, text="Metrics (2nd axis)")
        metric2_lf.pack(fill=tk.X, pady=(0, 5))

        metric2_ctrl = tk.Frame(metric2_lf, bg=C["bg"])
        metric2_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        # Create the second metric grid
        self._metric_grid_2 = MetricGrid(metric2_lf)

        ttk.Button(
            metric2_ctrl,
            text="None",
            width=6,
            command=self._metric_grid_2.uncheck_all,
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            metric2_ctrl,
            text="Means",
            width=6,
            command=self._metric_grid_2.set_means_only,
        ).pack(side=tk.LEFT, padx=(0, 2))

        self._metric_grid_2.pack(padx=6, pady=(0, 6))

        # ── Metrics (3rd axis) ───────────────────────────────────────────────
        metric3_lf = ttk.LabelFrame(parent, text="Metrics (3rd axis)")
        metric3_lf.pack(fill=tk.X, pady=(0, 5))

        metric3_ctrl = tk.Frame(metric3_lf, bg=C["bg"])
        metric3_ctrl.pack(fill=tk.X, padx=4, pady=(4, 2))

        # Create the third metric grid
        self._metric_grid_3 = MetricGrid(metric3_lf)

        ttk.Button(
            metric3_ctrl,
            text="None",
            width=6,
            command=self._metric_grid_3.uncheck_all,
        ).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(
            metric3_ctrl,
            text="Means",
            width=6,
            command=self._metric_grid_3.set_means_only,
        ).pack(side=tk.LEFT, padx=(0, 2))

        self._metric_grid_3.pack(padx=6, pady=(0, 6))

        # ── Display Options ───────────────────────────────────────────────
        disp_lf = ttk.LabelFrame(parent, text="Display Options")
        disp_lf.pack(fill=tk.X, pady=(0, 5))

        self._band_var = tk.BooleanVar()
        self._norm_var = tk.BooleanVar()

        opt_row = tk.Frame(disp_lf, bg=C["bg"])
        opt_row.pack(fill=tk.X, padx=8, pady=(4, 0))
        ttk.Checkbutton(opt_row, text="P25–P75 band", variable=self._band_var).pack(
            side=tk.LEFT, padx=(0, 16)
        )
        ttk.Checkbutton(opt_row, text="Normalize [0–1]", variable=self._norm_var).pack(
            side=tk.LEFT
        )

        # ── Color By ─────────────────────────────────────────────────────
        col_lf = ttk.LabelFrame(parent, text="Color By")
        col_lf.pack(fill=tk.X, pady=(0, 5))

        col_row = tk.Frame(col_lf, bg=C["bg"])
        col_row.pack(padx=8, pady=6)
        self._color_var = tk.StringVar(value="family")
        for val, lbl in [("family", "Metric Family"), ("algorithm", "Algorithm"),
                         ("graph", "Graph")]:
            ttk.Radiobutton(
                col_row, text=lbl, variable=self._color_var, value=val
            ).pack(side=tk.LEFT, padx=(0, 12))

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = ttk.Frame(parent)
        btn_row.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        ttk.Button(btn_row, text="⤓  Export PDF", command=self._export_pdf).grid(
            row=0, column=0, sticky="nsew", padx=(0, 1), pady=2
        )
        ttk.Button(btn_row, text="⤓  Export PNG", command=self._export_png).grid(
            row=0, column=1, sticky="nsew", padx=(1, 0), pady=2
        )
        ttk.Button(
            btn_row, text="⟳  Plot", style="Accent.TButton", command=self._plot
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=2)

    # ─────────────────────────────────────────────────────────────────────────────

    def _build_right(self, parent: ttk.Frame) -> None:
        """Build the right plot panel with matplotlib canvas."""
        self._fig = Figure(facecolor=C["bg"])
        self._ax = self._fig.add_subplot(111, facecolor=C["panel"])
        self._style_axes(self._ax)

        self._mpl_canvas = FigureCanvasTkAgg(self._fig, master=parent)
        self._mpl_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._status_var = tk.StringVar(value="Load a directory to begin.")
        ttk.Label(parent, textvariable=self._status_var, foreground=C["subtext"]).pack(
            anchor="w", padx=4, pady=(4, 0)
        )

    def _style_axes(self, ax) -> None:
        """Apply consistent styling to a matplotlib axis."""
        ax.tick_params(colors=C["text"], labelsize=9)
        for spine in ax.spines.values():
            spine.set_edgecolor(C["border"])
        ax.grid(True, color=C["surface1"], linestyle="--", linewidth=0.6, zorder=0)
        ax.set_facecolor(C["panel"])

    # ─────────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────────

    def _browse_dir(self) -> None:
        """Browse for and load a benchmark directory."""
        directory = filedialog.askdirectory(title="Select benchmark summary directory")
        if not directory:
            return

        self._dir_label.configure(text=directory, foreground=C["text"])
        self._records = scan_directory(directory)

        if not self._records:
            messagebox.showwarning(
                "No Files Found",
                "No *_summary.csv files were found in the selected directory.",
            )
            return

        # Populate graph tree with all records (family + size hierarchy only)
        self._graph_tree.populate(self._records)

        # Cascade to populate algo/thread/seed with all values
        self._cascade_from(1)

        self._status_var.set(f"Loaded {len(self._records)} summary file(s).")

    # ─────────────────────────────────────────────────────────────────────────────
    # Cascading filter logic
    # ─────────────────────────────────────────────────────────────────────────────

    def _cascade_from(self, level: int) -> None:
        """Repopulate filters based on upstream selections.
        
        level 1 → repopulate algo, thread, seed
        level 2 → repopulate thread, seed
        level 3 → repopulate seed
        """
        if level <= 1:
            graph_indices = sorted(self._graph_tree.get_selected_indices())
            graph_recs = [self._records[i] for i in graph_indices]
            index_map = {pos: graph_indices[pos] for pos in range(len(graph_indices))}
            self._algo_tree.populate(graph_recs, index_map=index_map)

        if level <= 2:
            algo_recs = self._get_algo_filtered_records()
            threads = sorted(
                {r.get("threads") or "t1" for r in algo_recs},
                key=_sort_key_numeric_suffix,
            )
            self._thread_list.populate(threads)

        if level <= 3:
            thread_recs = self._get_thread_filtered_records()
            seeds = sorted(
                {r.get("seed") or UNSEEDED for r in thread_recs},
                key=lambda s: (s == UNSEEDED, _sort_key_numeric_suffix(s)),
            )
            self._seed_list.populate(seeds)

    # ─────────────────────────────────────────────────────────────────────────────

    def _get_graph_filtered_records(self) -> list:
        """Records matching current graph-tree (step 1) selection."""
        indices = self._graph_tree.get_selected_indices()
        return [self._records[i] for i in sorted(indices)]

    def _get_algo_filtered_records(self) -> list:
        """Records matching steps 1 + 2 (graph + algorithm/tuning)."""
        indices = self._algo_tree.get_selected_indices()
        return [self._records[i] for i in sorted(indices)]

    def _get_thread_filtered_records(self) -> list:
        """Records matching steps 1 + 2 + 3."""
        records = self._get_algo_filtered_records()
        threads = self._thread_list.get_selected()
        return [r for r in records if (r.get("threads") or "t1") in threads]

    def _selected_records(self) -> list:
        """Return records matching all four selection steps."""
        if not self._records:
            return []
        records = self._get_thread_filtered_records()
        seeds = self._seed_list.get_selected()
        return [r for r in records if (r.get("seed") or UNSEEDED) in seeds]

    # ─────────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _graph_label(rec: dict) -> str:
        """Generate display label for a graph record."""
        parts = []
        for k in ("family", "size", "algorithm", "tuning", "threads", "seed"):
            v = rec.get(k)
            if v and str(v).lower() not in ("none", "(none)", "t1", "unseeded"):
                parts.append(str(v))
        return " / ".join(parts) if parts else rec.get("filename", "?")

    @staticmethod
    def auto_linthresh(values: list, default: float = 1.0) -> float:
        """Calculate appropriate linear threshold for symlog scale."""
        nonzero = [abs(v) for v in values if v != 0]
        if not nonzero:
            return default
        return min(nonzero) * 0.5

    # ─────────────────────────────────────────────────────────────────────────────

    def _plot(self) -> None:
        """Plot selected metrics over time."""
        records = self._selected_records()
        selected_metrics = self._metric_grid.get_selected()
        selected_metrics_2 = self._metric_grid_2.get_selected()
        selected_metrics_3 = self._metric_grid_3.get_selected()

        if not records:
            messagebox.showwarning("No Selection", "Select at least one graph.")
            return
        if not selected_metrics and not selected_metrics_2 and not selected_metrics_3:
            messagebox.showwarning("No Metrics", "Select at least one metric.")
            return

        # ── Fresh figure ──────────────────────────────────────────────────
        if self._colorbar is not None:
            try:
                self._colorbar.remove()
            except Exception:
                pass
            self._colorbar = None

        self._fig.clear()
        ax = self._fig.add_subplot(111, facecolor=C["panel"])
        self._ax = ax
        self._style_axes(ax)
        
        # Create secondary axes if needed (all twinned to the primary axis)
        ax2 = None
        ax3 = None
        
        if selected_metrics_2 or selected_metrics_3:
            ax2 = ax.twinx()
            self._style_axes(ax2)
            # Position the first right axis
            ax2.spines["right"].set_position(("outward", 0))
        
        if selected_metrics_3:
            ax3 = ax.twinx()
            self._style_axes(ax3)
            # Position the second right axis further to the right
            ax3.spines["right"].set_position(("outward", 60))

        color_by = self._color_var.get()
        show_band = self._band_var.get()
        normalize = self._norm_var.get()

        # ── Build series list ─────────────────────────────────────────────
        series = []

        # Pre-build a stable (algo, tuning) → color map so every unique
        # combination gets its own palette slot, in order of first appearance.
        if color_by == "algorithm":
            _seen_at: dict[tuple, int] = {}
            for rec in records:
                key = (rec.get("algorithm") or NA, rec.get("tuning") or "")
                if key not in _seen_at:
                    _seen_at[key] = len(_seen_at)
            _algo_tuning_colors: dict[tuple, str] = {
                key: GRAPH_PALETTE[idx % len(GRAPH_PALETTE)]
                for key, idx in _seen_at.items()
            }
        else:
            _algo_tuning_colors = {}

        for g_idx, rec in enumerate(records):
            data = rec.get("csv_data", {})
            graph_color = GRAPH_PALETTE[g_idx % len(GRAPH_PALETTE)]
            graph_lbl = self._graph_label(rec)

            # First axis metrics
            for fam_key, stat_key in selected_metrics:
                col_name = f"{fam_key}_{stat_key}"
                y_raw = data.get(col_name)
                if not y_raw:
                    continue

                x_data = list(range(len(y_raw)))
                pairs = [(x, y) for x, y in zip(x_data, y_raw) if y is not None]
                if not pairs:
                    continue
                xs, ys = zip(*pairs)

                fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                ls = "-"
                lw = STAT_LINEWIDTH.get(stat_key, 1.5)

                algo = rec.get("algorithm") or NA
                tuning = rec.get("tuning") or ""
                if color_by == "family":
                    base_color = FAMILY_COLORS.get(fam_key, GRAPH_PALETTE[0])
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                elif color_by == "algorithm":
                    base_color = _algo_tuning_colors[(algo, tuning)]
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                else:
                    color = lighten_color(graph_color) if stat_key in LIGHTENED_STATS else graph_color

                label = f"{fam_lbl}  {stat_lbl}"
                if len(records) > 1:
                    label = f"{graph_lbl}  ·  {label}"

                series.append(
                    dict(
                        xs=list(xs),
                        ys=list(ys),
                        label=label,
                        color=color,
                        ls=ls,
                        lw=lw,
                        family=fam_key,
                        stat=stat_key,
                        g_idx=g_idx,
                        algo=algo,
                        tuning=tuning,
                        axis="left",
                    )
                )
            
            # Second axis metrics
            for fam_key, stat_key in selected_metrics_2:
                col_name = f"{fam_key}_{stat_key}"
                y_raw = data.get(col_name)
                if not y_raw:
                    continue

                x_data = list(range(len(y_raw)))
                pairs = [(x, y) for x, y in zip(x_data, y_raw) if y is not None]
                if not pairs:
                    continue
                xs, ys = zip(*pairs)

                fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                ls = ":"
                lw = STAT_LINEWIDTH.get(stat_key, 1.5)

                algo = rec.get("algorithm") or NA
                tuning = rec.get("tuning") or ""
                if color_by == "family":
                    base_color = FAMILY_COLORS.get(fam_key, GRAPH_PALETTE[0])
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                elif color_by == "algorithm":
                    base_color = _algo_tuning_colors[(algo, tuning)]
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                else:
                    color = lighten_color(graph_color) if stat_key in LIGHTENED_STATS else graph_color

                label = f"{fam_lbl}  {stat_lbl}"
                if len(records) > 1:
                    label = f"{graph_lbl}  ·  {label}"

                series.append(
                    dict(
                        xs=list(xs),
                        ys=list(ys),
                        label=label,
                        color=color,
                        ls=ls,
                        lw=lw,
                        family=fam_key,
                        stat=stat_key,
                        g_idx=g_idx,
                        algo=algo,
                        tuning=tuning,
                        axis="right",
                    )
                )
            
            # Third axis metrics
            for fam_key, stat_key in selected_metrics_3:
                col_name = f"{fam_key}_{stat_key}"
                y_raw = data.get(col_name)
                if not y_raw:
                    continue

                x_data = list(range(len(y_raw)))
                pairs = [(x, y) for x, y in zip(x_data, y_raw) if y is not None]
                if not pairs:
                    continue
                xs, ys = zip(*pairs)

                fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                ls = "--"
                lw = STAT_LINEWIDTH.get(stat_key, 1.5)

                algo = rec.get("algorithm") or NA
                tuning = rec.get("tuning") or ""
                if color_by == "family":
                    base_color = FAMILY_COLORS.get(fam_key, GRAPH_PALETTE[0])
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                elif color_by == "algorithm":
                    base_color = _algo_tuning_colors[(algo, tuning)]
                    color = lighten_color(base_color) if stat_key in LIGHTENED_STATS else base_color
                else:
                    color = lighten_color(graph_color) if stat_key in LIGHTENED_STATS else graph_color

                label = f"{fam_lbl}  {stat_lbl}"
                if len(records) > 1:
                    label = f"{graph_lbl}  ·  {label}"

                series.append(
                    dict(
                        xs=list(xs),
                        ys=list(ys),
                        label=label,
                        color=color,
                        ls=ls,
                        lw=lw,
                        family=fam_key,
                        stat=stat_key,
                        g_idx=g_idx,
                        algo=algo,
                        tuning=tuning,
                        axis="right2",
                    )
                )

        if not series:
            messagebox.showwarning(
                "No Data", "No data columns found for the selected combination."
            )
            return

        # ── Normalize ─────────────────────────────────────────────────────
        if normalize:
            for s in series:
                ys = s["ys"]
                lo, hi = min(ys), max(ys)
                if hi > lo:
                    s["ys"] = [(y - lo) / (hi - lo) for y in ys]

        # ── Draw series ───────────────────────────────────────────────────
        for s in series:
            axis_type = s.get("axis")
            if axis_type == "right2" and ax3 is not None:
                use_ax = ax3
            elif axis_type == "right" and ax2 is not None:
                use_ax = ax2
            else:
                use_ax = ax
            use_ax.plot(
                s["xs"],
                s["ys"],
                color=s["color"],
                linestyle=s["ls"],
                linewidth=s["lw"],
                alpha=0.88,
                zorder=3,
                label=s["label"],
            )

        # ── Percentile bands ──────────────────────────────────────────────
        if show_band and not normalize:
            shown_families = {s["family"] for s in series}
            for g_idx, rec in enumerate(records):
                data = rec.get("csv_data", {})
                for fam_key in shown_families:
                    p25 = data.get(f"{fam_key}_p25")
                    p75 = data.get(f"{fam_key}_p75")
                    if not p25 or not p75:
                        continue
                    x_data = list(range(len(p25)))
                    triples = [
                        (x, lo, hi)
                        for x, lo, hi in zip(x_data, p25, p75)
                        if lo is not None and hi is not None
                    ]
                    if not triples:
                        continue
                    xs_b, lo_b, hi_b = zip(*triples)
                    fc = (
                        FAMILY_COLORS.get(fam_key, C["muted"])
                        if color_by == "family"
                        else GRAPH_PALETTE[g_idx % len(GRAPH_PALETTE)]
                    )
                    # Determine which axis this family belongs to
                    use_ax = ax
                    for s in series:
                        if s["family"] == fam_key:
                            if s.get("axis") == "right2":
                                use_ax = ax3
                                break
                            elif s.get("axis") == "right":
                                use_ax = ax2
                                break
                    if use_ax is not None:
                        use_ax.fill_between(xs_b, lo_b, hi_b, alpha=0.11, color=fc, zorder=2)

        # ── Log scale ─────────────────────────────────────────────────────
        if not normalize:
            # Apply log scale to left axis if enabled
            if self._metric_grid.get_log_enabled():
                y_values = [s["ys"] for s in series if s.get("axis") != "right" and s.get("axis") != "right2"]
                if y_values:
                    all_y = []
                    for ys in y_values:
                        all_y.extend(ys)
                    linthresh = self.auto_linthresh(all_y)
                    try:
                        ax.set_yscale("symlog", linthresh=linthresh)
                    except Exception:
                        pass
            
            # Apply log scale to right axis if enabled and exists
            if ax2 and self._metric_grid_2.get_log_enabled():
                y_values = [s["ys"] for s in series if s.get("axis") == "right"]
                if y_values:
                    all_y = []
                    for ys in y_values:
                        all_y.extend(ys)
                    linthresh = self.auto_linthresh(all_y)
                    try:
                        ax2.set_yscale("symlog", linthresh=linthresh)
                    except Exception:
                        pass
            
            # Apply log scale to right2 axis if enabled and exists
            if ax3 and self._metric_grid_3.get_log_enabled():
                y_values = [s["ys"] for s in series if s.get("axis") == "right2"]
                if y_values:
                    all_y = []
                    for ys in y_values:
                        all_y.extend(ys)
                    linthresh = self.auto_linthresh(all_y)
                    try:
                        ax3.set_yscale("symlog", linthresh=linthresh)
                    except Exception:
                        pass

        # ── Legend ────────────────────────────────────────────────────────
        self._draw_legend(ax, ax2, ax3, series, records, color_by)

        # ── Axis labels & title ───────────────────────────────────────────
        ax.set_xlabel("Time Step (bin index)", color=C["text"], fontsize=11, labelpad=8)

        if normalize:
            ax.set_ylabel(
                "Normalized value  [0 – 1]", color=C["text"], fontsize=11, labelpad=8
            )
        else:
            left_fams = sorted({s["family"] for s in series if s.get("axis") not in ("right", "right2")})
            left_lbls = [dict(METRIC_FAMILIES).get(f, f) for f in left_fams]
            ax.set_ylabel(
                " / ".join(left_lbls) if left_lbls else "Value",
                color=C["text"],
                fontsize=11,
                labelpad=8,
            )
            if ax2:
                right_fams = sorted({s["family"] for s in series if s.get("axis") == "right"})
                right_lbls = [dict(METRIC_FAMILIES).get(f, f) for f in right_fams]
                ax2.set_ylabel(
                    " / ".join(right_lbls), color=C["text"], fontsize=11, labelpad=8
                )
            if ax3:
                right2_fams = sorted({s["family"] for s in series if s.get("axis") == "right2"})
                right2_lbls = [dict(METRIC_FAMILIES).get(f, f) for f in right2_fams]
                ax3.set_ylabel(
                    " / ".join(right2_lbls), color=C["text"], fontsize=11, labelpad=8
                )

        if len(records) == 1:
            title_lhs = self._graph_label(records[0])
        else:
            title_lhs = f"{len(records)} graph(s)"
        ax.set_title(
            f"{title_lhs}   ·   Timeline",
            color=C["text"],
            fontsize=11,
            pad=12,
            fontweight="bold",
        )

        self._fig.tight_layout()
        self._mpl_canvas.draw()

        total_metrics = len(selected_metrics) + len(selected_metrics_2) + len(selected_metrics_3)
        self._status_var.set(
            f"{len(series)} series plotted  ·  "
            f"{len(records)} graph(s)  ·  "
            f"{total_metrics} metric(s)"
        )

    # ─────────────────────────────────────────────────────────────────────────────

    def _draw_legend(self, ax, ax2, ax3, series, records, color_by) -> None:
        """Draw legend for the plot."""
        handles = []

        if color_by == "family":
            # Group series by family and stat to show mean/median separately with their colors and line styles
            family_stats = {}
            for s in series:
                fam_key = s["family"]
                stat_key = s["stat"]
                if fam_key not in family_stats:
                    family_stats[fam_key] = {}
                if stat_key not in family_stats[fam_key]:
                    family_stats[fam_key][stat_key] = {"color": s["color"], "ls": s["ls"]}
            
            # Create legend entries for each family-stat combination
            for fam_key in sorted(family_stats.keys()):
                fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                for stat_key in sorted(family_stats[fam_key].keys()):
                    color = family_stats[fam_key][stat_key]["color"]
                    ls = family_stats[fam_key][stat_key]["ls"]
                    stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                    lbl = f"{fam_lbl} {stat_lbl}"
                    handles.append(
                        Line2D([0], [0], color=color, linewidth=2.5, linestyle=ls, label=lbl)
                    )
        elif color_by == "algorithm":
            # Group by algorithm-tuning pairs with family-stat labels
            algo_tuning_fams = {}
            for s in series:
                key = (s["algo"], s["tuning"])
                if key not in algo_tuning_fams:
                    algo_tuning_fams[key] = {}
                fam_stat = (s["family"], s["stat"])
                if fam_stat not in algo_tuning_fams[key]:
                    algo_tuning_fams[key][fam_stat] = {"color": s["color"], "ls": s["ls"]}
            
            for algo, tuning in sorted(algo_tuning_fams.keys()):
                algo_lbl = f"{algo} · {tuning}" if tuning else algo
                for (fam_key, stat_key) in sorted(algo_tuning_fams[(algo, tuning)].keys()):
                    color = algo_tuning_fams[(algo, tuning)][(fam_key, stat_key)]["color"]
                    ls = algo_tuning_fams[(algo, tuning)][(fam_key, stat_key)]["ls"]
                    fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                    stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                    lbl = f"{algo_lbl} · {fam_lbl} {stat_lbl}"
                    handles.append(
                        Line2D([0], [0], color=color, linewidth=2.5, linestyle=ls, label=lbl)
                    )
        else:
            # Group by graph index with family-stat labels
            graph_fams = {}
            for s in series:
                g_idx = s["g_idx"]
                if g_idx not in graph_fams:
                    graph_fams[g_idx] = {}
                fam_stat = (s["family"], s["stat"])
                if fam_stat not in graph_fams[g_idx]:
                    graph_fams[g_idx][fam_stat] = {"color": s["color"], "ls": s["ls"]}
            
            for g_idx in sorted(graph_fams.keys()):
                graph_lbl = self._graph_label(records[g_idx])
                for (fam_key, stat_key) in sorted(graph_fams[g_idx].keys()):
                    color = graph_fams[g_idx][(fam_key, stat_key)]["color"]
                    ls = graph_fams[g_idx][(fam_key, stat_key)]["ls"]
                    fam_lbl = dict(METRIC_FAMILIES).get(fam_key, fam_key)
                    stat_lbl = STAT_LABEL.get(stat_key, stat_key)
                    lbl = f"{graph_lbl} · {fam_lbl} {stat_lbl}"
                    handles.append(
                        Line2D([0], [0], color=color, linewidth=2.5, linestyle=ls, label=lbl)
                    )

        if not handles:
            return

        leg = ax.legend(
            handles=handles,
            facecolor=C["panel"],
            edgecolor=C["border"],
            labelcolor=C["text"],
            fontsize=9,
            framealpha=0.95,
            loc="best",
        )
        ax.add_artist(leg)

    # ── Export ────────────────────────────────────────────────────────────────

    def _default_stem(self) -> str:
        """Generate default filename stem for exports."""
        records = self._selected_records()
        fams = sorted({str(r.get("family") or "unknown") for r in records})
        fam_str = "_".join(fams[:2]) + ("_etc" if len(fams) > 2 else "")
        metrics = self._metric_grid.get_selected()
        met_str = "_".join(f"{fk[:4]}_{sk}" for fk, sk in metrics[:2])
        return f"{fam_str}_{met_str}_timeline"

    def _export_png(self) -> None:
        """Export plot to PNG file."""
        path = filedialog.asksaveasfilename(
            title="Export as PNG",
            initialfile=self._default_stem() + ".png",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            orig = self._fig.get_size_inches()
            self._fig.set_size_inches(EXPORT_WIDTH_MM / 25.4, EXPORT_HEIGHT_MM / 25.4)
            self._fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
            self._fig.set_size_inches(*orig)
            self._mpl_canvas.draw()
            self._status_var.set(f"Exported → {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _export_pdf(self) -> None:
        """Export plot to PDF file."""
        path = filedialog.asksaveasfilename(
            title="Export as PDF",
            initialfile=self._default_stem() + ".pdf",
            defaultextension=".pdf",
            filetypes=[("PDF document", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            from matplotlib.backends.backend_pdf import PdfPages

            orig = self._fig.get_size_inches()
            self._fig.set_size_inches(EXPORT_WIDTH_MM / 25.4, EXPORT_HEIGHT_MM / 25.4)
            with PdfPages(path) as pdf:
                pdf.savefig(self._fig, bbox_inches="tight", facecolor="white")
                d = pdf.infodict()
                d["Title"] = self._ax.get_title() or "PQ Timeline"
                d["Creator"] = "PQ Timeline Visualizer"
            self._fig.set_size_inches(*orig)
            self._mpl_canvas.draw()
            self._status_var.set(f"Exported → {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
