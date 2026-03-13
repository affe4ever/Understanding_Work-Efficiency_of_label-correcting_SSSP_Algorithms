#!/usr/bin/env python3

import sys
import random
from multiprocessing import Pool, cpu_count


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


def _generate_chunk(args):
    edges_chunk, weight_min, weight_max, seed = args
    rng = random.Random(seed)
    return [f"a {u} {v} {rng.randint(weight_min, weight_max)}\n" for u, v in edges_chunk]


def write_gr(output_path, num_nodes, edges, weight_min, weight_max, seed):
    """
    Writes DIMACS .gr file:
        p sp N M
        a u v weight
    """
    rng = random.Random(seed)
    n_workers = cpu_count()
    chunk_size = max(1, len(edges) // n_workers)
    chunks = [edges[i:i + chunk_size] for i in range(0, len(edges), chunk_size)]
    chunk_seeds = [rng.randint(0, 2**32) for _ in chunks]

    with Pool(n_workers) as pool:
        results = pool.map(
            _generate_chunk,
            [(chunk, weight_min, weight_max, s) for chunk, s in zip(chunks, chunk_seeds)],
        )

    with open(output_path, "w") as f:
        f.write("c Generated from edgelist with random weights\n")
        f.write(f"p sp {num_nodes} {len(edges)}\n")
        for lines in results:
            f.writelines(lines)


def main():
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        print("Usage:")
        print("  python add_random_weights.py input.edgelist output.gr weight_min weight_max [seed]")
        sys.exit(1)

    edgelist_path = sys.argv[1]
    output_path = sys.argv[2]
    weight_min = int(sys.argv[3])
    weight_max = int(sys.argv[4])

    seed = int(sys.argv[5]) if len(sys.argv) == 6 else None

    if weight_min > weight_max:
        print("Error: weight_min must be <= weight_max")
        sys.exit(1)

    num_nodes, edges = read_edgelist(edgelist_path)

    if num_nodes is None:
        print("Error: invalid DIMACS edgelist (missing 'p' line)")
        sys.exit(1)

    write_gr(output_path, num_nodes, edges, weight_min, weight_max, seed)

    print("Done.")


if __name__ == "__main__":
    main()