"""
Benchmark Suite for Pathfinding Algorithms

This script runs multiple pathfinding algorithms on various graphs and analyzes their quality.
All algorithms must:
  - Support -j (num threads) and -l (log file) flags
  - Output logs compatible with analyze_quality tool
  - Print results to stderr in the expected format

To add a new algorithm:
  1. Add an AlgorithmConfig to the ALGORITHMS list below
  2. Provide: executable path, name, and flag configurations
  
Example:
    ALGORITHMS.append(AlgorithmConfig(
        path="path/to/my_algorithm",
        name="myalgo",
        flag_configs=[
            ("config1", ["--flag1", "value1"]),
            ("config2", ["--flag1", "value2", "--flag2", "value3"]),
        ]
    ))

IMPORTANT: The first algorithm in the ALGORITHMS list is used as the baseline/reference
           for within-graph comparisons. Place your reference implementation first.

To add a new randomly generated graph:
  1. Add a tuple to the RANDOM_GRAPHS list: (filename, min_weight, max_weight)
  2. The new graph will then be generated using KaGen

To add a pre-existing graph (e.g. road networks, DIMACS benchmarks):
  1. Add its path to the OTHER_GRAPHS list
  2. The file must already exist on disk — it will only be validated, never generated
"""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys


# ===== Configuration =====
GRAPH_FOLDER = "graphs"
BASE_GRAPH_NAME = "base_gnm_edgelist"
RANDOM_WEIGHT_SCRIPT = "random_weight_distributor.py"
OUT_PATH = Path("out")

# Graph paths
KAGEN_PATH = Path("KaGen/build/app/KaGen")
BASE_GRAPH_PATH = Path(GRAPH_FOLDER) / BASE_GRAPH_NAME
WEIGHT_SCRIPT_PATH = Path(GRAPH_FOLDER) / RANDOM_WEIGHT_SCRIPT

# Graph definitions (name, weight_min, weight_max)
RANDOM_GRAPHS = [
    #("gnm_1-10.gr", 1, 10),
    ("gnm_1-100.gr", 1, 100),
    ("gnm_1-1000.gr", 1, 1000),
    ("gnm_1-10000.gr", 1, 10000),
]

# Pre-existing graphs to benchmark alongside the generated ones.
# Each entry is a path to an already-present .gr file.
OTHER_GRAPHS = [
    Path("graphs/NY.gr"),
    #Path("graphs/full_USA.gr"),
    Path("graphs/rhg.gr"),
]

# Tool paths
ANALYZE_QUALITY_PATH = Path("multiqueue_experiments/build/tools/analyze_quality")

MAX_THREADS = 10

class AlgorithmConfig:
    """Configuration for a pathfinding algorithm."""
    def __init__(self, path, name, flag_configs=None):
        """
        Args:
            path: Path to the executable
            name: Name identifier for the algorithm
            flag_configs: List of (config_name, flags_list) tuples
                         e.g., [("default", []), ("relaxed", ["--mean", "1"])]
                         Include -j and -l flags here as needed
        """
        self.path = Path(path)
        self.name = name
        self.flag_configs = flag_configs or [("default", [])]


