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
import json
import subprocess
import argparse
import re
import sys
from collections import defaultdict

# ===== Configuration =====

ANALYZE_QUALITY_PATH = Path("multiqueue_experiments/build/tools/analyze_quality")
SUMMARY_GEN_PATH = Path("summary_gen.py")


OUT_PATH = Path("outs")
META_OUTPUT_DIR = OUT_PATH / Path("meta")
HISTOGRAM_OUTPUT_DIR = OUT_PATH
SUMMARIES_OUTPUT_DIR = OUT_PATH / Path("summaries")
WARNINGS_FILE_PATH = OUT_PATH / "warnings"


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
        # RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s4.gr",
        # RANDOM_GRAPHS_PATH / "grid_graph_X13_Y13_s5.gr",
        # # RANDOM_GRAPHS_PATH / "example.gr",
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
        # # RANDOM_HYPERBOLIC_GRAPHS_PATH / "the_rhg.gr",
        # RANDOM_HYPERBOLIC_GRAPHS_PATH / "rhg_18.gr",
    ],
}

# ===== Summary Generation Configuration =====
CLEANUP_CSV_AFTER_ANALYZER = True

# ===== Chunking Configuration =====
# Default chunk size: number of graphs to process together before cleanup
CHUNK_SIZE = 5

# Override chunk size for specific categories
# If a category is not listed, it uses CHUNK_SIZE
CHUNK_PER_CATEGORY = {
    # "Random Hyperbolic Graphs": 21,
    "Road Networks": 3,
}

