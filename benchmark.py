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
        # SOCIAL_GRAPHS_PATH / "mawi_graph1.gr",
        # SOCIAL_GRAPHS_PATH / "example.gr",
        # SOCIAL_GRAPHS_PATH / "mawi_graph1.gr",
    ],
    "Random Graphs": [
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s1.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s2.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s3.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s4.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X10_Y10_s5.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s1.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s2.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s3.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s4.gr",
        RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s5.gr",
        # RANDOM_GRAPHS_PATH / "example.gr",
    ],
    "Random Hyperbolic Graphs": [
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18_s1.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18_s2.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18_s4.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18_s5.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20_s1.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20_s2.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20_s4.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_20_s5.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s1.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s2.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s4.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_22_s5.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_s1.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_s2.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_s3.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_s4.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_s5.gr",
        RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_24_deg8_s1.gr",
        # RANDOM_HYPERBOLIC_GRAPHS_PATH / "the_rhg.gr",
        # RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18.gr",
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
    # AlgorithmConfig(
    #     path="multiqueue_experiments/build/benchmarks/dijkstra_log_mq_stick_swap",
    #     name="mq_ss256",
    #     flag_configs=[
    #         ("t32_c4", ["-j", "32", "-k", "256", "-c", "4"]),
    #         ("t32_c8", ["-j", "32", "-k", "256", "-c", "8"]),
    #         ("t32_c16", ["-j", "32", "-k", "256", "-c", "16"]),
    #     ]
    # ),
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
    """Check if all graphs exist. Return list of missing graphs."""
    missing = []
    for category, paths in GRAPH_CATEGORIES.items():
        for path in paths:
            if not path.exists():
                missing.append((category, str(path)))
    return missing


def run_benchmarks(cached_only=False):
    """
    Run all configured algorithms on all graphs and analyze quality.

    Args:
        cached_only: If True, only load and analyze cached results; skip running benchmarks

    Returns:
        Tuple of (graph_results, failures) where failures is a list of failure messages

    Results are cached using .meta files. Each .meta file contains:
      - graph_hash + cmd: validates the config belongs to this graph
      - benchmark_output: stderr from running the benchmark
      - quality_output: stderr from analyze_quality
      - quality_stdout: stdout from analyze_quality (csv format)
      - complete: True if both benchmark and analyze_quality succeeded
      - benchmark_failed: True if benchmark failed
      - quality_failed: True if analyze_quality failed
    
    Log files (.log) are deleted after successful quality analysis.
    Cached results are only reused when complete=True.
    """
    algo_failures = []
    cache_failures = []
    
    if not ALGORITHMS:
        raise RuntimeError("ALGORITHMS list is empty. At least one algorithm must be configured.")

    # Check for missing algorithms but don't fail
    available_algs = []
    for alg in ALGORITHMS:
        if not alg.path.exists():
            algo_failures.append(f"Algorithm '{alg.name}' not found at {alg.path}")
        else:
            available_algs.append(alg)
    
    if not available_algs:
        raise RuntimeError("No algorithms found. Build multiqueue_experiments then try again.")

    if not ANALYZE_QUALITY_PATH.exists():
        raise RuntimeError("analyze_quality not found, build multiqueue_experiments then continue")

    # Create output directory
    OUT_PATH.mkdir(exist_ok=True)

    # Flatten all graph paths from every category in order (skip missing ones)
    graph_paths = [p for paths in GRAPH_CATEGORIES.values() for p in paths if p.exists()]

    print("Running benchmarks...")
    print(f"Algorithms: {', '.join(a.name for a in ALGORITHMS)}")
    print(f"Graphs: {', '.join(g.stem for g in graph_paths)}")
    print()

    meta_files = {}

    if cached_only:
        print("[CACHED-ONLY MODE] Loading only cached results...\n")

    # Run benchmarks for each graph
    for graph in graph_paths:
        print(f"Graph: {graph.stem}")
        graph_hash = hash_file(graph)

        configs     = []
        meta_paths  = []
        run_cmds    = []
        run_graph_hashes = []
        is_complete = []     # True if cached complete result exists
        is_recovery = []     # True if orphaned log file found (meta missing)

        # Classify each task as cached or pending
        for alg in available_algs:
            for config_name, flags in alg.flag_configs:
                log_file  = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.log"
                meta_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.meta"
                csv_file  = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.csv"
                cmd = [str(alg.path)] + flags + ["-l", str(log_file), str(graph)]

                use_cache = False
                recover = False
                
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        if meta.get("graph_hash") == graph_hash and meta.get("cmd") == cmd:
                            if meta.get("complete", False):
                                # Complete run cached - verify CSV exists
                                if csv_file.exists():
                                    use_cache = True
                                    print(f"  Reusing cached run for {alg.name}_{config_name}")
                                else:
                                    # Meta says complete but CSV is missing, re-run
                                    cache_failures.append(f"Incomplete cache for {alg.name}_{config_name} (CSV missing)")
                    except (json.JSONDecodeError, KeyError):
                        pass
                elif log_file.exists():
                    # Orphaned log file (meta missing) - try to recover by analyzing it
                    recover = True
                    print(f"  Recovering {alg.name}_{config_name} (found orphaned log, will analyze)")
                
                if not use_cache and cached_only:
                    print(f"  [SKIP] {alg.name}_{config_name} (no cached run found)")
                    continue

                configs.append((alg.name, config_name))
                meta_paths.append(meta_file)
                run_cmds.append(cmd)
                run_graph_hashes.append(graph_hash)
                is_complete.append(use_cache)
                is_recovery.append(recover)

        pending = [i for i, complete in enumerate(is_complete) if not complete]
        
        if cached_only:
            if pending:
                print(f"  [CACHED-ONLY] Skipping {len(pending)} non-cached benchmarks")
        else:
            if pending:
                print(f"  Running {len(pending)} benchmarks...")

        # Run benchmark + analyze_quality for pending tasks
        if not cached_only:
            for i in pending:
                algo_name, config_name = configs[i]
                log_file = OUT_PATH / f"{graph.stem}_{algo_name}_{config_name}.log"
                csv_file = OUT_PATH / f"{graph.stem}_{algo_name}_{config_name}.csv"
                err_file = OUT_PATH / f"{graph.stem}_{algo_name}_{config_name}.err"
                quality_file = log_file.with_suffix(".quality")
                
                # For recovery cases (orphaned log), skip benchmark and go straight to analysis
                if is_recovery[i]:
                    print(f"  Analyzing log of {algo_name}_{config_name}...")
                    if not log_file.exists():
                        # Log disappeared, mark both as failed
                        meta = {
                            "graph_hash": run_graph_hashes[i],
                            "cmd": run_cmds[i],
                            "benchmark_failed": True,
                            "benchmark_output": "",
                            "quality_output": "",
                            "quality_failed": True,
                            "complete": False,
                        }
                        meta_paths[i].write_text(json.dumps(meta))
                        err_file.write_text("ERROR: Log file disappeared before analysis\n")
                        print(f"  Warning: {algo_name}_{config_name} log disappeared (both benchmark and analysis failed)")
                        continue
                    
                    # Try to analyze existing log
                    # Use stdin/stdout redirection like: analyze_quality < log > csv
                    quality_output = ""
                    with open(log_file, 'r') as log_in, open(csv_file, 'w') as csv_out:
                        proc = subprocess.Popen(
                            [str(ANALYZE_QUALITY_PATH)],
                            stdin=log_in,
                            stdout=csv_out,
                            stderr=subprocess.PIPE,
                            text=True,
                        )
                        _, quality_output = proc.communicate()
                        quality_failed = proc.returncode != 0
                    
                    meta = {
                        "graph_hash": run_graph_hashes[i],
                        "cmd": run_cmds[i],
                        "benchmark_failed": quality_failed,  # Mark benchmark as failed if recovery analysis fails
                        "quality_output": quality_output,
                        "quality_failed": quality_failed,
                        "complete": not quality_failed,
                    }
                    
                    if quality_failed:
                        print(f"  Warning: {algo_name}_{config_name} analysis failed (exit code {proc.returncode})")
                        err_file.write_text(quality_output)
                    else:
                        if log_file.exists():
                            log_file.unlink()
                    
                    meta_paths[i].write_text(json.dumps(meta))
                    print(f"  Completed {algo_name}_{config_name}!")
                    continue
                
                # Regular path: run benchmark
                print(f"  Running {algo_name}_{config_name}...")
                result = subprocess.run(
                    run_cmds[i],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                benchmark_failed = result.returncode != 0
                benchmark_output = result.stderr
                
                meta = {
                    "graph_hash": run_graph_hashes[i],
                    "cmd": run_cmds[i],
                    "benchmark_failed": benchmark_failed,
                    "benchmark_output": benchmark_output,
                    "quality_failed": False,
                    "complete": False,
                }
                
                if benchmark_failed:
                    print(f"  Warning: {algo_name}_{config_name} benchmark failed (exit code {result.returncode})")
                    err_file.write_text(benchmark_output)
                    meta_paths[i].write_text(json.dumps(meta))
                    continue
                
                # Benchmark succeeded, run analyze_quality immediately
                print(f"  Analyzing log of {algo_name}_{config_name}...")
                
                # Use stdin/stdout redirection like: analyze_quality < log > csv
                quality_output = ""
                with open(log_file, 'r') as log_in, open(csv_file, 'w') as csv_out:
                    proc = subprocess.Popen(
                        [str(ANALYZE_QUALITY_PATH)],
                        stdin=log_in,
                        stdout=csv_out,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    _, quality_output = proc.communicate()
                    quality_failed = proc.returncode != 0
                
                if quality_failed:
                    print(f"  Warning: {algo_name}_{config_name} analysis failed (exit code {proc.returncode})")
                    err_file.write_text(quality_output)
                    meta["quality_failed"] = True
                    meta["quality_output"] = quality_output
                    meta_paths[i].write_text(json.dumps(meta))
                    continue
                
                # Both succeeded: save results and delete log
                meta["benchmark_output"] = benchmark_output
                meta["quality_output"] = quality_output
                meta["complete"] = True
                meta_paths[i].write_text(json.dumps(meta))
                
                # Delete log file to save space
                if log_file.exists():
                    log_file.unlink()
                
                print(f"  Completed {algo_name}_{config_name}!")
        
        meta_files[graph] = list(zip(configs, meta_paths))


    # Parse all results
    graph_results = []
    mismatches = []
    
    results_header = "=" * 60 + "\nRESULTS\n" + "=" * 60
    print(results_header)
    
    with open(OUT_PATH / "overview", 'w') as f:
        for graph in meta_files:
            print(f"\nGraph: {graph.stem}")
            f.write(f"\nGraph: {graph.stem}\n")
            print("-" * 40)
            f.write("-" * 40 + "\n")
            
            for config, meta_path in meta_files[graph]:
                algo_name, config_name = config
                
                # Read meta file to check if run is complete
                is_complete = False
                benchmark_output = ""
                quality_stderr = ""
                try:
                    meta = json.loads(meta_path.read_text())
                    is_complete = meta.get("complete", False)
                    benchmark_output = meta.get("benchmark_output", "")
                    quality_stderr = meta.get("quality_output", "")
                except (json.JSONDecodeError, FileNotFoundError):
                    pass
                
                csv_file = OUT_PATH / f"{graph.stem}_{algo_name}_{config_name}.csv"
                if not is_complete and not csv_file.exists():
                    continue
                
                print(f"({algo_name}_{config_name})")
                f.write(f"({algo_name}_{config_name})\n")
                
                gr = GraphResults()
                gr.name = f"{graph.stem}_{algo_name}_{config_name}"

                # Parse benchmark results from the meta file
                if "= Results =" in benchmark_output:
                    result_data = benchmark_output.split("= Results =")[1].strip()
                    print(result_data)
                    f.write(result_data + "\n")
                    
                    bkv = _parse_kv(result_data)
                    if "Time (s)"          in bkv: gr.time              = float(bkv["Time (s)"])
                    if "Processed nodes"   in bkv: gr.processed_nodes   = int(bkv["Processed nodes"])
                    if "Ignored nodes"     in bkv: gr.ignored_nodes      = int(bkv["Ignored nodes"])
                    if "Edge relaxations"  in bkv: gr.edge_relaxations   = int(bkv["Edge relaxations"])
                    if "Discarded edges"   in bkv: gr.discarded_edges    = int(bkv["Discarded edges"])

                # Parse quality metrics from meta file
                qkv = _parse_kv(quality_stderr)
                if "Average rank error" in qkv: gr.average_rank_error = float(qkv["Average rank error"])
                if "Average delay"      in qkv: gr.average_delay      = float(qkv["Average delay"])
                if "Average PQ size"    in qkv: gr.average_pq_size    = float(qkv["Average PQ size"])
                if "Max PQ size"        in qkv: gr.max_pq_size        = int(qkv["Max PQ size"])
                
                graph_results.append(gr)
                
                if gr.average_rank_error != gr.average_delay:
                    mismatches.append((graph.stem, algo_name, config_name))
                
                # Print quality analysis output (skip internal messages, read from file on-demand)
                quality_lines = [line for line in quality_stderr.split('\n') if line.strip() and 'Analyzing log' not in line and 'Reading log' not in line and 'Writing metrics' not in line]
                quality_output = '\n'.join(quality_lines)
                print(quality_output)
                f.write(quality_output + "\n")
                print("-" * 20)
                f.write("-" * 20 + "\n")

    return graph_results, algo_failures, cache_failures, mismatches


def analyze_results(graph_results, algo_failures=None, cache_failures=None, graph_failures=None, mismatches=None):
    """
    Analyze benchmark results with cross-graph and within-graph comparisons.
    
    For within-graph comparisons, the first algorithm in the ALGORITHMS list
    is used as the baseline/reference for computing ratios.
    
    Args:
        graph_results: List of GraphResults objects
        algo_failures: List of missing algorithm messages
        cache_failures: List of incomplete cache messages
        graph_failures: List of missing graph messages
        mismatches: List of (graph, algo, config) tuples with rank error vs delay mismatches
    """
    if algo_failures is None:
        algo_failures = []
    if cache_failures is None:
        cache_failures = []
    if graph_failures is None:
        graph_failures = []
    if mismatches is None:
        mismatches = []
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
    
    # Display warnings and failures
    if algo_failures or cache_failures or graph_failures or mismatches:
        print("\n" + "=" * 60)
        print("WARNINGS")
        print("=" * 60)
        
        if algo_failures:
            print("Algorithms not found:")
            for failure in algo_failures:
                print(f"  {failure}")
        
        if cache_failures:
            if algo_failures:
                print()
            print("Cache issues:")
            for failure in cache_failures:
                print(f"  {failure}")
        
        if graph_failures:
            if algo_failures or cache_failures:
                print()
            print("Graphs not found:")
            for failure in graph_failures:
                print(f"  {failure}")
        
        if mismatches:
            if algo_failures or cache_failures or graph_failures:
                print()
            print("Rank error vs delay mismatches:")
            for graph, algo, config in mismatches:
                print(f"  {graph}_{algo}_{config}")
    
    print("\n" + "=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Benchmark pathfinding algorithms")
    parser.add_argument(
        "--cached-only",
        action="store_true",
        help="Only load and analyze cached results; skip running benchmarks and quality analysis"
    )
    args = parser.parse_args()
    
    missing_graphs = check_graphs()
    results, algo_failures, cache_failures, mismatches = run_benchmarks(cached_only=args.cached_only)
    
    # Format graph failures
    graph_failures = []
    for category, path in missing_graphs:
        graph_failures.append(f"[{category}]: {path}")
    
    analyze_results(results, algo_failures=algo_failures, cache_failures=cache_failures, graph_failures=graph_failures, mismatches=mismatches)
    print("done :)")


if __name__ == "__main__":
    main()
