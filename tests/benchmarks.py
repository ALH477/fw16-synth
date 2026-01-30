#!/usr/bin/env python3
"""Performance Benchmarks for FW16 Synth"""

import time
import statistics
from argparse import ArgumentParser


def run_benchmark(func, iterations=10000, warmup=100):
    """Run a benchmark function"""
    for _ in range(warmup):
        func()
    
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)
    
    total = sum(times)
    avg = statistics.mean(times)
    min_t = min(times)
    max_t = max(times)
    ops = iterations / total
    
    return {
        'name': '',
        'iterations': iterations,
        'total': total,
        'avg': avg,
        'min': min_t,
        'max': max_t,
        'ops': ops
    }


def velocity_linear():
    """Linear velocity calculation"""
    elapsed = 0.050
    t_fast = 0.015
    t_slow = 0.200
    v_min = 20
    v_max = 127
    elapsed = max(t_fast, min(t_slow, elapsed))
    normalized = (elapsed - t_fast) / (t_slow - t_fast)
    return int(v_max - normalized * (v_max - v_min))


def velocity_exponential():
    """Exponential velocity calculation"""
    elapsed = 0.050
    t_fast = 0.015
    t_slow = 0.200
    v_min = 20
    v_max = 127
    elapsed = max(t_fast, min(t_slow, elapsed))
    normalized = (elapsed - t_fast) / (t_slow - t_fast)
    return int(v_max - (normalized ** 2) * (v_max - v_min))


def modulation_pitch_bend():
    """Pitch bend from X-axis"""
    return 8192 + int((0.75 - 0.5) * 2 * 8192)


def modulation_filter_cutoff():
    """Filter cutoff from Y-axis (inverted)"""
    return int(127 * (1.0 - 0.25))


def modulation_expression():
    """Expression from pressure"""
    return int(0.5 * 127)


def dict_get():
    """Dictionary get operation"""
    return {}.get(500, 0)


def dict_set():
    """Dictionary set operation"""
    d = {}
    d[500] = 501
    return d


def run_all():
    """Run all benchmarks"""
    parser = ArgumentParser(description="FW16 Synth Performance Benchmarks")
    parser.add_argument('-n', '--iterations', type=int, default=10000)
    parser.add_argument('-q', '--quick', action='store_true')
    args = parser.parse_args()
    
    iterations = 1000 if args.quick else args.iterations
    
    print("=" * 70)
    print("FW16 Synth Performance Benchmarks")
    print("=" * 70)
    print(f"Iterations: {iterations:,}")
    print()
    
    # Velocity benchmarks
    print("Velocity Calculation:")
    r = run_benchmark(velocity_linear, iterations)
    print(f"  linear: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    r = run_benchmark(velocity_exponential, iterations)
    print(f"  exponential: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    # Modulation benchmarks
    print("Modulation:")
    r = run_benchmark(modulation_pitch_bend, iterations)
    print(f"  pitch_bend: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    r = run_benchmark(modulation_filter_cutoff, iterations)
    print(f"  filter_cutoff: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    r = run_benchmark(modulation_expression, iterations)
    print(f"  expression: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    # Dictionary benchmarks
    print("Dictionary Operations:")
    r = run_benchmark(dict_get, iterations)
    print(f"  get: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    r = run_benchmark(dict_set, iterations)
    print(f"  set: avg={r['avg']*1000:.2f}us, ops/sec={r['ops']:.0f}")
    
    print()
    print("=" * 70)
    print("Target: >50,000 ops/sec for time-critical operations")


if __name__ == "__main__":
    run_all()
