#Python script to run benchmrks :D
# intention is to have: 
# --build flag that runs cmake on the underlying structure with the correct flag
# -v, --verbose to print what commands are actually being run
# -r, --runs flag to decide how many times each algorithm is run
# -j, --num_threads set amount of threads both for the build and for the run
# -g, --graph selects what graph the alg should be run on
# -o, --output_dir defines output directory, output files will have the form, <name of alg>_<name of graph>_run_<N>

# additional flag functionality may include utilization of the analyze_quality

# However may also just add some fun functions just cause
from pathlib import Path
import subprocess   
import sys


GRAPH1_NAME = "gnm_1-10.gr"
GRAPH2_NAME = "gnm_1-100.gr"
GRAPH3_NAME = "gnm_1-1000.gr"
GRAPH_FOLDER = "graphs"
BASE_GRAPH_NAME = "base_gnm_edgelist"
RANDOM_WEIGHT_SCRIPT = "random_weight_distributor.py"
KAGEN_PATH = Path("KaGen/build/app/KaGen")
BASE_GRAPH_PATH = Path(f"{GRAPH_FOLDER}/{BASE_GRAPH_NAME}")
WEIGHT_SCRIPT_PATH = Path(f"{GRAPH_FOLDER}/{RANDOM_WEIGHT_SCRIPT}")
GRAPH1_PATH = Path(f"{GRAPH_FOLDER}/{GRAPH1_NAME}")
GRAPH2_PATH = Path(f"{GRAPH_FOLDER}/{GRAPH2_NAME}")
GRAPH3_PATH = Path(f"{GRAPH_FOLDER}/{GRAPH3_NAME}")

STD_DIJKSTRA_PATH = Path("multiqueue_experiments/build/benchmarks/dijkstra_seq")
DRPQ_PATH = Path("multiqueue_experiments/build/benchmarks/dijkstra_seq_error")
OUT_PATH = Path("out/")

class GraphResults:
    def __init__(self):
        self.name: str = ""
        self.time: float = 0.0
        self.processed_nodes: int = 0
        self.ignored_nodes: int = 0
        self.edge_relaxations: int = 0
        self.discarded_edges: int = 0
        self.average_pq_size: float = 0.0
        self.max_pq_size: int = 0



