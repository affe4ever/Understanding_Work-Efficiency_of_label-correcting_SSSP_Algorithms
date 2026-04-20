"""
Benchmark Suite for Pathfinding Algorithms

All algorithms must:
  - Support -j (num threads) and -l (log file) flags
  - Output logs compatible with analyze_quality
  - Print results to stderr in the expected format

To add an algorithm:
  1. Add an AlgorithmConfig to ALGORITHMS
  2. The first entry is the baseline for within-graph comparisons

To add a graph:
  1. Place the .gr file in the appropriate subfolder under graphs/
  2. Add its Path to the matching list in GRAPH_CATEGORIES
"""

from pathlib import Path
from itertools import chain
import hashlib
import json
import subprocess
import argparse

# ===== Configuration =====
OUT_PATH = Path("out")

ROAD_GRAPHS_PATH               = Path("graphs/road")
SOCIAL_GRAPHS_PATH             = Path("graphs/social")
RANDOM_GRAPHS_PATH             = Path("graphs/random")
RANDOM_HYPERBOLIC_GRAPHS_PATH  = Path("graphs/random_hyperbolic")

# Add Path entries to the relevant category. Files must already exist on disk.
# Graphs can be generated using the get_graphs.py
GRAPH_CATEGORIES = {
    "Road Networks": [
        ROAD_GRAPHS_PATH / "USA-road-t.NY.gr",
        ROAD_GRAPHS_PATH / "USA-road-t.CTR.gr",
        ROAD_GRAPHS_PATH / "USA-road-t.USA.gr",
        # ROAD_GRAPHS_PATH / "example.gr",

    ],
    "Social Networks": [
        # SOCIAL_GRAPHS_PATH / "example.gr",
    ],
    "Random Graphs": [
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s1.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s2.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s3.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s4.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s5.gr",
        # RANDOM_GRAPHS_PATH / "example.gr",
    ],
    "Random Hyperbolic Graphs": [
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s1.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s2.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s4.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s5.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24.gr",
        # RANDOM_HYPERBOLIC_GRAPHS_PATH / "the_rhg.gr",
        # RANDOM_HYPERBOLIC_GRAPHS_PATH / "example.gr",
    ],
}

ANALYZE_QUALITY_PATH = Path("multiqueue_experiments/build/tools/analyze_quality")

class AlgorithmConfig:
    """A pathfinding algorithm with one or more named flag configurations."""
    def __init__(self, path, name, flag_configs=None):
        """
        Args:
            path: Path to the executable
            name: Short identifier used in output filenames
            flag_configs: List of (config_name, flags_list) tuples
        """
        self.path = Path(path)
        self.name = name
        self.flag_configs = flag_configs or [("default", [])]


