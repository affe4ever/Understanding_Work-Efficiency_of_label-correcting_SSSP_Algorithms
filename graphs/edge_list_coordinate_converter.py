#!/usr/bin/env python3

import sys
import math


def read_coordinates(xyz_path):
    """
    Reads coordinates from .xyz file into memory.
    Only one coordinate per node.
    """
    coords = {}
    eps = 1e-12  # safety margin

    with open(xyz_path, "r") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            x, y = map(float, line.split()[:2])
            r2 = x*x + y*y

            if r2 >= 1.0:
                r = math.sqrt(r2)
                scale = (1.0 - eps) / r
                x *= scale
                y *= scale

            coords[idx] = (x, y)

    return coords


def get_edgelist_info(edgelist_path):
    """
    Reads DIMACS-style edge list header to get graph info.
    Returns (num_nodes, num_edges)
    """
    num_nodes = None
    num_edges = None

    with open(edgelist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c"):
                continue

            parts = line.split()
            if parts[0] == "p":
                num_nodes = int(parts[1])
                num_edges = int(parts[2])
                break

    return num_nodes, num_edges


def stream_edges(edgelist_path):
    """
    Generator that yields edges from edgelist without storing all in memory.
    """
    with open(edgelist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c") or line.startswith("p"):
                continue

            parts = line.split()
            if parts[0] == "e":
                u = int(parts[1])
                v = int(parts[2])
                yield (u, v)


def hyperbolic_distance(u, v):
    """
    Hyperbolic distance in Poincaré disk model.
    u, v are (x, y) tuples.
    Returns distance as float, or None if invalid.
    """
    ux, uy = u
    vx, vy = v

    norm_u_sq = ux * ux + uy * uy
    norm_v_sq = vx * vx + vy * vy

    dx = ux - vx
    dy = uy - vy
    diff_sq = dx * dx + dy * dy

    denom = (1 - norm_u_sq) * (1 - norm_v_sq)

    # Prevent numerical issues
    if denom <= 0:
        return None

    arg = 1 + (2 * diff_sq) / denom

    # Clamp for floating-point safety
    arg = max(arg, 1.0)

    try:
        return math.acosh(arg)
    except (ValueError, OverflowError):
        return None


def write_gr(output_path, num_nodes, num_edges, edgelist_path, coords):
    """
    Reads edges from edgelist and writes to .gr file in streaming fashion.
    This avoids loading all edges into memory.
    """
    edges_written = 0
    edges_skipped = 0

    with open(output_path, "w") as f:
        f.write("c Generated from edgelist + xyz\n")
        f.write(f"p sp {num_nodes} {num_edges}\n")

        for u, v in stream_edges(edgelist_path):
            if u not in coords or v not in coords:
                edges_skipped += 1
                continue

            dist = hyperbolic_distance(coords[u], coords[v])
            if dist is None:
                edges_skipped += 1
                continue

            # Convert to integer weight (like road datasets)
            weight = int(round(dist * 100000))
            weight = max(weight, 1)

            f.write(f"a {u} {v} {weight}\n")
            edges_written += 1

    return edges_written, edges_skipped


def main():
    if len(sys.argv) != 4:
        print("Usage: python edge_list_coordinate_converter.py input.edgelist input.xyz output.gr")
        sys.exit(1)

    edgelist_path = sys.argv[1]
    xyz_path = sys.argv[2]
    output_path = sys.argv[3]

    coords = read_coordinates(xyz_path)
    num_nodes, num_edges = get_edgelist_info(edgelist_path)
    edges_written, edges_skipped = write_gr(
        output_path, num_nodes, num_edges, edgelist_path, coords
    )

    print(f"Done. Wrote {edges_written} edges (skipped {edges_skipped})")


if __name__ == "__main__":
    main()