# Algorithm definitions
# NOTE: The FIRST algorithm in this list is used as the baseline for within-graph comparisons
ALGORITHMS = [
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_locked_pq",
        name="dijkstra",
        flag_configs=[
            ("seq", ["-j", "1"]),
            #("t_8", ["-j", "8"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_dr_pq",
        name="drpq",
        flag_configs=[
            ("mean0", ["-j", "1", "--mean", "0", "--stddev", "0"]),
            ("mean1", ["-j", "1", "--mean", "1", "--stddev", "0"]),
        ]
    ),
    # AlgorithmConfig(
    #     path="multiqueue_experiments/build/benchmarks/dijkstra_log_dr_pq_buffered",
    #     name="drpq_buffered",
    #     flag_configs=[
    #         ("mean5_stddev5_t8", ["-j", "8", "--mean", "5", "--stddev", "5"]),
    #         #("mean1_t8", ["-j", "8", "--mean", "1", "--stddev", "0"]),
    #         ("mean1_t1", ["-j", "1", "--mean", "1", "--stddev", "0"]),
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


def hash_file(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _threads_for_flags(flags: list) -> int:
    """Return the -j thread count from a specific flag list, defaulting to 4."""
    for k, flag in enumerate(flags):
        if flag == "-j" and k + 1 < len(flags):
            try:
                return int(flags[k + 1])
            except ValueError:
                pass
    return 4


def check_build_graphs():
    """Ensure base graph and weighted variants exist; validate other_graphs are present."""
    if not BASE_GRAPH_PATH.exists():
        if not KAGEN_PATH.exists():
            raise RuntimeError("Kagen does not exist, build KaGen then continue")
        
        print("Base graph does not exist, building it")
        args = ["gnm-directed", "-m", "15403114", "-N", "20", "-f", "edgelist", "-o", str(BASE_GRAPH_PATH)]
        subprocess.run([str(KAGEN_PATH)] + args, capture_output=True, text=True, check=True)
    
    processes = []
    for graph_name, weight_min, weight_max in RANDOM_GRAPHS:
        graph_path = Path(GRAPH_FOLDER) / graph_name
        if not graph_path.exists():
            print(f"{graph_name} does not exist, creating...")
            args = [str(BASE_GRAPH_PATH), str(graph_path), str(weight_min), str(weight_max)]
            process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
            processes.append(process)
    
    if processes:
        print(f"Creating {len(processes)} graphs in parallel...")
        for process in processes:
            process.wait()
        print("Graph creation complete")

    for graph_path in OTHER_GRAPHS:
        if not Path(graph_path).exists():
            raise RuntimeError(f"Graph not found: {graph_path}")


def run_benchmarks():
    """
    Run all configured algorithms on all graphs and analyze quality.

    Results are cached using .meta files stored alongside each log file.
    Each .meta file contains:
      - graph_hash + cmd: validates that the log belongs to this graph and config
      - log_hash + quality_output: validates that the quality result belongs to this log
    A cached result is only reused when the full chain is verified.
    """
    # Verify ALGORITHMS is not empty and all algorithms exist
    if not ALGORITHMS:
        raise RuntimeError("ALGORITHMS list is empty. At least one algorithm must be configured.")
    
    for algo in ALGORITHMS:
        if not algo.path.exists():
            raise RuntimeError(f"{algo.name} not found at {algo.path}, build multiqueue_experiments then continue")
    
    if not ANALYZE_QUALITY_PATH.exists():
        raise RuntimeError("analyze_quality not found, build multiqueue_experiments then continue")
    
    # Create output directory
    OUT_PATH.mkdir(exist_ok=True)
    
    # Get graph paths — generated random graphs first, then pre-existing other graphs
    graph_paths = [Path(GRAPH_FOLDER) / name for name, _, _ in RANDOM_GRAPHS]
    graph_paths += [Path(p) for p in OTHER_GRAPHS]
    
    print("Running benchmarks...")
    print(f"Algorithms: {', '.join(a.name for a in ALGORITHMS)}")
    print(f"Graphs: {', '.join(g.stem for g in graph_paths)}")
    print()
    
    all_outputs = {}
    log_files = {}
    # meta_paths mirrors log_files: (config, meta_path) per entry
    meta_files = {}
    quality_files = {}
    
    # Run benchmarks for each graph
    for graph in graph_paths:
        print(f"Graph: {graph.stem}")
        graph_hash = hash_file(graph)
        
        processes = []       # None if cached, "pending" if needs fresh run
        cached_outputs = []  # cached benchmark stderr, parallel to processes
        configs = []
        log_paths = []
        meta_paths = []
        run_cmds = []
        run_graph_hashes = []
        job_threads = []     # thread count per job, for CPU-aware scheduling

        # Classify each task as cached or pending (no Popen yet)
        for algo in ALGORITHMS:
            for config_name, flags in algo.flag_configs:
                log_file = OUT_PATH / f"{graph.stem}_{algo.name}_{config_name}.log"
                meta_file = OUT_PATH / f"{graph.stem}_{algo.name}_{config_name}.meta"
                cmd = [str(algo.path)] + flags + ["-l", str(log_file), str(graph)]

                use_cache = False
                cached_output = ""
                if log_file.exists() and meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        if meta.get("graph_hash") == graph_hash and meta.get("cmd") == cmd:
                            use_cache = True
                            cached_output = meta.get("benchmark_output", "")
                    except (json.JSONDecodeError, KeyError):
                        pass

                if use_cache:
                    print(f"  Reusing cached log for {algo.name}_{config_name}")

                configs.append((algo.name, config_name))
                log_paths.append(log_file)
                meta_paths.append(meta_file)
                run_cmds.append(cmd)
                run_graph_hashes.append(graph_hash)
                processes.append(None if use_cache else "pending")
                cached_outputs.append(cached_output)
                job_threads.append(_threads_for_flags(flags))

        # Launch pending benchmarks using ordered first-fit bin-packing:
        # accumulate jobs in order until adding the next one would exceed cpu_count,
        # then flush the batch. This respects each job's actual -j value rather than
        # using the global maximum, so 1-thread jobs share slots with 8-thread jobs.
        cpu_count = MAX_THREADS or 1
        pending = [(i, job_threads[i]) for i, p in enumerate(processes) if p == "pending"]
        if pending:
            print(f"  Running {len(pending)} benchmarks...")

        outputs = list(cached_outputs)  # pre-filled with cached values

        def _run_batch(batch_indices):
            active = []
            for i in batch_indices:
                algo_name, config_name = configs[i]
                print(f"  Starting {algo_name}_{config_name}...")
                proc = subprocess.Popen(
                    run_cmds[i],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                active.append((i, proc))
            for i, proc in active:
                algo_name, config_name = configs[i]
                _, stderr = proc.communicate()
                outputs[i] = stderr
                meta = {
                    "graph_hash": run_graph_hashes[i],
                    "cmd": run_cmds[i],
                    "benchmark_output": stderr,
                }
                meta_paths[i].write_text(json.dumps(meta))
                print(f"  Completed {algo_name}_{config_name}")

        current_batch = []
        current_threads = 0
        for i, threads in pending:
            if current_batch and current_threads + threads > cpu_count:
                _run_batch(current_batch)
                current_batch = []
                current_threads = 0
            current_batch.append(i)
            current_threads += threads
        if current_batch:
            _run_batch(current_batch)

        quality_paths = [OUT_PATH / f"{graph.stem}_{c[0]}_{c[1]}.quality" for c in configs]
        all_outputs[graph] = list(zip(configs, outputs))
        log_files[graph] = list(zip(configs, log_paths))
        meta_files[graph] = list(zip(configs, meta_paths))
        quality_files[graph] = list(zip(configs, quality_paths))
    
    # Run analyze_quality on all log files in batches
    # Classify into cached results and pending tasks first (no Popen yet)
    print("\nRunning analyze_quality on log files...")
    # Each entry: (graph, config, output_str) for cached, or None for pending
    quality_tasks = []   # (graph, config, meta_path, quality_file, log_hash, existing_meta, log_content)
                         # log_content is None when cached
    cached_results = []  # (graph, config, cached_str)

    for graph in log_files:
        for (config, log_path), (_, meta_path), (_, quality_file) in zip(log_files[graph], meta_files[graph], quality_files[graph]):
            if not log_path.exists():
                print(f"  Warning: {log_path.name} does not exist, skipping")
                cached_results.append((graph, config, ""))
                continue

            log_hash = hash_file(log_path)

            use_cache = False
            existing_meta = {}
            if meta_path.exists():
                try:
                    existing_meta = json.loads(meta_path.read_text())
                except json.JSONDecodeError:
                    pass
            if quality_file.exists() and existing_meta.get("log_hash") == log_hash:
                use_cache = True

            if use_cache:
                print(f"  Reusing cached quality for {graph.stem}_{config[0]}_{config[1]}")
                cached_results.append((graph, config, quality_file.read_text()))
            else:
                # Store the path only — log content is read at batch-launch time
                # so only one batch-worth of log data is in memory at once.
                quality_tasks.append((graph, config, meta_path, quality_file, log_hash, existing_meta, log_path))

    # Process pending tasks in CPU-aware batches.
    # analyze_quality is single-threaded, so max_j=1 → batch size = cpu_count.
    max_parallel = MAX_THREADS or 1
    fresh_results = []  # (graph, config, stderr)

    if quality_tasks:
        print(f"  Running {len(quality_tasks)} analyze_quality jobs...")

    for batch_start in range(0, len(quality_tasks), max_parallel):
        batch = quality_tasks[batch_start:batch_start + max_parallel]
        # Read log contents and launch all processes in the batch.
        # Reading happens here (not during classification) so only this batch's
        # log files occupy memory at once rather than all pending logs at once.
        procs = []
        batch_contents = []
        for graph, config, meta_path, quality_file, log_hash, existing_meta, log_path in batch:
            print(f"  Starting analyze_quality for {graph.stem}_{config[0]}_{config[1]}")
            log_content = log_path.read_text()
            batch_contents.append(log_content)
            proc = subprocess.Popen(
                [str(ANALYZE_QUALITY_PATH)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            procs.append(proc)

        # communicate(input=...) internally threads stdin-write and stdout/stderr-drain
        # to prevent pipe-buffer deadlocks on large log files.
        # Processes in the batch run in parallel; we collect them sequentially —
        # total wait equals the slowest job in the batch.
        for (graph, config, meta_path, quality_file, log_hash, existing_meta, log_path), proc, log_content in zip(batch, procs, batch_contents):
            _, stderr = proc.communicate(input=log_content)
            quality_file.write_text(stderr)
            existing_meta["log_hash"] = log_hash
            meta_path.write_text(json.dumps(existing_meta))
            fresh_results.append((graph, config, stderr))
            print(f"  Completed analyze_quality for {graph.stem}_{config[0]}_{config[1]}")

        # Explicitly release this batch's log contents before loading the next batch.
        batch_contents.clear()

    # Merge cached + fresh results into quality_results dict, preserving
    # the original log_files iteration order so downstream positional zips work.
    result_map = {(id(graph), config): output for graph, config, output in cached_results + fresh_results}
    quality_results = {}
    for graph in log_files:
        quality_results[graph] = []
        for config, log_path in log_files[graph]:
            key = (id(graph), config)
            quality_results[graph].append((config, result_map.get(key, "")))
    
    # Parse all results
    graph_results = []
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for graph in all_outputs:
        print(f"\nGraph: {graph.stem}")
        print("-" * 40)
        
        graph_configs = log_files[graph]
        graph_outputs = all_outputs[graph]
        graph_quality = quality_results[graph]
        
        for (config, log_path), (_, stderr), (_, quality_stderr) in zip(graph_configs, graph_outputs, graph_quality):
            if "= Results =" in stderr:
                algo_name, config_name = config
                print(f"({algo_name}_{config_name})")
                
                # Parse benchmark stderr output
                result_data = stderr.split("= Results =")[1].strip()
                
                gr = GraphResults()
                gr.name = f"{graph.stem}_{algo_name}_{config_name}"
                
                for line in result_data.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == "Time (s)":
                            gr.time = float(value)
                        elif key == "Processed nodes":
                            gr.processed_nodes = int(value)
                        elif key == "Ignored nodes":
                            gr.ignored_nodes = int(value)
                        elif key == "Edge relaxations":
                            gr.edge_relaxations = int(value)
                        elif key == "Discarded edges":
                            gr.discarded_edges = int(value)
                
                # Parse analyze_quality stderr output
                for line in quality_stderr.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == "Average rank error":
                            gr.average_rank_error = float(value)
                        elif key == "Average PQ size":
                            gr.average_pq_size = float(value)
                        elif key == "Max PQ size":
                            gr.max_pq_size = int(value)
                
                graph_results.append(gr)
                print(result_data)
                print(f"Average rank error: {gr.average_rank_error:.5f}")
                print(f"Average PQ size: {gr.average_pq_size:.0f}")
                print(f"Max PQ size: {gr.max_pq_size}")
                print("-" * 20)

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
    # Build list of known graph names (without extension) from both graph lists
    known_graphs = [name.rsplit('.', 1)[0] for name, _, _ in RANDOM_GRAPHS]
    known_graphs += [Path(p).stem for p in OTHER_GRAPHS]
    
    by_graph = {}
    by_config = {}
    
    for gr in graph_results:
        # Extract graph base name and config from name
        # Format: graphname_algorithmname_configname
        # Match against known graph names for efficient parsing
        graph_base = None
        algo_config = None
        
        for known_graph in known_graphs:
            if gr.name.startswith(known_graph + '_'):
                graph_base = known_graph
                algo_config = gr.name[len(known_graph) + 1:]  # Everything after "graphname_"
                break
        
        if not graph_base:
            raise RuntimeError(f"Result name '{gr.name}' does not match any known graph from GRAPHS list")
        
        if graph_base not in by_graph:
            by_graph[graph_base] = {}
        by_graph[graph_base][algo_config] = gr
        
        if algo_config not in by_config:
            by_config[algo_config] = {}
        by_config[algo_config][graph_base] = gr
    
    # Sets used to route each result to the right cross-graph section
    random_graph_names = {name.rsplit('.', 1)[0] for name, _, _ in RANDOM_GRAPHS}
    other_graph_names  = {Path(p).stem for p in OTHER_GRAPHS}

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

    # Cross-graph comparison — Random graphs
    print("\n" + "=" * 60)
    print("CROSS-GRAPH COMPARISON (Random Graphs)")
    print("=" * 60)
    _print_cross_graph_section(random_graph_names)

    # Cross-graph comparison — Other graphs
    print("\n" + "=" * 60)
    print("CROSS-GRAPH COMPARISON (Other Graphs)")
    print("=" * 60)
    _print_cross_graph_section(other_graph_names)
    
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

def benchmark_gnm():
    check_build_graphs()
    results = run_benchmarks()
    analyze_results(results)
    print("done :(")



if __name__=="__main__":
    benchmark_gnm()