# Per-graph-base algorithm limits (takes precedence over global)
# Key: prefix to match against graph stem (e.g., "rhg" matches "rhg_18_s1", "rhg_20_s1", etc.)
#      Uses longest matching prefix for specificity (e.g., "rhg_24" matches before "rhg")
# Value: maximum number of algorithms to run on this graph base at a time
# If a graph is not listed, all algorithms run sequentially (one at a time)
ALG_PER_BASE = {
    "grid_graph_X13": 2,
    "rhg_24" : 2,
}

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
            ("mean1_p001", ["-j", "1", "--mean", "1", "--percentile", "0.01"]),
            ("mean10_p001", ["-j", "1", "--mean", "10", "--percentile", "0.01"]),
            ("mean100_p001", ["-j", "1", "--mean", "100", "--percentile", "0.01"]),
            ("mean1000_p001", ["-j", "1", "--mean", "1000", "--percentile", "0.01"]),
            ("mean10000_p001", ["-j", "1", "--mean", "10000", "--percentile", "0.01"]),
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
            ("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_klsm1024",
        name="klsm1024",
        flag_configs=[
            ("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_klsm4096",
        name="klsm4096",
        flag_configs=[
            ("t8", ["-j", "8"]),
            ("t16", ["-j", "16"]),
            ("t32", ["-j", "32"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_capq",
        name="capq",
        flag_configs=[
            ("t8", ["-j", "8"]),
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
        self.min_degree: int = 0
        self.avg_degree: float = 0.0
        self.max_degree: int = 0





def _parse_kv(text: str) -> dict:
    """Parse 'Key: value' lines from text into a dict."""
    result = {}
    for line in text.split("\n"):
        if ":" in line:
            k, v = (s.strip() for s in line.split(":", 1))
            result[k] = v
    return result


def _extract_metrics(benchmark_output: str, quality_output: str) -> dict:
    """Extract and parse metrics from benchmark and quality outputs into a clean dict with proper types."""
    metrics = {}
    
    # Extract benchmark metrics from "= Results =" section
    if "= Results =" in benchmark_output:
        result_section = benchmark_output.split("= Results =")[1]
        bkv = _parse_kv(result_section)
        
        # Map and convert benchmark metrics
        metric_map = {
            "Time (s)": ("time_s", float),
            "Processed nodes": ("processed_nodes", int),
            "Ignored nodes": ("ignored_nodes", int),
            "Edge relaxations": ("edge_relaxations", int),
            "Discarded edges": ("discarded_edges", int),
            "Min degree": ("min_degree", int),
            "Avg degree": ("avg_degree", float),
            "Max degree": ("max_degree", int),
            "Furthest node": ("furthest_node", int),
            "Longest distance": ("longest_distance", int),
        }
        
        for key, (metric_name, type_fn) in metric_map.items():
            if key in bkv:
                try:
                    metrics[metric_name] = type_fn(bkv[key])
                except (ValueError, TypeError):
                    metrics[metric_name] = bkv[key]
    
    # Extract quality metrics
    if quality_output:
        qkv = _parse_kv(quality_output)
        
        metric_map = {
            "Average rank error": ("avg_rank_error", float),
            "Largest rank error": ("largest_rank_error", int),
            "Smallest rank error": ("smallest_rank_error", int),
            "Average delay": ("avg_delay", float),
            "Largest delay": ("largest_delay", int),
            "Smallest delay": ("smallest_delay", int),
            "Average PQ size": ("avg_pq_size", float),
            "Max PQ size": ("max_pq_size", int),
            "Invalid pops": ("invalid_pops", int),
        }
        
        for key, (metric_name, type_fn) in metric_map.items():
            if key in qkv:
                try:
                    metrics[metric_name] = type_fn(qkv[key])
                except (ValueError, TypeError):
                    metrics[metric_name] = qkv[key]
    
    return metrics


def check_graphs():
    """Check if all graphs exist. Return list of missing graphs."""
    missing = []
    for category, paths in GRAPH_CATEGORIES.items():
        for path in paths:
            if not path.exists():
                missing.append((category, str(path)))
    return missing


def _get_alg_limit_for_graph(graph_path: Path) -> int:
    """
    Determine algorithm limit for a graph based on longest prefix match.
    Returns the max number of algorithms to run on this graph base.
    
    Uses longest matching prefix for specificity:
    Example:
        ALG_PER_BASE = {"rhg": 10, "rhg_24": 2}
        - "rhg_18_s1" matches "rhg" → limit 10
        - "rhg_24_s1" matches "rhg_24" (longest) → limit 2
    
    If no match found, returns None (will run all algorithms).
    """
    stem = graph_path.stem  # e.g., "rhg_18_s1", "grid_graph_X13_Y13_s1"
    
    # Find longest matching prefix in ALG_PER_BASE
    longest_match_limit = None
    longest_match_key = None
    
    for key in ALG_PER_BASE:
        if stem.startswith(key):
            if longest_match_key is None or len(key) > len(longest_match_key):
                longest_match_limit = ALG_PER_BASE[key]
                longest_match_key = key
    
    return longest_match_limit


def flatten_graphs_into_chunks() -> list:
    """
    Flatten graphs from GRAPH_CATEGORIES into a single flat list.
    Each graph will be processed individually with per-graph algorithm batching.
    
    Returns:
        List of all graph paths (flat list, no categories)
    """
    all_graphs = []
    
    for category, paths in GRAPH_CATEGORIES.items():
        if not paths:
            continue
        
        for path in paths:
            if path.exists():
                all_graphs.append(path)
    
    return sorted(all_graphs)


def _split_algorithms_into_chunks(available_algs: list, batch_size: int) -> list:
    """
    Split algorithms into chunks of batch_size for processing.
    
    Args:
        available_algs: List of AlgorithmConfig objects
        batch_size: Maximum number of algorithms per chunk
    
    Returns:
        List of algorithm chunks, where each chunk is a list of AlgorithmConfig objects
    """
    chunks = []
    for i in range(0, len(available_algs), batch_size):
        chunks.append(available_algs[i:i+batch_size])
    return chunks


def cleanup_chunk_files(graph_stems: list, available_algs: list, file_types: list = None):
    """
    Delete specified file types (.log, .csv, etc) for the given graph stems.
    
    Args:
        graph_stems: List of graph file stems (e.g., ["grid_graph_X10_Y10_s1", ...])
        available_algs: List of available AlgorithmConfig objects
        file_types: List of extensions to delete, e.g., ["log", "csv"]. If None, deletes both.
    """
    if file_types is None:
        file_types = ["log", "csv"]
    
    for stem in graph_stems:
        for alg in available_algs:
            for config_name, _ in alg.flag_configs:
                for ftype in file_types:
                    fpath = OUT_PATH / f"{stem}_{alg.name}_{config_name}.{ftype}"
                    if fpath.exists():
                        fpath.unlink()


def run_benchmarks(cached_only=False):
    """
    Run all configured algorithms on all graphs with per-graph algorithm batching.
    
    For each graph:
    1. Determine batch size from ALG_PER_BASE
    2. Split algorithms into chunks of that batch size
    3. For each algorithm batch:
       - Run benchmark and analysis for all algorithm configs
       - Delete .log files
       - Run summary_gen
       - Delete .csv files
    
    Args:
        cached_only: If True, skip benchmarks and only load cached results
    
    Returns:
        Tuple of (graph_results, algo_failures, cache_failures, mismatches)
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
    
    # Create output directories
    OUT_PATH.mkdir(exist_ok=True)
    META_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get all graphs (flat list)
    all_graphs = flatten_graphs_into_chunks()
    
    print(f"Processing {len(all_graphs)} graphs with per-graph algorithm batching")
    if not cached_only:
        print(f"Processing order: benchmark → analysis → log cleanup → summary_gen → csv cleanup\n")
    else:
        print("[CACHED-ONLY MODE] Loading cached results only\n")
    
    # Collect all meta_files and graph results for final parsing
    all_meta_files = {}
    graph_results = []
    mismatches = []
    
    # Process each graph
    for graph_idx, graph in enumerate(all_graphs):
        # Determine batch size for this graph
        alg_limit = _get_alg_limit_for_graph(graph)
        batch_size = alg_limit if alg_limit else len(available_algs)
        
        # Split algorithms into batches for this graph
        alg_chunks = _split_algorithms_into_chunks(available_algs, batch_size)
        
        print(f"Graph {graph_idx + 1}/{len(all_graphs)}: {graph.stem} (batch_size={batch_size}, {len(alg_chunks)} algorithm batches)")
        
        # Orphaned CSV recovery: check if any meta files show analysis complete but analyzer hasn't run
        for alg in available_algs:
            for config_name, _ in alg.flag_configs:
                meta_file = META_OUTPUT_DIR / f"{graph.stem}_{alg.name}_{config_name}.meta"
                csv_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.csv"
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                        benchmark_failed = meta.get("benchmark_failed", False)
                        quality_failed = meta.get("quality_failed", False)
                        analyzer_failed = meta.get("analyzer_failed", False)
                        
                        if not benchmark_failed and not quality_failed and analyzer_failed:
                            if not csv_file.exists():
                                # CSV missing, delete meta to force complete rerun
                                meta_file.unlink()
                    except (json.JSONDecodeError, KeyError):
                        pass
        
        # Process each algorithm batch
        for batch_idx, alg_chunk in enumerate(alg_chunks):
            batch_work_done = False
            batch_meta_files = {}
            
            # Run benchmarks and analysis for each algorithm in this batch on this graph
            for alg in alg_chunk:
                for config_name, flags in alg.flag_configs:
                    log_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.log"
                    meta_file = META_OUTPUT_DIR / f"{graph.stem}_{alg.name}_{config_name}.meta"
                    csv_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.csv"
                    err_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.err"
                    cmd = [str(alg.path)] + flags + ["-l", str(log_file), str(graph)]
                    
                    # Check cache
                    use_cache = False
                    recover = False
                    
                    if meta_file.exists():
                        try:
                            meta = json.loads(meta_file.read_text())
                            if meta.get("cmd") == cmd:
                                if meta.get("complete", False):
                                    use_cache = True
                        except (json.JSONDecodeError, KeyError):
                            pass
                    elif log_file.exists():
                        recover = True
                    
                    if use_cache:
                        # Already complete, just record meta
                        batch_meta_files[f"{alg.name}_{config_name}"] = meta_file
                        continue
                    
                    if cached_only:
                        continue
                    
                    batch_work_done = True
                    
                    # Recovery case: analyze existing orphaned log
                    if recover:
                        if not log_file.exists():
                            meta = {
                                "cmd": cmd,
                                "benchmark_failed": True,
                                "benchmark_output": "",
                                "quality_output": "",
                                "quality_failed": True,
                                "analyzer_failed": False,
                                "complete": False,
                                "metrics": {},
                            }
                            meta_file.write_text(json.dumps(meta, indent=2))
                            err_file.write_text("ERROR: Log file disappeared\n")
                            continue
                        
                        print(f"  Status: Running analysis on {graph.stem}_{alg.name}_{config_name}")
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
                            "cmd": cmd,
                            "benchmark_failed": quality_failed,
                            "quality_output": quality_output,
                            "quality_failed": quality_failed,
                            "analyzer_failed": False,
                            "complete": not quality_failed,
                            "metrics": _extract_metrics("", quality_output),
                        }
                        
                        if quality_failed:
                            err_file.write_text(quality_output)
                        
                        meta_file.write_text(json.dumps(meta, indent=2))
                        batch_meta_files[f"{alg.name}_{config_name}"] = meta_file
                        
                        # Delete log file immediately after successful analysis
                        if not quality_failed and log_file.exists():
                            log_file.unlink()
                        
                        continue
                    
                    # Regular path: run benchmark
                    print(f"  Status: Running benchmark on {graph.stem}_{alg.name}_{config_name}")
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    benchmark_failed = result.returncode != 0
                    benchmark_output = result.stderr
                    
                    meta = {
                        "cmd": cmd,
                        "benchmark_failed": benchmark_failed,
                        "benchmark_output": benchmark_output,
                        "quality_failed": False,
                        "analyzer_failed": False,
                        "complete": False,
                        "metrics": {},
                    }
                    
                    if benchmark_failed:
                        err_file.write_text(benchmark_output)
                        meta_file.write_text(json.dumps(meta, indent=2))
                        batch_meta_files[f"{alg.name}_{config_name}"] = meta_file
                        continue
                    
                    # Benchmark succeeded, run analyze_quality
                    print(f"  Status: Running analysis on {graph.stem}_{alg.name}_{config_name}")
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
                    
                    meta["benchmark_output"] = benchmark_output
                    meta["quality_output"] = quality_output
                    meta["metrics"] = _extract_metrics(benchmark_output, quality_output)
                    meta["complete"] = not quality_failed
                    
                    if quality_failed:
                        meta["quality_failed"] = True
                        err_file.write_text(quality_output)
                    else:
                        meta["complete"] = True
                    
                    meta_file.write_text(json.dumps(meta, indent=2))
                    batch_meta_files[f"{alg.name}_{config_name}"] = meta_file
                    
                    # Delete log file immediately after successful analysis
                    if not quality_failed and log_file.exists():
                        log_file.unlink()
            
            # Delete any remaining .log files
            for alg in alg_chunk:
                for config_name, _ in alg.flag_configs:
                    log_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.log"
                    if log_file.exists():
                        log_file.unlink()
            
            # Run summary_gen for this batch on this graph
            summary_failed = False
            if batch_work_done and SUMMARY_GEN_PATH.exists():
                HISTOGRAM_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                print(f"  Status: Running summary (batch {batch_idx + 1}/{len(alg_chunks)})")
                try:
                    result = subprocess.run(
                        [sys.executable, str(SUMMARY_GEN_PATH), "--data-dir", str(OUT_PATH), 
                         "--summaries-dir", str(SUMMARIES_OUTPUT_DIR), "--histogram-dir", str(HISTOGRAM_OUTPUT_DIR), 
                         "--meta-dir", str(META_OUTPUT_DIR)],
                        cwd=Path.cwd(),
                        timeout=3600,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    summary_failed = result.returncode != 0
                    if result.stderr:
                        print(f"  Summary generator err:\n{result.stderr}")
                    if summary_failed:
                        print(f"  Warning: summary_gen exited with code {result.returncode}")
                except subprocess.TimeoutExpired:
                    summary_failed = True
                    print(f"  Warning: summary_gen timed out on {graph.stem} batch {batch_idx}")
                except Exception as e:
                    summary_failed = True
                    print(f"  Warning: summary_gen failed on {graph.stem} batch {batch_idx}: {e}")
            
            # Update meta files with summary_gen status
            for alg in alg_chunk:
                for config_name, _ in alg.flag_configs:
                    meta_file = META_OUTPUT_DIR / f"{graph.stem}_{alg.name}_{config_name}.meta"
                    try:
                        meta = json.loads(meta_file.read_text())
                        meta["analyzer_failed"] = summary_failed
                        meta_file.write_text(json.dumps(meta, indent=2))
                    except (json.JSONDecodeError, FileNotFoundError):
                        pass
            
            # Delete all .csv files for this batch on this graph
            if CLEANUP_CSV_AFTER_ANALYZER:
                for alg in alg_chunk:
                    for config_name, _ in alg.flag_configs:
                        csv_file = OUT_PATH / f"{graph.stem}_{alg.name}_{config_name}.csv"
                        if csv_file.exists():
                            csv_file.unlink()
        
        # Record all meta files for this graph
        all_meta_files[graph] = batch_meta_files
    
    # Parse all results
    for graph in all_meta_files:
        for config_key, meta_file in all_meta_files[graph].items():
            algo_name, config_name = config_key.split("_", 1) if "_" in config_key else (config_key, "default")
            
            try:
                meta = json.loads(meta_file.read_text())
                is_complete = meta.get("complete", False)
                benchmark_output = meta.get("benchmark_output", "")
                quality_stderr = meta.get("quality_output", "")
            except (json.JSONDecodeError, FileNotFoundError):
                continue
            
            if not is_complete:
                continue
            
            gr = GraphResults()
            gr.name = f"{graph.stem}_{algo_name}_{config_name}"
            
            if "= Results =" in benchmark_output:
                result_data = benchmark_output.split("= Results =")[1].strip()
                bkv = _parse_kv(result_data)
                if "Time (s)" in bkv: gr.time = float(bkv["Time (s)"])
                if "Processed nodes" in bkv: gr.processed_nodes = int(bkv["Processed nodes"])
                if "Ignored nodes" in bkv: gr.ignored_nodes = int(bkv["Ignored nodes"])
                if "Edge relaxations" in bkv: gr.edge_relaxations = int(bkv["Edge relaxations"])
                if "Discarded edges" in bkv: gr.discarded_edges = int(bkv["Discarded edges"])
                if "Min degree" in bkv: gr.min_degree = int(bkv["Min degree"])
                if "Avg degree" in bkv: gr.avg_degree = float(bkv["Avg degree"])
                if "Max degree" in bkv: gr.max_degree = int(bkv["Max degree"])
            
            qkv = _parse_kv(quality_stderr)
            if "Average rank error" in qkv: gr.average_rank_error = float(qkv["Average rank error"])
            if "Average delay" in qkv: gr.average_delay = float(qkv["Average delay"])
            if "Average PQ size" in qkv: gr.average_pq_size = float(qkv["Average PQ size"])
            if "Max PQ size" in qkv: gr.max_pq_size = int(qkv["Max PQ size"])
            
            graph_results.append(gr)
            
            if gr.average_rank_error != gr.average_delay:
                mismatches.append((graph.stem, algo_name, config_name))
    
    print(f"\nProcessed {len(all_graphs)} graphs. Parsed {len(graph_results)} results.")
    
    return graph_results, algo_failures, cache_failures, mismatches





def analyze_results(graph_results, algo_failures=None, cache_failures=None, graph_failures=None, mismatches=None, warnings_file_path=None):
    """
    Analyze benchmark results and write warnings/failures to file.
    
    Args:
        graph_results: List of GraphResults objects
        algo_failures: List of missing algorithm messages
        cache_failures: List of incomplete cache messages
        graph_failures: List of missing graph messages
        mismatches: List of (graph, algo, config) tuples with rank error vs delay mismatches
        warnings_file_path: Optional Path to write warnings to. If None, no warnings file is written.
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
        if warnings_file_path:
            warnings_file_path.write_text("No results to analyze\n")
        return
    
    # Write warnings to file if warnings exist and file path provided
    if warnings_file_path and (algo_failures or cache_failures or graph_failures or mismatches):
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("WARNINGS")
        lines.append("=" * 60)
        
        if algo_failures:
            lines.append("\nAlgorithms not found:")
            for failure in algo_failures:
                lines.append(f"  {failure}")
        
        if cache_failures:
            if algo_failures:
                lines.append("")
            lines.append("Cache issues:")
            for failure in cache_failures:
                lines.append(f"  {failure}")
        
        if graph_failures:
            if algo_failures or cache_failures:
                lines.append("")
            lines.append("Graphs not found:")
            for failure in graph_failures:
                lines.append(f"  {failure}")
        
        if mismatches:
            if algo_failures or cache_failures or graph_failures:
                lines.append("")
            lines.append("Rank error vs delay mismatches:")
            for graph, algo, config in mismatches:
                lines.append(f"  {graph}_{algo}_{config}")
        
        lines.append("\n" + "=" * 60)
        warnings_file_path.write_text("\n".join(lines))



def main():
    parser = argparse.ArgumentParser(description="Benchmark pathfinding algorithms with chunking")
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
    
    analyze_results(results, algo_failures=algo_failures, cache_failures=cache_failures, graph_failures=graph_failures, mismatches=mismatches, warnings_file_path=WARNINGS_FILE_PATH)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Completed benchmarking with {len(results)} total results")
    print(f"Warnings file: {WARNINGS_FILE_PATH}")
    print(f"Meta files: {META_OUTPUT_DIR}")
    print(f"Summary output: {HISTOGRAM_OUTPUT_DIR}")
    print("done :)")


if __name__ == "__main__":
    main()