def check_build_graphs():
    if not BASE_GRAPH_PATH.exists():
        if not KAGEN_PATH.exists():
            raise RuntimeError("Kagen does not exist, build KaGen then continue")
        else:
            print("Base graph does not exist, building it")
            args = ["gnm-directed", "-m", "15403114", "-N", "20", "-f", "edgelist", "-o", str(BASE_GRAPH_PATH)]
            _result = subprocess.run([
                str(KAGEN_PATH)] + args,
                capture_output=True, 
                text=True
                )
    
    processes = []
    if not GRAPH1_PATH.exists():
        print("g1 does not exist")
        args = [str(BASE_GRAPH_PATH), str(GRAPH1_PATH), "1", "10"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if not GRAPH2_PATH.exists():
        print("g2 does not exist")
        args = [str(BASE_GRAPH_PATH), str(GRAPH2_PATH), "1", "100"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if not GRAPH3_PATH.exists():
        print("g3 does not exist")
        args = [str(BASE_GRAPH_PATH), str(GRAPH3_PATH), "1", "1000"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if processes:
        print("Creating graphs:")
        for process in processes:
            process.wait()


def run_benchmarks():
    if not STD_DIJKSTRA_PATH.exists():
        raise RuntimeError("Standard Dijkstra not found, build multiqueue_experiments then continue")
    if not DRPQ_PATH.exists():
        raise RuntimeError("DrPQ not found, build multiqueue_experiments then continue")
    
    graph_paths = [
        GRAPH1_PATH, 
        GRAPH2_PATH, 
        GRAPH3_PATH,
        ]
    args_list = [
        ["--mean", "0", "--stddev", "0"],
        ["--mean", "1", "--stddev", "0"],
        ]
    
    print("Running benchmarks...")
    all_outputs = {}
    
    for graph in graph_paths:
        print(f"on {graph}")
        processes = []
        configs = []
        
        # Run baseline standard dijkstra
        processes.append(
            subprocess.Popen([str(STD_DIJKSTRA_PATH), str(graph)], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        )
        configs.append(["baseline"])
        
        # Run with different relaxation parameters
        for args in args_list:
            processes.append(
                subprocess.Popen([str(DRPQ_PATH)] + args + [str(graph)], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            )
            configs.append(args)
        
        outputs = []
        for process in processes:
            _stdout, stderr = process.communicate()
            outputs.append(stderr)
        
        all_outputs[graph] = list(zip(configs, outputs))
    
    graph_results = []

    print("\n= Results =")
    for graph, results in all_outputs.items():
        print(f"Graph: {graph}")
        print("=" * 40)
        for config, stderr in results:
            if "= Results =" in stderr:
                if config[0] == "baseline":
                    print("(baseline)")
                    config_name = "baseline"
                else:
                    print(f"(mean={config[1]}, stddev={config[3]})")
                    config_name = f"mean{config[1]}_stddev{config[3]}"
                
                result_data = stderr.split("= Results =")[1].strip()
                
                gr = GraphResults()
                gr.name = f"{graph.stem}_{config_name}"
                
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
                        elif key == "Average PQ size":
                            gr.average_pq_size = float(value)
                        elif key == "Max PQ size":
                            gr.max_pq_size = int(value)
                
                graph_results.append(gr)
                print(result_data)
                print("-" * 20)

    return graph_results


def analyze_results(graph_results):
    """Analyze benchmark results with cross-graph and within-graph comparisons."""
    if not graph_results:
        print("No results to analyze")
        return
    
    # Group results by graph and by config
    by_graph = {}
    by_config = {}
    
    for gr in graph_results:
        # Extract graph base name and config from name
        parts = gr.name.split('_')
        if 'baseline' in gr.name:
            graph_base = '_'.join(parts[:-1])
            config = 'baseline'
        else:
            # Format: gnm_1-10_mean0_stddev0
            graph_base = '_'.join(parts[:-2])
            config = '_'.join(parts[-2:])
        
        if graph_base not in by_graph:
            by_graph[graph_base] = {}
        by_graph[graph_base][config] = gr
        
        if config not in by_config:
            by_config[config] = {}
        by_config[config][graph_base] = gr
    
    # Cross-graph comparison (same config, different graphs)
    print("\n" + "=" * 60)
    print("CROSS-GRAPH COMPARISON (baseline as reference)")
    print("=" * 60)
    
    for config in sorted(by_config.keys()):
        graphs_in_config = by_config[config]
        if len(graphs_in_config) < 2:
            continue
        
        print(f"\n--- Configuration: {config} ---")
        
        # Find baseline graph (first one alphabetically)
        baseline_graph = sorted(graphs_in_config.keys())[0]
        baseline = graphs_in_config[baseline_graph]
        
        print(f"{'Graph':<20} {'Time':<8} {'Proc.Nodes':<12} {'Ign.Nodes':<12} {'Avg.PQ':<10} {'Max.PQ':<10}")
        print("-" * 80)
        print(f"{baseline_graph:<20} {'1.000':<8} {'1.000':<12} {'1.000':<12} {'1.000':<10} {'1.000':<10}")
        
        for graph_name in sorted(graphs_in_config.keys()):
            if graph_name == baseline_graph:
                continue
            gr = graphs_in_config[graph_name]
            
            time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
            proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
            ign_ratio = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0
            avg_pq_ratio = gr.average_pq_size / baseline.average_pq_size if baseline.average_pq_size > 0 else 0
            max_pq_ratio = gr.max_pq_size / baseline.max_pq_size if baseline.max_pq_size > 0 else 0
            
            print(f"{graph_name:<20} {time_ratio:<8.3f} {proc_ratio:<12.3f} {ign_ratio:<12.3f} {avg_pq_ratio:<10.3f} {max_pq_ratio:<10.3f}")
    
    # Within-graph comparison (same graph, different configs)
    print("\n" + "=" * 60)
    print("WITHIN-GRAPH COMPARISON (baseline as reference)")
    print("=" * 60)
    
    for graph_name in sorted(by_graph.keys()):
        configs_in_graph = by_graph[graph_name]
        if len(configs_in_graph) < 2:
            continue
        
        # Use baseline as reference if available, otherwise first config
        baseline = configs_in_graph.get('baseline')
        if not baseline:
            baseline_config = sorted(configs_in_graph.keys())[0]
            baseline = configs_in_graph[baseline_config]
            reference_name = baseline_config
        else:
            reference_name = 'baseline'
        
        print(f"\n--- Graph: {graph_name} (reference: {reference_name}) ---")
        print(f"{'Config':<20} {'Time':<8} {'Proc.Nodes':<12} {'Ign.Nodes':<12} {'Avg.PQ':<10} {'Max.PQ':<10}")
        print("-" * 80)
        
        for config in sorted(configs_in_graph.keys()):
            gr = configs_in_graph[config]
            
            time_ratio = gr.time / baseline.time if baseline.time > 0 else 0
            proc_ratio = gr.processed_nodes / baseline.processed_nodes if baseline.processed_nodes > 0 else 0
            ign_ratio = gr.ignored_nodes / baseline.ignored_nodes if baseline.ignored_nodes > 0 else 0
            avg_pq_ratio = gr.average_pq_size / baseline.average_pq_size if baseline.average_pq_size > 0 else 0
            max_pq_ratio = gr.max_pq_size / baseline.max_pq_size if baseline.max_pq_size > 0 else 0
            
            print(f"{config:<20} {time_ratio:<8.3f} {proc_ratio:<12.3f} {ign_ratio:<12.3f} {avg_pq_ratio:<10.3f} {max_pq_ratio:<10.3f}")
    
    print("\n" + "=" * 60)
def benchmark_gnm():
    check_build_graphs()
    results = run_benchmarks()
    analyze_results(results)
    print("done :(")



if __name__=="__main__":
    benchmark_gnm()