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

To add a new graph:
  1. Add a tuple to the GRAPHS list: (filename, min_weight, max_weight)
  2. The new graph will then be generated using KaGen
"""

from pathlib import Path
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
GRAPHS = [
    #("gnm_1-10.gr", 1, 10),
    ("gnm_1-100.gr", 1, 100),
    ("gnm_1-1000.gr", 1, 1000),
    #("gnm_1-10000.gr", 1, 10000),
]

# Tool paths
ANALYZE_QUALITY_PATH = Path("multiqueue_experiments/build/tools/analyze_quality")


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
        flag_configs=[("seq", ["-j", "1"])]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_dr_pq",
        name="drpq",
        flag_configs=[
            ("mean0", ["-j", "1", "--mean", "0", "--stddev", "0"]),
            ("mean1", ["-j", "1", "--mean", "1", "--stddev", "0"]),
        ]
    ),
    AlgorithmConfig(
        path="multiqueue_experiments/build/benchmarks/dijkstra_log_dr_pq_buffered",
        name="drpq_buffered",
        flag_configs=[
            ("mean0", ["-j", "1", "--mean", "0", "--stddev", "0"]),
            ("mean1", ["-j", "1", "--mean", "1", "--stddev", "0"]),
        ]
    ),
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


def check_build_graphs():
    """Ensure base graph and weighted variants exist."""
    if not BASE_GRAPH_PATH.exists():
        if not KAGEN_PATH.exists():
            raise RuntimeError("Kagen does not exist, build KaGen then continue")
        
        print("Base graph does not exist, building it")
        args = ["gnm-directed", "-m", "15403114", "-N", "20", "-f", "edgelist", "-o", str(BASE_GRAPH_PATH)]
        subprocess.run([str(KAGEN_PATH)] + args, capture_output=True, text=True, check=True)
    
    processes = []
    for graph_name, weight_min, weight_max in GRAPHS:
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


def run_benchmarks():
    """Run all configured algorithms on all graphs and analyze quality."""
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
    
    # Get graph paths
    graph_paths = [Path(GRAPH_FOLDER) / name for name, _, _ in GRAPHS]
    
    print("Running benchmarks...")
    print(f"Algorithms: {', '.join(a.name for a in ALGORITHMS)}")
    print(f"Graphs: {', '.join(g.stem for g in graph_paths)}")
    print()
    
    all_outputs = {}
    log_files = {}
    
    # Run benchmarks for each graph
    for graph in graph_paths:
        print(f"Graph: {graph.name}")
        processes = []
        configs = []
        log_paths = []
        
        # Run each algorithm with all its configurations
        for algo in ALGORITHMS:
            for config_name, flags in algo.flag_configs:
                log_file = OUT_PATH / f"{graph.stem}_{algo.name}_{config_name}.txt"
                
                # Build command: executable [flags] -l log_file graph
                cmd = [str(algo.path)] + flags + ["-l", str(log_file), str(graph)]
                
                print(f"  Starting {algo.name}/{config_name}...")
                processes.append(subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                ))
                configs.append((algo.name, config_name))
                log_paths.append(log_file)
        
        # Wait for all processes for this graph
        print(f"  Waiting for {len(processes)} processes to complete...")
        outputs = []
        for i, process in enumerate(processes):
            _stdout, stderr = process.communicate()
            outputs.append(stderr)
            print(f"  Process {i+1}/{len(processes)} completed")
        
        all_outputs[graph] = list(zip(configs, outputs))
        log_files[graph] = list(zip(configs, log_paths))
    
    # Run analyze_quality on all log files in parallel
    print("\nRunning analyze_quality on log files...")
    quality_processes = []
    quality_configs = []
    
    for graph in log_files:
        for config, log_path in log_files[graph]:
            if log_path.exists():
                print(f"  Starting analyze_quality for {log_path.name}")
                with open(log_path, 'r') as f:
                    log_content = f.read()
                
                proc = subprocess.Popen(
                    [str(ANALYZE_QUALITY_PATH)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                proc.stdin.write(log_content)
                proc.stdin.close()
                quality_processes.append(proc)
                quality_configs.append((graph, config))
            else:
                print(f"  Warning: {log_path} does not exist, skipping")
                quality_processes.append(None)
                quality_configs.append((graph, config))
    
    # Collect results
    print(f"Waiting for {sum(p is not None for p in quality_processes)} analyze_quality processes...")
    quality_results = {}
    for i, (graph, config) in enumerate(quality_configs):
        if graph not in quality_results:
            quality_results[graph] = []
        
        if quality_processes[i] is not None:
            _stdout, stderr = quality_processes[i].communicate()
            quality_results[graph].append((config, stderr))
            print(f"  Completed {i+1}/{len(quality_configs)}")
        else:
            quality_results[graph].append((config, ""))
    
    # Parse all results
    graph_results = []
    
    print("\n= Results =")
    for graph in all_outputs:
        print(f"Graph: {graph.name}")
        print("=" * 40)
        
        graph_configs = log_files[graph]
        graph_outputs = all_outputs[graph]
        graph_quality = quality_results[graph]
        
        for (config, log_path), (_, stderr), (_, quality_stderr) in zip(graph_configs, graph_outputs, graph_quality):
            if "= Results =" in stderr:
                algo_name, config_name = config
                print(f"({algo_name}/{config_name})")
                
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
                print(f"Average rank error: {gr.average_rank_error:.3f}")
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
    # Build list of known graph names (without .gr extension)
    known_graphs = [name.rsplit('.', 1)[0] for name, _, _ in GRAPHS]
    
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
    
    # Cross-graph comparison (same config, different graphs)
    print("\n" + "=" * 60)
    print("CROSS-GRAPH COMPARISON")
    print("=" * 60)
    
    for config in sorted(by_config.keys()):
        graphs_in_config = by_config[config]
        if len(graphs_in_config) < 2:
            continue
        
        print(f"\n--- Configuration: {config} ---")
        
        # Sort graph names once and reuse
        sorted_graphs = sorted(graphs_in_config.keys())
        baseline_graph = sorted_graphs[0]
        baseline = graphs_in_config[baseline_graph]
        
        print(f"{'Graph':<20} {'Time':<8} {'Proc.Nodes':<12} {'Ign.Nodes':<12} {'Avg.PQ':<12} {'Max.PQ':<12} {'Avg.Rank.Err':<12}")
        print("-" * 100)
        print(f"{baseline_graph:<20} {'1.000':<8} {'1.000':<12} {'1.000':<12} {baseline.average_pq_size:<12.0f} {baseline.max_pq_size:<12} {baseline.average_rank_error:<12.3f}")
        
        for graph_name in sorted_graphs:
            if graph_name == baseline_graph:
                continue
            gr = graphs_in_config[graph_name]
            
            time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
            proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
            ign_ratio = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0
            
            print(f"{graph_name:<20} {time_ratio:<8.3f} {proc_ratio:<12.3f} {ign_ratio:<12.3f} {gr.average_pq_size:<12.0f} {gr.max_pq_size:<12} {gr.average_rank_error:<12.3f}")
    
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
        print(f"{'Config':<25} {'Time':<8} {'Proc.Nodes':<12} {'Ign.Nodes':<12} {'Avg.PQ':<12} {'Max.PQ':<12} {'Avg.Rank.Err':<12}")
        print("-" * 105)
        
        for config in sorted_configs:
            gr = configs_in_graph[config]
            
            time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
            proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
            ign_ratio = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0
            
            print(f"{config:<25} {time_ratio:<8.3f} {proc_ratio:<12.3f} {ign_ratio:<12.3f} {gr.average_pq_size:<12.0f} {gr.max_pq_size:<12} {gr.average_rank_error:<12.3f}")
    
    print("\n" + "=" * 60)

def benchmark_gnm():
    check_build_graphs()
    results = run_benchmarks()
    analyze_results(results)
    print("done :(")



if __name__=="__main__":
    benchmark_gnm()