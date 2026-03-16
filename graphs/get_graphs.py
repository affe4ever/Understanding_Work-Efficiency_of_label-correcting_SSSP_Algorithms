"""Download and generate the graphs used for the SSSP experiments."""
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


def check_kagen() -> None:
    """Build KaGen if the binary is not present."""
    if not KAGEN_PATH.exists():
        if not KAGEN_BUILD_SCRIPT.exists():
            msg = (
                "KaGen build script is not present, try\n"
                " submodule update --init --recursive"
            )
            raise RuntimeError(msg)
        subprocess.run(
            ["bash", str(KAGEN_BUILD_SCRIPT)],
            cwd=KAGEN_BUILD_SCRIPT.parent,
            check=True,
        )


def download_road_graphs() -> None:
    """Download road graphs using curl and decompress with gunzip.

    Assumes the format used in https://www.diag.uniroma1.it/challenge9/download.shtml.
    """
    curl_links = (
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.USA.gr.gz",
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.NY.gr.gz",
    )

    if shutil.which("curl") is None:
        msg = "curl is not installed or not on PATH"
        raise RuntimeError(msg)

    ROAD_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for link in curl_links:
        filename = link.rsplit("/", 1)[-1]
        output_path = ROAD_GRAPHS_PATH / filename
        if not output_path.with_suffix("").exists():
            print(f"Downloading {filename}")
            subprocess.run(["curl", "-L", "-o", str(output_path), link], check=True)
            subprocess.run(["gunzip", "-f", str(output_path)], check=True)


def generate_random_hyperbolic_graphs() -> None:
    """Generate random hyperbolic graphs using KaGen.

    Produces a weighted DIMACS graph via the edgelist converter script.
    """
    kagen_cmds = (
        ("the_rhg", "rhg -f edgelist -f coordinates --gamma 2.3 --avg-deg 16 -N 20"),
    )

    if not EDGELIST_CONVERTER_SCRIPT.exists():
        msg = "The edgelist converter is missing..."
        raise RuntimeError(msg)

    RANDOM_HYPERBOLIC_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, args in kagen_cmds:

        edgelist = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.edgelist"
        xyz      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.xyz"
        out      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.gr"

        if out.exists():
            continue


        print(f"Generating {name}")
        subprocess.run(
            f"{KAGEN_PATH} {args} -o {RANDOM_HYPERBOLIC_GRAPHS_PATH}/{name}",
            shell=True, check=True, capture_output=True,
        )
        subprocess.run(
            [sys.executable, str(EDGELIST_CONVERTER_SCRIPT),
             str(edgelist), str(xyz), str(out)],
            check=True,
        )
        edgelist.unlink(missing_ok=True)
        xyz.unlink(missing_ok=True)


def generate_random_graphs() -> None:
    """Generate random graphs using KaGen and assign random edge weights.

    Weights are distributed using the random weight script.

    CMDS needs:
        - a name for the graph
        - The KaGen command
        - Min Weight
        - Max Weight
        - Seed
    """
    cmds = (
        ("grid_graph_30_1", "grid2d -X 10 -Y 10 -p 30 -s 1", "1000", "10000", "1"),
        ("grid_graph_30_2", "grid2d -X 10 -Y 10 -p 30 -s 2", "1000", "10000", "1"),
        ("grid_graph_30_3", "grid2d -X 10 -Y 10 -p 30 -s 3", "1000", "10000", "1"),
        ("grid_graph_40_1", "grid2d -X 10 -Y 10 -p 40 -s 1", "1000", "10000", "1"),
        ("grid_graph_40_2", "grid2d -X 10 -Y 10 -p 40 -s 2", "1000", "10000", "1"),
        ("grid_graph_40_3", "grid2d -X 10 -Y 10 -p 40 -s 3", "1000", "10000", "1"),
        ("grid_graph_50_1", "grid2d -X 10 -Y 10 -p 50 -s 1", "1000", "10000", "1"),
        ("grid_graph_50_2", "grid2d -X 10 -Y 10 -p 50 -s 2", "1000", "10000", "1"),
        ("grid_graph_50_3", "grid2d -X 10 -Y 10 -p 50 -s 3", "1000", "10000", "1"),
    )

    if not RANDOM_WEIGHT_SCRIPT.exists():
        msg = "The random weight distributor is missing..."
        raise RuntimeError(msg)

    RANDOM_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, args, min_weight, max_weight, seed in cmds:
        gr = RANDOM_GRAPHS_PATH / f"{name}.gr"

        if gr.exists():
            continue


        out = RANDOM_GRAPHS_PATH / f"{name}.edgelist"
        print(f"Generating {name}")
        subprocess.run(
            f"{KAGEN_PATH} {args} -f edgelist -o {out}",
            shell=True, check=True, capture_output=True,
        )
        subprocess.run(
            [sys.executable, str(RANDOM_WEIGHT_SCRIPT), str(out),
             str(gr), str(min_weight), str(max_weight), str(seed)],
            check=True, capture_output=True,
        )
        out.unlink(missing_ok=True)


def main() -> None:
    """Run all graph acquisition and generation steps."""
    check_kagen()
    download_road_graphs()
    generate_random_hyperbolic_graphs()
    generate_random_graphs()



if __name__ == "__main__":
    main()
