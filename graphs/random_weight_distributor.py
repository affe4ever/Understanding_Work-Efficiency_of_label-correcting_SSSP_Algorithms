"""
random_weight_distributor.py

Converts a DIMACS .edgelist file to a .gr weighted graph file by assigning
random integer weights to every edge. Designed for massive graphs (hundreds
of millions of edges) with streaming I/O and batched RNG so memory usage
stays flat regardless of graph size.

Usage:
    python random_weight_distributor.py input.edgelist output.gr weight_min weight_max [seed]

Example:
    python random_weight_distributor.py graph.edgelist graph.gr 1 100000 42
"""

import sys
import os
import numpy as np

# ── tuneable constants ────────────────────────────────────────────────────────
# Number of edges whose weights are generated per RNG batch.
# Larger  → fewer numpy calls, better throughput (uses ~8 MB per 1 M edges).
# Smaller → lower peak memory when weight_max – weight_min is huge.
BATCH_SIZE = 1_000_000

# I/O buffer sizes (bytes).  Large buffers cut syscall overhead significantly
# for sequential reads/writes on files this large.
READ_BUFFER  = 256 * 1024 * 1024   # 256 MB
WRITE_BUFFER = 256 * 1024 * 1024   # 256 MB
# ─────────────────────────────────────────────────────────────────────────────


def read_edgelist_metadata(path: str):
    """
    Fast first-pass scan: find the 'p' header line and return (num_nodes,
    num_edges).  Everything else is skipped so this is O(1) in practice –
    the 'p' line is always near the top of DIMACS files.
    """
    try:
        with open(path, "r", buffering=READ_BUFFER) as fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] == "c":
                    continue
                if line[0] == "p":
                    parts = line.split()
                    # Accept both "p N M" and "p sp N M"
                    if len(parts) == 3:
                        return int(parts[1]), int(parts[2])
                    elif len(parts) >= 4:
                        return int(parts[-2]), int(parts[-1])
                    else:
                        return None, None
    except OSError as exc:
        print(f"Error reading {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    return None, None


def write_gr(
    in_path: str,
    out_path: str,
    num_nodes: int,
    num_edges: int,
    weight_min: int,
    weight_max: int,
    seed,
):
    """
    Stream the input edgelist, attach a random weight to every 'e' line, and
    write DIMACS .gr output.  Weights are generated in large numpy batches so
    Python-level overhead per edge is negligible.
    """
    rng   = np.random.default_rng(seed)
    span  = weight_max - weight_min + 1   # inclusive range size

    # Pre-generate the first batch immediately so the hot loop never blocks.
    weight_buf   = rng.integers(0, span, size=BATCH_SIZE, dtype=np.int64)
    buf_pos      = 0          # next unused index inside weight_buf
    edges_seen   = 0          # progress counter
    report_every = max(1, num_edges // 20)   # ~5 % increments

    try:
        with (
            open(in_path,  "r", buffering=READ_BUFFER)  as fin,
            open(out_path, "w", buffering=WRITE_BUFFER) as fout,
        ):
            # ── header ───────────────────────────────────────────────────────
            fout.write("c Generated from edgelist with random weights\n")
            fout.write(f"p sp {num_nodes} {num_edges}\n")

            # ── edge lines ───────────────────────────────────────────────────
            for raw in fin:
                if not raw or raw[0] != "e":
                    continue

                # Refill weight buffer when exhausted.
                if buf_pos >= BATCH_SIZE:
                    weight_buf = rng.integers(0, span, size=BATCH_SIZE, dtype=np.int64)
                    buf_pos    = 0

                w = int(weight_buf[buf_pos]) + weight_min
                buf_pos += 1

                # Parse "e <u> <v>" – using split() handles any whitespace.
                parts = raw.split()          # ['e', 'u', 'v']
                fout.write(f"a {parts[1]} {parts[2]} {w}\n")

                edges_seen += 1
                if edges_seen % report_every == 0:
                    pct = 100.0 * edges_seen / num_edges
                    print(
                        f"  {edges_seen:,} / {num_edges:,} edges written "
                        f"({pct:.1f}%)",
                        file=sys.stderr,
                    )

    except OSError as exc:
        print(f"\nI/O error: {exc}", file=sys.stderr)
        # Clean up partial output so callers don't mistake it for a good file.
        try:
            os.remove(out_path)
        except OSError:
            pass
        sys.exit(1)

    if edges_seen != num_edges:
        print(
            f"Warning: header declared {num_edges:,} edges but "
            f"{edges_seen:,} 'e' lines were found.",
            file=sys.stderr,
        )


def main():
    if len(sys.argv) < 5 or len(sys.argv) > 6:
        print("Usage:")
        print(
            "  python random_weight_distributor.py "
            "input.edgelist output.gr weight_min weight_max [seed]"
        )
        sys.exit(1)

    edgelist_path = sys.argv[1]
    output_path   = sys.argv[2]

    try:
        weight_min = int(sys.argv[3])
        weight_max = int(sys.argv[4])
    except ValueError:
        print("Error: weight_min and weight_max must be integers.", file=sys.stderr)
        sys.exit(1)

    seed = None
    if len(sys.argv) == 6:
        try:
            seed = int(sys.argv[5])
        except ValueError:
            print("Error: seed must be an integer.", file=sys.stderr)
            sys.exit(1)

    if weight_min > weight_max:
        print("Error: weight_min must be <= weight_max", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(edgelist_path):
        print(f"Error: input file not found: {edgelist_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading metadata from {edgelist_path}...", file=sys.stderr)
    num_nodes, num_edges = read_edgelist_metadata(edgelist_path)

    if num_nodes is None:
        print(
            "Error: invalid DIMACS edgelist (missing or malformed 'p' line)",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"  nodes={num_nodes:,}  edges={num_edges:,}  "
        f"weights=[{weight_min}, {weight_max}]  seed={seed}",
        file=sys.stderr,
    )
    print(f"Writing weighted graph to {output_path}...", file=sys.stderr)

    write_gr(
        edgelist_path,
        output_path,
        num_nodes,
        num_edges,
        weight_min,
        weight_max,
        seed,
    )

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()