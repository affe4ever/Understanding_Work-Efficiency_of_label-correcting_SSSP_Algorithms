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

DRPQ_PATH = Path("multiqueue_experiments/build/benchmarks/dijkstra_seq_error")
OUT_PATH = Path("benchmarks.out")


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
        args = [f"{BASE_GRAPH_PATH}", f"{GRAPH_FOLDER}/{GRAPH1_NAME}", "1", "10"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if not GRAPH2_PATH.exists():
        print("g2 does not exist")
        args = [f"{BASE_GRAPH_PATH}", f"{GRAPH_FOLDER}/{GRAPH2_NAME}", "1", "100"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if not GRAPH3_PATH.exists():
        print("g3 does not exist")
        args = [f"{BASE_GRAPH_PATH}", f"{GRAPH_FOLDER}/{GRAPH3_NAME}", "1", "1000"]
        process = subprocess.Popen([sys.executable, str(WEIGHT_SCRIPT_PATH)] + args)
        processes.append(process)
    
    if processes:
        print("Creating graphs:")
        for process in processes:
            process.wait()


def run_benchmarks():
    if not DRPQ_PATH.exists():
        raise RuntimeError("DrPQ not found, build multiqueue_experiments then continue")
    
    graph_paths = [GRAPH1_PATH, GRAPH2_PATH, GRAPH3_PATH]
    args_list = [
        ["--mean", "0", "--stddev", "0"],
        ["--mean", "1", "--stddev", "0"]
    ]
    
    print("Running benchmarks...")
    all_outputs = {}
    
    for graph in graph_paths:
        print(f"on {graph}")
        graph_path = Path(graph)
        processes = []
        
        for args in args_list:
            processes.append(
                subprocess.Popen([str(DRPQ_PATH)] + args + [str(graph_path)], 
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            )
        
        outputs = []
        for process in processes:
            _stdout, stderr = process.communicate()
            outputs.append(stderr)
        
        all_outputs[graph] = list(zip(args_list, outputs))
    
    print("\n= Results =")
    for graph, results in all_outputs.items():
        print(f"Graph: {graph}")
        print("=" * 40)
        for args, stderr in results:
            if "= Results =" in stderr:
                print(f"(mean={args[1]})")
                result_data = stderr.split("= Results =")[1].strip()
                print(result_data)
                print("-" * 20)


def benchmark_gnm():
    check_build_graphs()
    run_benchmarks()
    print("done :(")



if __name__=="__main__":
    benchmark_gnm()