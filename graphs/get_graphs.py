"""Download and generate the graphs used for the SSSP experiments."""
import shutil
import subprocess
import sys
from pathlib import Path
import kagen

EDGELIST_CONVERTER_SCRIPT       = Path("edge_list_coordinate_converter.py")

ROAD_GRAPHS_PATH                = Path("road")
SOCIAL_GRAPHS_PATH              = Path("social")
RANDOM_GRAPHS_PATH              = Path("random")
RANDOM_HYPERBOLIC_GRAPHS_PATH   = Path("random_hyperbolic")


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
    """Generate random hyperbolic graphs using the KaGen Python library.

    Produces a weighted DIMACS graph via the edgelist converter script.
    """
    # Each entry: (name, N (log2 of nodes), avg_degree, seed)
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
        edgelist = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.edgelist"
        xyz      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.xyz"
        out      = RANDOM_HYPERBOLIC_GRAPHS_PATH / f"{name}.gr"

        if out.exists():
            continue

        if not (edgelist.exists() and xyz.exists()):
            print(f"Generating {name}")
            graph = kagen.generate_rhg(
                gamma=2.3,
                n=2**n_log2,
                d=avg_degree,
                seed=seed,
                coordinates=True,
            )

            with edgelist.open("w") as ef:
                ef.write(f"p {graph.num_vertices()} {graph.num_edges()}\n")
                for u, v in graph.edges():
                    ef.write(f"e {int(u)+1} {int(v)+1}\n")

            with xyz.open("w") as cf:
                for coord in graph.coordinates_2d():
                    cf.write(f"{coord[0]} {coord[1]}\n")
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
    """Generate random graphs using the KaGen Python library.

    Produces a weighted DIMACS graph via the edgelist converter script.

    configs entries:
        (name, grid_x_log2, grid_y_log2, seed)
    """
    configs = (
        ("grid_graph_X10_Y10_s1", 10, 10, 1),
        ("grid_graph_X10_Y10_s2", 10, 10, 2),
        ("grid_graph_X10_Y10_s3", 10, 10, 3),
        ("grid_graph_X10_Y10_s4", 10, 10, 4),
        ("grid_graph_X10_Y10_s5", 10, 10, 5),
        ("grid_graph_X13_Y13_s1", 13, 13, 1),
        ("grid_graph_X13_Y13_s2", 13, 13, 2),
        ("grid_graph_X13_Y13_s3", 13, 13, 3),
        ("grid_graph_X13_Y13_s4", 13, 13, 4),
        ("grid_graph_X13_Y13_s5", 13, 13, 5),
    )

    if not EDGELIST_CONVERTER_SCRIPT.exists():
        msg = "The edgelist converter is missing..."
        raise RuntimeError(msg)

    RANDOM_GRAPHS_PATH.mkdir(parents=True, exist_ok=True)

    for name, x_log2, y_log2, seed in configs:
        gr  = RANDOM_GRAPHS_PATH / f"{name}.gr"
        edgelist = RANDOM_GRAPHS_PATH / f"{name}.edgelist"
        xyz = RANDOM_GRAPHS_PATH / f"{name}.xyz"

        if gr.exists():
            continue

        if not (edgelist.exists() and xyz.exists()):
            print(f"Generating {name}")
            graph = kagen.generate_grid2d(
                grid_x=2**x_log2,
                grid_y=2**y_log2,
                p=1.0,
                periodic=False,
                seed=seed,
                coordinates=True,
            )

            with edgelist.open("w") as ef:
                ef.write(f"p {graph.num_vertices()} {graph.num_edges()}\n")
                for u, v in graph.edges():
                    ef.write(f"e {int(u)+1} {int(v)+1}\n")

            with xyz.open("w") as cf:
                for coord in graph.coordinates_2d():
                    cf.write(f"{coord[0]} {coord[1]}\n")
        else:
            print(f"Intermediate files exist for {name}, skipping KaGen")

        subprocess.run(
            [sys.executable, str(EDGELIST_CONVERTER_SCRIPT),
             str(edgelist), str(xyz), str(gr)],
            check=True,
        )
        edgelist.unlink(missing_ok=True)
        xyz.unlink(missing_ok=True)


def main() -> None:
    """Run all graph acquisition and generation steps."""
    download_road_graphs()
    generate_random_hyperbolic_graphs()
    generate_random_graphs()


if __name__ == "__main__":
    main()