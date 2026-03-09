#!/usr/bin/env python3

import sys
import math


def read_coordinates(xyz_path):
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


def read_edgelist(edgelist_path):
    """
    Reads DIMACS-style edge list with:
        p n m
        e u v
    Returns (num_nodes, edges)
    """
    edges = []
    num_nodes = None

    with open(edgelist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c"):
                continue

            parts = line.split()

            if parts[0] == "p":
                num_nodes = int(parts[1])
            elif parts[0] == "e":
                u = int(parts[1])
                v = int(parts[2])
                edges.append((u, v))

    return num_nodes, edges


def hyperbolic_distance(u, v):
    """
    Hyperbolic distance in PoincarÃ© disk model.
    u, v are (x, y)
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
        raise ValueError("Point lies outside the unit disk.")

    arg = 1 + (2 * diff_sq) / denom

    # Clamp for floating-point safety
    arg = max(arg, 1.0)

    return math.acosh(arg)


def write_gr(output_path, num_nodes, edges, coords):
    """
    Writes DIMACS .gr file:
        p sp N M
        a u v weight
    """
    with open(output_path, "w") as f:
        f.write("c Generated from edgelist + xyz\n")
        f.write(f"p sp {num_nodes} {len(edges)}\n")

        for u, v in edges:
            dist = hyperbolic_distance(coords[u], coords[v])

            # Convert to integer weight (like road datasets)
            weight = int(round(dist * 100000))

            f.write(f"a {u} {v} {weight}\n")


def main():
    if len(sys.argv) != 4:
        print("Usage: python edgelist_to_gr.py input.edgelist input.xyz output.gr")
        sys.exit(1)

    edgelist_path = sys.argv[1]
    xyz_path = sys.argv[2]
    output_path = sys.argv[3]

    num_nodes, edges = read_edgelist(edgelist_path)
    coords = read_coordinates(xyz_path)

    if num_nodes != len(coords):
        print("Warning: number of nodes in edgelist and xyz differ.")

    write_gr(output_path, num_nodes, edges, coords)

    print("Done.")


if __name__ == "__main__":
    main()