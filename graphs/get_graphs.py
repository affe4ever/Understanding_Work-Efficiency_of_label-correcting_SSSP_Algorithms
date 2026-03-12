# A script used to download and generate the graphs used for our experiments
import shutil
import subprocess
import sys
from pathlib import Path

KAGEN_PATH                      = Path("KaGen/build/app/KaGen")
KAGEN_BUILD_SCRIPT              = Path("KaGen/compile.sh")
EDGELIST_CONVERTER_SCRIPT       = Path("edge_list_coordinate_converter.py")
RANDOM_WEIGHT_SCRIPT            = Path("random_weight_distributor.py")

ROAD_GRAPHS_PATH                = Path("road")
SOCIAL_GRAPHS_PATH              = Path("social")
RANDOM_GRAPHS_PATH              = Path("random")
RANDOM_HYPERBOLIC_GRAPHS_PATH   = Path("random_hyperbolic")


def check_kagen():
    if not KAGEN_PATH.exists():
        print("KaGen is not built, attemting to build")
        if not KAGEN_BUILD_SCRIPT.exists():
            raise RuntimeError("KaGen build script is not present, try\n submodule update --init --recursive")
        subprocess.run(["bash", str(KAGEN_BUILD_SCRIPT)], cwd=KAGEN_BUILD_SCRIPT.parent, check=True)


def download_road_graphs():
    """This is will download graphs using curl and then unzip them using gunzip
    The function assumes the form used in https://www.diag.uniroma1.it/challenge9/download.shtml
    """
    CURL_LINKS = (
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.USA.gr.gz",
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.NY.gr.gz",
    )

    if shutil.which("curl") is None:
        raise RuntimeError("curl is not installed or not on PATH")

    ROAD_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for link in CURL_LINKS:
        filename = link.rsplit("/", 1)[-1]
        output_path = ROAD_GRAPHS_PATH / filename
        if not output_path.with_suffix("").exists():
            print(f"Downloading: {filename}")
            subprocess.run(["curl", "-L", "-o", str(output_path), link], check=True)
            subprocess.run(["gunzip", "-f", str(output_path)], check=True)


def generate_random_hyperbolic_graphs():
    """Generate edgelist and coordinated for random hyperbolic graphs using KaGen
    then generate weighted graph in DIMACS format using script
    """
    KAGEN_CMDS = (
        ("the_rhg", "rhg -f edgelist -f coordinates --gamma 2.3 --avg-deg 16 -N 10"),
    )

    if not EDGELIST_CONVERTER_SCRIPT.exists():
        raise RuntimeError("The edgelist converter is missing...")

    RANDOM_HYPERBOLIC_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, args in KAGEN_CMDS:
        edgelist = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.edgelist"
        xyz      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.xyz"
        out      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.gr"

        if out.exists():
            continue

        print(f"Generating {name}")

        subprocess.run(f"{KAGEN_PATH} {args} -o {RANDOM_HYPERBOLIC_GRAPHS_PATH}/{name}", shell=True, check=True, capture_output=True)
        subprocess.run([sys.executable, str(EDGELIST_CONVERTER_SCRIPT), str(edgelist), str(xyz), str(out)], check=True)
        edgelist.unlink(missing_ok=True)
        xyz.unlink(missing_ok=True)


def generate_random_graphs():
    """Generate edgelist for random graphs using KaGen
    random weight are then distributed using script

    CMDS needs: 
        - a name for the graph
        - The KaGen command
        - Min Weight
        - Max Weight
        - Seed
    """
    CMDS = (
        ("grid_graph", "grid2d -X 10 -Y 10 -p 0.7", "1", "2", "42"),
    )

    if not RANDOM_WEIGHT_SCRIPT.exists():
        raise RuntimeError("The random weight distributor is missing...")

    RANDOM_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, args, min_weight, max_weight, seed in CMDS:
        gr = RANDOM_GRAPHS_PATH / f"{name}.gr"

        if gr.exists():
            continue

        print(f"Generating {name}")

        out = RANDOM_GRAPHS_PATH / f"{name}.out"

        subprocess.run(f"{KAGEN_PATH} {args} -o {out}", shell=True, check=True, capture_output=True)
        subprocess.run([sys.executable, str(RANDOM_WEIGHT_SCRIPT), str(out), str(gr), str(min_weight), str(max_weight), str(seed)], check=True, capture_output=True)
        out.unlink(missing_ok=True)


def main():
    check_kagen()
    download_road_graphs()
    generate_random_hyperbolic_graphs()
    generate_random_graphs()

    print("done :)")


if __name__ == "__main__":
    main()
