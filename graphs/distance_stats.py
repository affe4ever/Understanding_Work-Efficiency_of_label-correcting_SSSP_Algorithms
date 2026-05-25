#!/usr/bin/env python3
"""
Script to compute distance statistics from a graph file.

Reads a graph file in DIMACS shortest path format and returns:
- Shortest distance (minimum edge weight)
- Longest distance (maximum edge weight)
- Average distance (mean of all edge weights)
- Median distance (median of all edge weights)
"""

from pathlib import Path
import sys


def compute_distance_stats(filepath, compute_median=True):
    """
    Compute distance statistics from a graph file with memory efficiency.
    
    File format (DIMACS shortest path):
    - Lines starting with 'c' are comments
    - Lines starting with 'p' are problem definition: p sp nodes edges
    - Lines starting with 'a' are edges: a source destination weight
    
    First pass: compute min, max, avg, count (memory efficient)
    Second pass: compute median if requested (uses binary search to minimize memory)
    
    Args:
        filepath: Path to the graph file
        compute_median: If True, compute median (requires second pass)
        
    Returns:
        dict with keys: min, max, avg, median, count
    """
    # First pass: compute min, max, sum, count
    min_dist = float('inf')
    max_dist = float('-inf')
    total_sum = 0
    count = 0
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('c'):
                continue
            
            # Skip problem definition
            if line.startswith('p'):
                continue
            
            # Parse edge lines
            if line.startswith('a'):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        weight = int(parts[3])
                        min_dist = min(min_dist, weight)
                        max_dist = max(max_dist, weight)
                        total_sum += weight
                        count += 1
                    except (ValueError, IndexError):
                        pass
    
    if count == 0:
        return None
    
    stats = {
        'min': min_dist,
        'max': max_dist,
        'avg': total_sum / count,
        'count': count,
    }
    
    # Second pass: compute median if requested
    if compute_median:
        median_dist = _compute_median_efficient(filepath, count)
        stats['median'] = median_dist
    else:
        stats['median'] = None
    
    return stats


def _compute_median_efficient(filepath, count):
    """
    Compute median using a memory-efficient approach for large datasets.
    
    Uses a two-phase approach:
    1. Count occurrences of each distance value
    2. Find the median position
    
    Args:
        filepath: Path to the graph file
        count: Total number of edges
        
    Returns:
        The median distance value
    """
    from collections import defaultdict
    
    # Count frequency of each distance (only stores unique values)
    freq = defaultdict(int)
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('a'):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        weight = int(parts[3])
                        freq[weight] += 1
                    except (ValueError, IndexError):
                        pass
    
    # Find median by accumulated frequency
    sorted_distances = sorted(freq.keys())
    accumulated = 0
    median_pos = count / 2.0
    
    for dist in sorted_distances:
        accumulated += freq[dist]
        if accumulated >= median_pos:
            return dist
    
    return sorted_distances[-1] if sorted_distances else None


def main():
    if len(sys.argv) < 2:
        print("Usage: python distance_stats.py <graph_file> [--no-median]")
        print("  --no-median: Skip median calculation (faster for very large graphs)")
        sys.exit(1)
    
    filepath = Path(sys.argv[1])
    compute_median = "--no-median" not in sys.argv
    
    if not filepath.exists():
        print(f"Error: File '{filepath}' not found")
        sys.exit(1)
    
    print(f"Processing: {filepath.name}")
    stats = compute_distance_stats(filepath, compute_median=compute_median)
    
    if stats is None:
        print("Error: No edges found in file")
        sys.exit(1)
    
    print(f"\nDistance Statistics")
    print(f"{'='*50}")
    print(f"Total edges:       {stats['count']:,}")
    print(f"Shortest distance: {stats['min']}")
    print(f"Longest distance:  {stats['max']}")
    print(f"Average distance:  {stats['avg']:.2f}")
    if stats['median'] is not None:
        print(f"Median distance:   {stats['median']}")
    else:
        print(f"Median distance:   (skipped)")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
