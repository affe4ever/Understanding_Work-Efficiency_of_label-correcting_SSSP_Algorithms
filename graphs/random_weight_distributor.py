#!/usr/bin/env python3

import sys
import random
from multiprocessing import Pool, cpu_count


def read_edgelist_metadata(edgelist_path):
    """
    Reads DIMACS-style edge list and returns (num_nodes, num_edges, file_size_bytes).
    Does not load edges into memory.
    """
    num_nodes = None
    num_edges = 0

    with open(edgelist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("c"):
                continue
            parts = line.split()
            if parts[0] == "p":
                num_nodes = int(parts[1])
            elif parts[0] == "e":
                num_edges += 1

    file_size = __import__('os').path.getsize(edgelist_path)
    return num_nodes, num_edges, file_size


def _generate_chunk(args):
    """Worker function to generate weights for a chunk of edges."""
    edges_chunk, weight_min, weight_max, seed = args
    rng = random.Random(seed)
    return [f"a {u} {v} {rng.randint(weight_min, weight_max)}\n" for u, v in edges_chunk]


def write_gr(edgelist_path, output_path, num_nodes, weight_min, weight_max, seed):
    """
    Writes DIMACS .gr file:
        p sp N M
        a u v weight
    """
    rng = random.Random(seed)
    
    # Estimate optimal worker count based on file size
    file_size = __import__('os').path.getsize(edgelist_path)
    available_workers = cpu_count()
    # Use fewer workers for massive graphs to reduce memory overhead
    if file_size > 1e9:  # > 1 GB
        n_workers = max(2, available_workers // 2)
    else:
        n_workers = available_workers
    
    # Stream edges in batches
    batch_size = max(1000, 100000 // n_workers)  # Adaptive batch size
    edges_batch = []
    
    with open(output_path, "w") as out_f:
        out_f.write("c Generated from edgelist with random weights\n")
        out_f.write(f"p sp {num_nodes} 0\n")  # Will update edge count later
        
        # Count total edges while streaming
        total_edges = 0
        
        with open(edgelist_path, "r") as in_f:
            for line in in_f:
                line = line.strip()
                if not line or line.startswith("c"):
                    continue
                
                parts = line.split()
                if parts[0] == "p":
                    continue
                elif parts[0] == "e":
                    u, v = int(parts[1]), int(parts[2])
                    edges_batch.append((u, v))
                    total_edges += 1
                    
                    # Process batch when full
                    if len(edges_batch) >= batch_size:
                        with Pool(n_workers) as pool:
                            chunk_size = max(1, len(edges_batch) // n_workers)
                            chunks = [
                                edges_batch[i:i + chunk_size] 
                                for i in range(0, len(edges_batch), chunk_size)
                            ]
                            chunk_seeds = [rng.randint(0, 2**31 - 1) for _ in chunks]
                            
                            results = pool.map(
                                _generate_chunk,
                                [(chunk, weight_min, weight_max, s) 
                                 for chunk, s in zip(chunks, chunk_seeds)],
                            )
                            
                            # Write immediately, don't buffer
                            for lines in results:
                                out_f.writelines(lines)
                        
                        edges_batch = []
        
        # Process remaining edges
        if edges_batch:
            with Pool(n_workers) as pool:
                chunk_size = max(1, len(edges_batch) // n_workers)
                chunks = [
                    edges_batch[i:i + chunk_size] 
                    for i in range(0, len(edges_batch), chunk_size)
                ]
                chunk_seeds = [rng.randint(0, 2**31 - 1) for _ in chunks]
                
                results = pool.map(
                    _generate_chunk,
                    [(chunk, weight_min, weight_max, s) 
                     for chunk, s in zip(chunks, chunk_seeds)],
                )
                
                for lines in results:
                    out_f.writelines(lines)
        
        # Update header with correct edge count
        out_f.seek(0)
        out_f.write("c Generated from edgelist with random weights\n")
        out_f.write(f"p sp {num_nodes} {total_edges}\n")


def main():
    if len(sys.argv) < 4 or len(sys.argv) > 6:
        print("Usage:")
        print("  python random_weight_distributor.py input.edgelist output.gr weight_min weight_max [seed]")
        sys.exit(1)

    edgelist_path = sys.argv[1]
    output_path = sys.argv[2]
    weight_min = int(sys.argv[3])
    weight_max = int(sys.argv[4])
    seed = int(sys.argv[5]) if len(sys.argv) == 6 else None

    if weight_min > weight_max:
        print("Error: weight_min must be <= weight_max")
        sys.exit(1)

    print(f"Reading metadata from {edgelist_path}...", file=sys.stderr)
    num_nodes, num_edges, file_size = read_edgelist_metadata(edgelist_path)

    if num_nodes is None:
        print("Error: invalid DIMACS edgelist (missing 'p' line)")
        sys.exit(1)

    print(f"Nodes: {num_nodes}, Edges: {num_edges}, Size: {file_size / 1e6:.1f} MB", 
          file=sys.stderr)
    print(f"Writing weighted graph to {output_path}...", file=sys.stderr)
    
    write_gr(edgelist_path, output_path, num_nodes, weight_min, weight_max, seed)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
