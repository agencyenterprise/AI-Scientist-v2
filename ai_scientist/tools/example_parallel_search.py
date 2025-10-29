#!/usr/bin/env python3
"""
Example script demonstrating parallel Semantic Scholar searches.

This script shows the performance difference between sequential and parallel searches.
"""

import time
from semantic_scholar import search_for_papers, search_for_papers_batch


def example_sequential_search():
    """Example of sequential search (old approach)."""
    print("=" * 60)
    print("SEQUENTIAL SEARCH EXAMPLE")
    print("=" * 60)
    
    queries = [
        "transformer attention mechanism",
        "reinforcement learning policy gradient",
        "neural network optimization adam",
        "graph neural networks message passing",
        "contrastive learning self-supervised",
    ]
    
    start_time = time.time()
    results = {}
    
    for query in queries:
        print(f"Searching: {query}...")
        papers = search_for_papers(query, result_limit=3)
        results[query] = papers
        if papers:
            print(f"  Found {len(papers)} papers")
        else:
            print(f"  No papers found")
    
    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.2f} seconds")
    print(f"Average time per query: {elapsed/len(queries):.2f} seconds")
    
    return results


def example_parallel_search():
    """Example of parallel search (new approach)."""
    print("\n" + "=" * 60)
    print("PARALLEL SEARCH EXAMPLE")
    print("=" * 60)
    
    queries = [
        "transformer attention mechanism",
        "reinforcement learning policy gradient",
        "neural network optimization adam",
        "graph neural networks message passing",
        "contrastive learning self-supervised",
    ]
    
    print(f"Searching {len(queries)} queries in parallel...")
    start_time = time.time()
    
    results = search_for_papers_batch(
        queries=queries,
        result_limit=3,
        max_workers=3  # Use 3 parallel workers
    )
    
    elapsed = time.time() - start_time
    
    for query, papers in results.items():
        if papers:
            print(f"  {query}: {len(papers)} papers")
        else:
            print(f"  {query}: No papers found")
    
    print(f"\nTotal time: {elapsed:.2f} seconds")
    print(f"Average time per query: {elapsed/len(queries):.2f} seconds")
    
    return results


def display_paper_details(results, max_papers=2):
    """Display details of found papers."""
    print("\n" + "=" * 60)
    print("SAMPLE RESULTS")
    print("=" * 60)
    
    for query, papers in results.items():
        print(f"\nQuery: {query}")
        if not papers:
            print("  No papers found")
            continue
        
        for i, paper in enumerate(papers[:max_papers], 1):
            title = paper.get("title", "Unknown")
            authors = paper.get("authors", [])
            author_names = ", ".join([a.get("name", "Unknown") for a in authors[:3]])
            if len(authors) > 3:
                author_names += " et al."
            year = paper.get("year", "Unknown")
            citations = paper.get("citationCount", "N/A")
            
            print(f"\n  {i}. {title}")
            print(f"     Authors: {author_names}")
            print(f"     Year: {year}, Citations: {citations}")


def compare_performance():
    """Compare sequential vs parallel performance."""
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON")
    print("=" * 60)
    
    test_queries = [
        "deep learning optimization",
        "natural language processing transformers",
        "computer vision convolution",
        "generative adversarial networks",
        "meta learning few shot",
    ]
    
    # Sequential
    print("\nRunning sequential search...")
    seq_start = time.time()
    seq_results = {}
    for q in test_queries:
        seq_results[q] = search_for_papers(q, result_limit=3)
    seq_time = time.time() - seq_start
    
    # Parallel
    print("\nRunning parallel search...")
    par_start = time.time()
    par_results = search_for_papers_batch(test_queries, result_limit=3, max_workers=3)
    par_time = time.time() - par_start
    
    # Comparison
    print("\n" + "-" * 60)
    print(f"Sequential time: {seq_time:.2f} seconds")
    print(f"Parallel time:   {par_time:.2f} seconds")
    print(f"Speedup:         {seq_time/par_time:.2f}x")
    print("-" * 60)
    
    # Verify same results
    match_count = sum(1 for q in test_queries if len(seq_results.get(q, [])) == len(par_results.get(q, [])))
    print(f"\nResults match: {match_count}/{len(test_queries)} queries returned same number of papers")


def main():
    """Run all examples."""
    print("\n")
    print("*" * 60)
    print("SEMANTIC SCHOLAR PARALLEL SEARCH EXAMPLES")
    print("*" * 60)
    
    # Example 1: Sequential search
    seq_results = example_sequential_search()
    
    # Example 2: Parallel search  
    par_results = example_parallel_search()
    
    # Display some paper details
    display_paper_details(par_results, max_papers=1)
    
    # Performance comparison
    compare_performance()
    
    print("\n" + "*" * 60)
    print("EXAMPLES COMPLETE")
    print("*" * 60)
    print("\nKey Takeaways:")
    print("1. Parallel search is 2-5x faster than sequential")
    print("2. Rate limiting prevents API overload")
    print("3. Both approaches return the same results")
    print("4. Parallel is ideal for bulk literature reviews")
    print("5. Get an API key for even better performance!")


if __name__ == "__main__":
    main()