# The FIRST entry is the baseline for within-graph comparisons.
ALGORITHMS = [
    # AlgorithmConfig(
    #     path="multiqueue_experiments/build/benchmarks/dijkstra_log_locked_pq",
    #     name="dijkstra",
    #     flag_configs=[
    #         ("seq", ["-j", "1"]),
    #         # ("t_8", ["-j", "8"]),
    #     ]
    # ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_dr_pq",
        name="drpq",
        flag_configs=[
            ("mean0", ["-j", "1", "--mean", "0", "--stddev", "0"]),
            ("mean1", ["-j", "1", "--mean", "1", "--stddev", "0"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_random_strict",
        name="mq_basic",
        flag_configs=[
            ("t1", ["-j", "1"]),
            ("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    # AlgorithmConfig(
    #     path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_mark",
    #     name="mq_stick_mark",
    #     flag_configs=[
    #         ("t8", ["-j", "8"]),
    #         ("t16", ["-j", "16"]),
    #         ("t32", ["-j", "32"]),
    #     ]
    # ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_random",
        name="mq_quality",
        flag_configs=[
            ("t8", ["-j", "8", "-k", "4"]),
            ("t16", ["-j", "16", "-k", "4"]),
            ("t32", ["-j", "32", "-k", "4"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_swap",
        name="mq_balanced",
        flag_configs=[
            ("t8", ["-j", "8", "-k", "256"]),
            ("t16", ["-j", "16", "-k", "256"]),
            ("t32", ["-j", "32", "-k", "256"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_random",
        name="mq_fast",
        flag_configs=[
            ("t8", ["-j", "8", "-k", "4096"]),
            ("t16", ["-j", "16", "-k", "4096"]),
            ("t32", ["-j", "32", "-k", "4096"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_swap",
        name="mq_ss256",
        flag_configs=[
            ("t32_c4", ["-j", "32", "-k", "256", "-c", "4"]),
            ("t32_c8", ["-j", "32", "-k", "256", "-c", "8"]),
            ("t32_c16", ["-j", "32", "-k", "256", "-c", "16"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_random",
        name="mq_sr256",
        flag_configs=[
            ("t32_c4", ["-j", "32", "-k", "256", "-c", "4"]),
            ("t32_c8", ["-j", "32", "-k", "256", "-c", "8"]),
            ("t32_c16", ["-j", "32", "-k", "256", "-c", "16"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_smq",
        name="smq",
        flag_configs=[
            ("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_klsm256",
        name="klsm256",
        flag_configs=[
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_klsm1024",
        name="klsm1024",
        flag_configs=[
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_klsm4096",
        name="klsm4096",
        flag_configs=[
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_capq",
        name="capq",
        flag_configs=[
            #("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    # AlgorithmConfig(
    #     path="multiqueue_experiments/build/benchmarks/dijkstra_log_example",
    #     name="example",
    #     flag_configs=[
    #         ("example", ["-j", "1"]),
    #     ]
    # ),
]

class GraphResults:
    """Results from running a benchmark and quality analysis."""
    def __init__(self):
        self.name: str = ""
        self.time: float = 0.0
        self.processed_nodes: int = 0
        self.ignored_nodes: int = 0
        self.edge_relaxations: int = 0
        self.discarded_edges: int = 0
        self.average_pq_size: float = 0.0
        self.max_pq_size: int = 0
        self.average_rank_error: float = 0.0
        self.average_delay: float = 0.0


def hash_file(path: Path) -> str:
    """SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _parse_kv(text: str) -> dict:
    """Parse 'Key: value' lines from text into a dict."""
    result = {}
    for line in text.split("\n"):
        if ":" in line:
            k, v = (s.strip() for s in line.split(":", 1))
            result[k] = v
    return result


def check_graphs():
    """Raise if any graph file listed in GRAPH_CATEGORIES is missing."""
    for category, paths in GRAPH_CATEGORIES.items():
        for path in paths:
            if not path.exists():
                raise RuntimeError(f"[{category}] Graph not found: {path}")


def run_benchmarks(cached_only=False):
    """
    Run all configured algorithms on all graphs and analyze quality.

    Args:
        cached_only: If True, only load and analyze cached results; skip running benchmarks

    Results are cached using .meta files stored alongside each log file.
    Each .meta file contains:
      - graph_hash + cmd: validates that the log belongs to this graph and config
      - log_hash: validates that the quality result belongs to this log
    A cached result is only reused when the full chain is verified.
    """
    if not ALGORITHMS:
        raise RuntimeError("ALGORITHMS list is empty. At least one algorithm must be configured.")

    for alg in ALGORITHMS:
        if not alg.path.exists():
            raise RuntimeError(f"{alg.name} not found at {alg.path}, build multiqueue_experiments then continue")

    if not ANALYZE_QUALITY_PATH.exists():
        raise RuntimeError("analyze_quality not found, build multiqueue_experiments then continue")

    # Create output directory
    OUT_PATH.mkdir(exist_ok=True)

    # Flatten all graph paths from every category in order
    graph_paths = [p for paths in GRAPH_CATEGORIES.values() for p in paths]

    print("Running benchmarks...")
    print(f"Algorithms: {', '.join(a.name for a in ALGORITHMS)}")
    print(f"Graphs: {', '.join(g.stem for g in graph_paths)}")
    print()

    all_outputs = {}
    log_files  = {}
    meta_files = {}

    if cached_only:
        print("[CACHED-ONLY MODE] Loading only cached results...\n")

    # Run benchmarks for each graph
    for graph in graph_paths:
        print(f"Graph: {graph.stem}")
        graph_hash = hash_file(graph)

        is_cached   = []     # True if this task has a valid cached result
        cached_outputs = []  # cached benchmark stderr, parallel to is_cached
        configs     = []
        log_paths   = []
        meta_paths  = []
        run_cmds    = []
        run_graph_hashes = []

        # Classify each task as cached or pending
        for alg in ALGORITHMS:
            for config_name, flags in alg.flag_configs:
                log_file  = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.log"
                meta_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.meta"
                cmd = [str(alg.path)] + flags + ["-l", str(log_file), str(graph)]

                use_cache     = False
                cached_output = ""
                if log_file.exists() and meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        if meta.get("graph_hash") == graph_hash and meta.get("cmd") == cmd:
                            if meta.get("failed", False):
                                use_cache = True
                                cached_output = ""
                                print(f"  Skipping rerun for {alg.name}_{config_name} (previous benchmark failed)")
                            else:
                                use_cache     = True
                                cached_output = meta.get("benchmark_output", "")
                    except (json.JSONDecodeError, KeyError):
                        pass
                else:
                    if cached_only:
                        print(f"  [SKIP] {alg.name}_{config_name} (no cached files found)")
                        continue

                if use_cache:
                    print(f"  Reusing cached log for {alg.name}_{config_name}")

                configs.append((alg.name, config_name))
                log_paths.append(log_file)
                meta_paths.append(meta_file)
                run_cmds.append(cmd)
                run_graph_hashes.append(graph_hash)
                is_cached.append(use_cache)
                cached_outputs.append(cached_output)

        pending = [i for i, cached in enumerate(is_cached) if not cached]
        
        if cached_only:
            if pending:
                print(f"  [CACHED-ONLY] Skipping {len(pending)} non-cached benchmarks")
        else:
            if pending:
                print(f"  Running {len(pending)} benchmarks...")

        outputs = list(cached_outputs)  # pre-filled with cached values

        if not cached_only:
            for i in pending:
                algo_name, config_name = configs[i]
                print(f"  Running {algo_name}_{config_name}...")
                result = subprocess.run(
                    run_cmds[i],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                failed = result.returncode != 0
                if failed:
                    print(f"  Warning: {algo_name}_{config_name} failed (exit code {result.returncode})")
                outputs[i] = result.stderr
                meta = {
                    "graph_hash": run_graph_hashes[i],
                    "cmd": run_cmds[i],
                    "benchmark_output": result.stderr,
                    "failed": failed,
                }
                meta_paths[i].write_text(json.dumps(meta))
                print(f"  Completed {algo_name}_{config_name}")

        all_outputs[graph] = list(zip(configs, outputs))
        log_files[graph]   = list(zip(configs, log_paths))
        meta_files[graph]  = list(zip(configs, meta_paths))

    # Run analyze_quality on all log files
    # Classify into cached results and pending tasks first
    print("\nRunning analyze_quality on log files...")
    quality_tasks   = []  # (graph, config, meta_path, quality_file, rank_file, log_hash, existing_meta, log_path)
    cached_results  = []  # (graph, config, quality_stderr)

    for graph in log_files:
        for (config, log_path), (_, meta_path) in zip(log_files[graph], meta_files[graph]):
            quality_file = log_path.with_suffix(".quality")
            rank_file    = log_path.with_name(log_path.stem + ".csv")

            existing_meta = {}
            if meta_path.exists():
                try:
                    existing_meta = json.loads(meta_path.read_text())
                except json.JSONDecodeError:
                    pass

            # Skip quality analysis for failed benchmark runs.
            if existing_meta.get("failed", False):
                print(f"  Skipping analyze_quality for {graph.stem}_{config[0]}_{config[1]} (benchmark failed)")
                cached_results.append((graph, config, ""))
                continue

            if not log_path.exists():
                print(f"  Warning: {log_path.name} does not exist, skipping")
                cached_results.append((graph, config, ""))
                continue

            log_hash      = hash_file(log_path)

            if quality_file.exists() and rank_file.exists() and existing_meta.get("log_hash") == log_hash:
                print(f"  Reusing cached quality for {graph.stem}_{config[0]}_{config[1]}")
                cached_results.append((graph, config, quality_file.read_text()))
            else:
                if cached_only:
                    print(f"  [SKIP] analyze_quality for {graph.stem}_{config[0]}_{config[1]} (no cached quality found)")
                    cached_results.append((graph, config, ""))
                else:
                    quality_tasks.append((graph, config, meta_path, quality_file, rank_file, log_hash, existing_meta, log_path))

    fresh_results = []  # (graph, config, quality_stderr)

    if not cached_only and quality_tasks:
        print(f"  Running {len(quality_tasks)} analyze_quality jobs...")

    if not cached_only:
        for graph, config, meta_path, quality_file, rank_file, log_hash, existing_meta, log_path in quality_tasks:
            print(f"  Running analyze_quality for {graph.stem}_{config[0]}_{config[1]}")
            log_content = log_path.read_text()
            result = subprocess.run(
                [str(ANALYZE_QUALITY_PATH)],
                input=log_content,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            quality_file.write_text(result.stderr)
            rank_file.write_text(result.stdout)
            existing_meta["log_hash"] = log_hash
            meta_path.write_text(json.dumps(existing_meta))
            fresh_results.append((graph, config, result.stderr))
            print(f"  Completed analyze_quality for {graph.stem}_{config[0]}_{config[1]}")

    # Merge cached + fresh results, preserving log_files iteration order
    result_map = {(graph, config): output for graph, config, output in chain(cached_results, fresh_results)}
    quality_results = {
        graph: [(config, result_map.get((graph, config), "")) for config, _ in log_files[graph]]
        for graph in log_files
    }
        
    # Parse all results
    graph_results = []
    mismatches = []
    
    results_header = "=" * 60 + "\nRESULTS\n" + "=" * 60
    print(results_header)
    
    with open(OUT_PATH / "overview", 'w') as f:
        for graph in all_outputs:
            print(f"\nGraph: {graph.stem}")
            f.write(f"\nGraph: {graph.stem}\n")
            print("-" * 40)
            f.write("-" * 40 + "\n")
            
            graph_configs = log_files[graph]
            graph_outputs = all_outputs[graph]
            graph_quality = quality_results[graph]
            
            for (config, log_path), (_, stderr), (_, quality_stderr) in zip(graph_configs, graph_outputs, graph_quality):
                if "= Results =" in stderr:
                    algo_name, config_name = config
                    print(f"({algo_name}_{config_name})")
                    f.write(f"({algo_name}_{config_name})\n")
                    
                    # Parse benchmark stderr output
                    result_data = stderr.split("= Results =")[1].strip()
                    
                    gr = GraphResults()
                    gr.name = f"{graph.stem}_{algo_name}_{config_name}"

                    bkv = _parse_kv(result_data)
                    if "Time (s)"          in bkv: gr.time              = float(bkv["Time (s)"])
                    if "Processed nodes"   in bkv: gr.processed_nodes   = int(bkv["Processed nodes"])
                    if "Ignored nodes"     in bkv: gr.ignored_nodes      = int(bkv["Ignored nodes"])
                    if "Edge relaxations"  in bkv: gr.edge_relaxations   = int(bkv["Edge relaxations"])
                    if "Discarded edges"   in bkv: gr.discarded_edges    = int(bkv["Discarded edges"])

                    qkv = _parse_kv(quality_stderr)
                    if "Average rank error" in qkv: gr.average_rank_error = float(qkv["Average rank error"])
                    if "Average delay"      in qkv: gr.average_delay      = float(qkv["Average delay"])
                    if "Average PQ size"    in qkv: gr.average_pq_size    = float(qkv["Average PQ size"])
                    if "Max PQ size"        in qkv: gr.max_pq_size        = int(qkv["Max PQ size"])
                    
                    graph_results.append(gr)
                    
                    if gr.average_rank_error != gr.average_delay:
                        mismatches.append((graph.stem, algo_name, config_name))
                    
                    print(result_data)
                    f.write(result_data + "\n")
                    
                    # Print quality analysis output (skip "Reading log...", "Analyzing log...", "Writing metrics..." lines)
                    quality_lines = [line for line in quality_stderr.split('\n') if line.strip() and 'Analyzing log' not in line and 'Reading log' not in line and 'Writing metrics' not in line]
                    quality_output = '\n'.join(quality_lines)
                    print(quality_output)
                    f.write(quality_output + "\n")
                    print("-" * 20)
                    f.write("-" * 20 + "\n")

    if mismatches:
        print("\n" + "=" * 60)
        print("RANK ERROR vs DELAY MISMATCHES")
        print("=" * 60)
        for graph, algo, config in mismatches:
            print(f"  {graph}_{algo}_{config}")

    return graph_results


def analyze_results(graph_results):
    """
    Analyze benchmark results with cross-graph and within-graph comparisons.
    
    For within-graph comparisons, the first algorithm in the ALGORITHMS list
    is used as the baseline/reference for computing ratios.
    """
    if not graph_results:
        print("No results to analyze")
        return
    
    # Determine baseline algorithm (first in ALGORITHMS list)
    baseline_algo_name = ALGORITHMS[0].name
    
    # Group results by graph and by config
    # Build list of known graph stems from all categories
    known_graphs = [p.stem for paths in GRAPH_CATEGORIES.values() for p in paths]

    by_graph  = {}
    by_config = {}

    for gr in graph_results:
        graph_base = None
        algo_config = None

        for known_graph in known_graphs:
            if gr.name.startswith(known_graph + '_'):
                graph_base  = known_graph
                algo_config = gr.name[len(known_graph) + 1:]
                break

        if not graph_base:
            raise RuntimeError(f"Result name '{gr.name}' does not match any known graph from GRAPH_CATEGORIES")

        by_graph.setdefault(graph_base, {})[algo_config] = gr
        by_config.setdefault(algo_config, {})[graph_base] = gr

    # Map each category name → set of graph stems for routing cross-graph rows
    category_stems = {cat: {p.stem for p in paths} for cat, paths in GRAPH_CATEGORIES.items()}

    def _print_cross_graph_section(subset_filter: set):
        """Print cross-graph comparison rows for graphs whose names are in subset_filter."""
        printed_any = False
        for config in sorted(by_config.keys()):
            graphs_in_config = by_config[config]
            subset = {g: v for g, v in graphs_in_config.items() if g in subset_filter}
            if len(subset) < 2:
                continue

            print(f"\n--- Configuration: {config} ---")
            printed_any = True

            sorted_graphs = sorted(subset.keys())
            baseline_graph = sorted_graphs[0]
            baseline = subset[baseline_graph]

            col_w = max(20, max(len(g) for g in sorted_graphs) + 2)
            sep_w = col_w + 10 + 14 + 14 + 12 + 12 + 15
            print(f"{'Graph':<{col_w}} {'Time(r)':<10} {'Proc.Nodes(r)':<14} {'Ign.Nodes(r)':<14} {'Avg.PQ(i)':<12} {'Max.PQ(i)':<12} {'Avg.Rank.Err(f)':<15}")
            print("-" * sep_w)
            print(f"{baseline_graph:<{col_w}} {'1.0000':<10} {'1.0000':<14} {'1.0000':<14} {baseline.average_pq_size:<12.0f} {baseline.max_pq_size:<12} {baseline.average_rank_error:<15.5f}")

            for graph_name in sorted_graphs:
                if graph_name == baseline_graph:
                    continue
                gr = subset[graph_name]

                time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
                proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
                ign_ratio  = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0

                print(f"{graph_name:<{col_w}} {time_ratio:<10.4f} {proc_ratio:<14.4f} {ign_ratio:<14.4f} {gr.average_pq_size:<12.0f} {gr.max_pq_size:<12} {gr.average_rank_error:<15.5f}")

        if not printed_any:
            print("  (fewer than 2 graphs with results — nothing to compare)")

    # Cross-graph comparison — one section per category
    for category, stems in category_stems.items():
        print("\n" + "=" * 60)
        print(f"CROSS-GRAPH COMPARISON ({category})")
        print("=" * 60)
        _print_cross_graph_section(stems)
    
    # Within-graph comparison (same graph, different configs)
    print("\n" + "=" * 60)
    print("WITHIN-GRAPH COMPARISON (baseline as reference)")
    print("=" * 60)
    
    for graph_name in sorted(by_graph.keys()):
        configs_in_graph = by_graph[graph_name]
        if len(configs_in_graph) < 2:
            continue
        
        # Sort config names once and reuse
        sorted_configs = sorted(configs_in_graph.keys())
        
        # Use first algorithm in ALGORITHMS list as reference
        baseline = None
        reference_name = None
        
        # Find first config from baseline algorithm
        for config_name in sorted_configs:
            if config_name.startswith(baseline_algo_name + "_"):
                baseline = configs_in_graph[config_name]
                reference_name = config_name
                break
        
        # Skip this graph if baseline algorithm didn't run
        if not baseline:
            print(f"\nWarning: Baseline algorithm '{baseline_algo_name}' has no results for graph '{graph_name}'. Skipping comparison.")
            continue
        
        print(f"\n--- Graph: {graph_name} (reference: {reference_name}) ---")
        col_w = max(25, max(len(c) for c in sorted_configs) + 2)
        sep_w = col_w + 10 + 14 + 14 + 16 + 12 + 16 + 12 + 12 + 15
        print(f"{'Config':<{col_w}} {'Time(r)':<10} {'Proc.Nodes(r)':<14} {'Ign.Nodes(r)':<14} {'Work.Eff(f)':<12} {'Throughput(n/s)':<16} {'Eff.Tput(n/s)':<16} {'Avg.PQ(i)':<12} {'Max.PQ(i)':<12} {'Avg.Rank.Err(f)':<15}")
        print("-" * sep_w)
        
        for config in sorted_configs:
            gr = configs_in_graph[config]
            
            time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
            proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
            ign_ratio = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0
            throughput = gr.processed_nodes / gr.time if gr.time > 0 else 0
            work_efficiency = baseline.processed_nodes / gr.processed_nodes if gr.processed_nodes > 0 else 0
            effective_throughput = throughput * work_efficiency
            
            print(f"{config:<{col_w}} {time_ratio:<10.4f} {proc_ratio:<14.4f} {ign_ratio:<14.4f} {work_efficiency:<12.5f} {throughput:<16.0f} {effective_throughput:<16.0f} {gr.average_pq_size:<12.0f} {gr.max_pq_size:<12} {gr.average_rank_error:<15.5f}")
    
    print("\n" + "=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Benchmark pathfinding algorithms")
    parser.add_argument(
        "--cached-only",
        action="store_true",
        help="Only load and analyze cached results; skip running benchmarks and quality analysis"
    )
    args = parser.parse_args()
    
    check_graphs()
    results = run_benchmarks(cached_only=args.cached_only)
    analyze_results(results)
    print("done :(")


if __name__ == "__main__":
    main()
