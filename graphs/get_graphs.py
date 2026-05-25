"""Download and generate the graphs used for the SSSP experiments."""
import shutil
import subprocess
import sys
from pathlib import Path

EDGELIST_CONVERTER_SCRIPT       = Path("edge_list_coordinate_converter.py")
RANDOM_WEIGHT_SCRIPT            = Path("random_weight_distributor.py")

ROAD_GRAPHS_PATH                = Path("road")
SOCIAL_GRAPHS_PATH              = Path("social")
RANDOM_GRAPHS_PATH              = Path("random")
RANDOM_HYPERBOLIC_GRAPHS_PATH   = Path("random_hyperbolic")
KAGEN_BINARY                    = Path("KaGen/build/app/KaGen")


def download_road_graphs() -> None:
    """Download road graphs using curl and decompress with gunzip.

    Assumes the format used in https://www.diag.uniroma1.it/challenge9/download.shtml.
    """
    curl_links = (
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.USA.gr.gz",
        "https://www.diag.uniroma1.it/challenge9/data/USA-road-t/USA-road-t.CTR.gr.gz",
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
    """Generate random hyperbolic graphs using KaGen binary.

    Produces a weighted DIMACS graph via the edgelist converter script.
    Configs entries: (name, N (log2 of nodes), avg_degree, seed)
    """
    configs = (
        ("rhg_18_s1", 18, 16.0, 1),
        ("rhg_18_s2", 18, 16.0, 2),
        ("rhg_18_s3", 18, 16.0, 3),
        ("rhg_18_s4", 18, 16.0, 4),
        ("rhg_18_s5", 18, 16.0, 5),
        ("rhg_20_s1", 20, 16.0, 1),
        ("rhg_20_s2", 20, 16.0, 2),
        ("rhg_20_s3", 20, 16.0, 3),
        ("rhg_20_s4", 20, 16.0, 4),
        ("rhg_20_s5", 20, 16.0, 5),
        ("rhg_22_s1", 22, 16.0, 1),
        ("rhg_22_s2", 22, 16.0, 2),
        ("rhg_22_s3", 22, 16.0, 3),
        ("rhg_22_s4", 22, 16.0, 4),
        ("rhg_22_s5", 22, 16.0, 5),
        ("rhg_24_s1", 24, 16.0, 1),
        ("rhg_24_s2", 24, 16.0, 2),
        ("rhg_24_s3", 24, 16.0, 3),
        ("rhg_24_s4", 24, 16.0, 4),
        ("rhg_24_s5", 24, 16.0, 5),
        ("rhg_24_deg8_s1", 24, 8.0, 1),
    )

    if not EDGELIST_CONVERTER_SCRIPT.exists():
        msg = "The edgelist converter is missing..."
        raise RuntimeError(msg)

    RANDOM_HYPERBOLIC_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, n_log2, avg_degree, seed in configs:
        base     = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}"
        edgelist = base.with_suffix(".edgelist")
        xyz      = base.with_suffix(".xyz")
        out      = base.with_suffix(".gr")

        if out.exists():
            continue

        if not (edgelist.exists() and xyz.exists()):
            print(f"Generating {name}")
            subprocess.run(
                [str(KAGEN_BINARY), "rhg",
                 "-N", str(n_log2), "-g", "2.3", "-d", str(avg_degree),
                 "-s", str(seed), "-f", "edgelist", "-f", "coordinates",
                 "-o", str(base)],
                check=True,
            )
        else:
            print(f"Intermediate files exist for {name}, skipping KaGen")

        subprocess.run(
            [sys.executable, str(EDGELIST_CONVERTER_SCRIPT),
             str(edgelist), str(xyz), str(out)],
            check=True,
        )
        edgelist.unlink(missing_ok=True)
        xyz.unlink(missing_ok=True)


def generate_random_graphs() -> None:
    """Generate random graphs using KaGen binary.

    Produces a weighted DIMACS graph via random weight script.    
    Configs entries:
        (name, grid_x_log2, grid_y_log2, min_weight, max_weight, num_seeds)
    """
    configs = (
        # ("grid_graph_X5_Y5", 5, 5, 1, 100000, 5),
        ("grid_graph_X10_Y10", 10, 10, 1, 100000, 5),
        ("grid_graph_X13_Y13", 13, 13, 1, 100000, 3),
    )

    if not EDGELIST_CONVERTER_SCRIPT.exists():
        msg = "The edgelist converter is missing..."
        raise RuntimeError(msg)

    RANDOM_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, x_log2, y_log2, min_weight, max_weight, num_seeds in configs:
        for seed in range(1, num_seeds + 1):
            gr  = RANDOM_GRAPHS_PATH / f"{name}_s{seed}.gr"
            edgelist = RANDOM_GRAPHS_PATH / f"{name}.edgelist"

            if gr.exists():
                continue

            if not (edgelist.exists()):
                print(f"Generating {name}")
                subprocess.run(
                    [str(KAGEN_BINARY), "grid2d",
                     "-X", str(x_log2), "-Y", str(y_log2), "-p", "1.0",
                     "-f", "edgelist", "-o", str(edgelist)],
                    check=True,
                )
            else:
                print(f"Intermediate files exist for {name}, skipping KaGen")

            subprocess.run(
                [sys.executable, str(RANDOM_WEIGHT_SCRIPT),
                str(edgelist), str(gr), str(min_weight), 
                str(max_weight), str(seed)],
                check=True,
            )
        edgelist.unlink(missing_ok=True)


def main() -> None:
    """Run all graph acquisition and generation steps."""
    download_road_graphs()
    generate_random_hyperbolic_graphs()
    generate_random_graphs()


if __name__ == "__main__":
    main()