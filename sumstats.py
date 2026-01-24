#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import csv
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from collections import defaultdict

# Allocator colors
ALLOCATOR_COLORS = {
    'default': '#78909c',   # blue-grey (distinct from smalloc green)
    'glibc': '#5c6bc0',      # indigo
    'jemalloc': '#66bb6a',    # green
    'snmalloc': '#ab47bc',    # purple
    'mimalloc': '#ffca28',   # amber
    'rpmalloc': '#ff7043',   # deep orange
    'smalloc': '#42a5f5',   # blue
}
UNKNOWN_ALLOCATOR_COLOR = '#9e9e9e'  # gray

# Canonical allocator ordering
ALLOCATOR_ORDER = ['default', 'jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc', 'smalloc']

def get_color(name):
    return ALLOCATOR_COLORS.get(name, UNKNOWN_ALLOCATOR_COLOR)

def sort_allocators(names):
    """Sort allocator names in canonical order: default, known allocators, unknown, smalloc last."""
    def sort_key(name):
        if name in ALLOCATOR_ORDER:
            return (0, ALLOCATOR_ORDER.index(name))
        else:
            return (0, ALLOCATOR_ORDER.index('smalloc') - 0.5)
    return sorted(names, key=sort_key)

def parse_time(time_str):
    """Convert time string like '1.23 µs' or '1.99ms' to nanoseconds."""
    time_str = time_str.strip()

    # Try splitting by space first
    parts = time_str.split()
    if len(parts) == 2:
        value_str = parts[0]
        unit = parts[1]
    else:
        # No space - extract numeric part and unit part
        # Find where digits/decimal end and unit begins
        i = 0
        while i < len(time_str) and (time_str[i].isdigit() or time_str[i] == '.'):
            i += 1
        if i == 0 or i == len(time_str):
            return None
        value_str = time_str[:i]
        unit = time_str[i:]

    try:
        value = float(value_str)
        multipliers = {'ns': 1, 'µs': 1000, 'us': 1000, 'ms': 1_000_000, 's': 1_000_000_000}
        return value * multipliers.get(unit, 1)
    except (ValueError, KeyError):
        return None

def format_time(ns):
    """Format nanoseconds as human-readable string with up to 2 decimal places."""
    if ns >= 1_000_000_000:
        val = ns / 1_000_000_000
        if val >= 100:
            return f"{val:.0f}s"
        elif val >= 10:
            return f"{val:.1f}s"
        else:
            return f"{val:.2f}s"
    elif ns >= 1_000_000:
        val = ns / 1_000_000
        if val >= 100:
            return f"{val:.0f}ms"
        elif val >= 10:
            return f"{val:.1f}ms"
        else:
            return f"{val:.2f}ms"
    elif ns >= 1_000:
        val = ns / 1_000
        if val >= 100:
            return f"{val:.0f}μs"
        elif val >= 10:
            return f"{val:.1f}μs"
        else:
            return f"{val:.2f}μs"
    else:
        if ns >= 100:
            return f"{ns:.0f}ns"
        elif ns >= 10:
            return f"{ns:.1f}ns"
        else:
            return f"{ns:.2f}ns"

def format_pct_diff(ratio):
    """Format percentage difference from baseline."""
    pct_diff = (ratio - 1.0) * 100
    if abs(pct_diff) < 0.5:
        return "0%"
    elif pct_diff > 0:
        return f"+{int(round(pct_diff))}%"
    else:
        return f"{int(round(pct_diff))}%"

def get_allocator_name(engine):
    """Extract allocator name from engine string like 'rust/regex-smalloc'."""
    engine = engine.strip()
    # Handle format: rust/regex-allocator or rust/regex
    if engine == 'rust/regex':
        engine = 'default'
        return engine
    if '-' in engine:
        # rust/regex-smalloc -> smalloc
        engine = engine.split('-')[-1]
        return engine
    return engine

def generate_graph(allocators, arith_mean_ratios, normalized_sums, metadata, output_file, title_suffix=''):
    """Generate bar chart comparing allocator performance."""
    # Try to use Arial/Helvetica for a cleaner look
    try:
        available_fonts = [f.name for f in fm.fontManager.ttflist]
        if 'Arial' in available_fonts:
            plt.rcParams['font.family'] = 'Arial'
        elif 'Helvetica' in available_fonts:
            plt.rcParams['font.family'] = 'Helvetica'
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
    except:
        plt.rcParams['font.family'] = 'sans-serif'

    # Calculate percentages (baseline = 100%)
    baseline_ratio = arith_mean_ratios.get('default', 1.0)
    percentages = [(arith_mean_ratios[a] / baseline_ratio) * 100 for a in allocators]

    # Get baseline absolute time for y-axis label
    baseline_time_ns = normalized_sums.get('default', 0)
    baseline_time_str = format_time(baseline_time_ns)

    # Create figure
    fig, ax = plt.subplots(figsize=(10, 5))
    plt.subplots_adjust(bottom=0.22, top=0.88, left=0.08, right=0.97)

    # Bar properties
    n_allocators = len(allocators)
    bar_width = 0.75

    # Create bars
    bars = []
    for i, (allocator, pct) in enumerate(zip(allocators, percentages)):
        color = get_color(allocator)
        bar = ax.bar(i, pct, bar_width, color=color, edgecolor='none')
        bars.append(bar[0])

    # Set y-axis
    max_pct = max(percentages)
    ax.set_ylim(0, max(max_pct * 1.15, 115))
    ax.set_ylabel(f'Time vs Baseline (%, baseline = {baseline_time_str})', fontsize=11, color='#999999')

    # Style y-axis
    ax.yaxis.set_tick_params(colors='#999999')
    for label in ax.get_yticklabels():
        label.set_color('#999999')
    ax.spines['left'].set_color('#999999')

    # X-axis labels
    ax.set_xticks(range(n_allocators))
    ax.set_xticklabels(allocators, fontsize=11)

    # Grid
    ax.yaxis.grid(True, linestyle='--', alpha=0.3, linewidth=0.5)
    ax.set_axisbelow(True)

    # Fixed offset for labels (in points)
    LABEL_OFFSET_ABOVE = 3
    LABEL_OFFSET_INSIDE = 8

    # Add labels: formatted time above bar, percentage diff inside bar
    for i, (bar, allocator, pct) in enumerate(zip(bars, allocators, percentages)):
        bar_height = bar.get_height()
        x_pos = bar.get_x() + bar.get_width() / 2

        # Formatted time above the bar
        norm_sum = normalized_sums[allocator]
        time_label = format_time(norm_sum)
        ax.annotate(time_label,
                    xy=(x_pos, bar_height),
                    xytext=(0, LABEL_OFFSET_ABOVE),
                    textcoords='offset points',
                    ha='center', va='bottom',
                    fontsize=9, fontweight='bold',
                    color='#333333')

        # Percentage diff inside the bar (near the top)
        if allocator == 'default':
            pct_label = "baseline"
        else:
            pct_label = format_pct_diff(arith_mean_ratios[allocator])
        ax.annotate(pct_label,
                    xy=(x_pos, bar_height),
                    xytext=(0, -LABEL_OFFSET_INSIDE),
                    textcoords='offset points',
                    ha='center', va='top',
                    fontsize=9, fontweight='bold',
                    color='white')

    # Title
    base_title = "Performance of rust/regex with different allocators"
    if title_suffix:
        title = f"{base_title}{title_suffix}"
    else:
        title = f"{base_title}—time (lower is better)"
    ax.set_title(title, fontsize=16, fontweight='bold', pad=15, color='#333333')

    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#000000')

    # Metadata
    meta_parts = []
    if metadata.get('source'):
        meta_parts.append(f"Source: {metadata['source']}")
    elif metadata.get('commit'):
        meta_parts.append("Source: https://github.com/zooko/rebar")
    if metadata.get('commit'):
        meta_parts.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        meta_parts.append(f'Git status: "{metadata["git_status"]}"')

    line2_parts = []
    if metadata.get('cpu'):
        line2_parts.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        line2_parts.append(f"OS: {metadata['os']}")

    if meta_parts:
        fig.text(0.5, 0.08, " · ".join(meta_parts), ha='center', fontsize=10,
                 color='#666666', family='monospace')
    if line2_parts:
        fig.text(0.5, 0.03, " · ".join(line2_parts), ha='center', fontsize=10,
                 color='#666666', family='monospace')

    plt.savefig(output_file, format='svg', bbox_inches='tight', dpi=150)
    plt.close()

    print(f"\n📊 Graph saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Analyze rebar benchmark results and generate comparison graphs')
    parser.add_argument('csv_file', help='CSV file from rebar measure')
    parser.add_argument('--graph', help='Output SVG graph to this file')
    parser.add_argument('--title-suffix', default='', help='Suffix to add to graph title')
    parser.add_argument('--commit', help='Git commit hash')
    parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
    parser.add_argument('--cpu', help='CPU type')
    parser.add_argument('--os', help='OS type')
    parser.add_argument('--source', help='Source URL')

    args = parser.parse_args()

    # Parse CSV file
    test_data = defaultdict(dict)  # test_name -> {allocator -> median_ns}

    with open(args.csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_name = row['name']
            engine = row['engine']
            allocator = get_allocator_name(engine)
            median_ns = parse_time(row['median'])
            if median_ns is not None:
                test_data[test_name][allocator] = median_ns

    # Filter to tests that have a 'default' baseline
    valid_tests = [name for name, results in test_data.items() if 'default' in results]

    if not valid_tests:
        print("No tests with 'default' allocator found.", file=sys.stderr)
        sys.exit(1)

    # Collect normalized times for each allocator
    # For each test, compute how long it would take if run for a standardized
    # number of iterations (the number that would complete in 1 second with default allocator)
    allocator_normalized_times = defaultdict(list)

    for test_name in valid_tests:
        results = test_data[test_name]
        baseline_time = results['default']  # time for default allocator (ns)

        # iterations = how many iterations would complete in 1 second with default allocator
        # If baseline_time is in nanoseconds, then iterations = 1e9 / baseline_time
        iterations = 1e9 / baseline_time

        for allocator, time_ns in results.items():
            # How long would this allocator take for `iterations` iterations?
            # Each iteration takes time_ns, so total = time_ns * iterations
            normalized_time = time_ns * iterations
            allocator_normalized_times[allocator].append(normalized_time)

    # Sum of normalized times for each allocator
    normalized_sums = {}
    for allocator, times in allocator_normalized_times.items():
        normalized_sums[allocator] = sum(times)

    # Arithmetic mean ratio = allocator's sum / default's sum
    baseline_sum = normalized_sums.get('default', 1.0)
    arith_mean_ratios = {}
    for allocator in normalized_sums:
        arith_mean_ratios[allocator] = normalized_sums[allocator] / baseline_sum

    # Sort allocators in canonical order
    sorted_allocators = sort_allocators(list(arith_mean_ratios.keys()))

    # Print summary
    print(f"\nBenchmarks analyzed: {len(valid_tests)}")
    print(f"\n{'Allocator':<12} {'Normalized Sum':>16} {'vs Baseline':>12}")
    print("-" * 44)

    for allocator in sorted_allocators:
        norm_sum = normalized_sums[allocator]
        ratio = arith_mean_ratios[allocator]
        pct = (ratio - 1.0) * 100
        vs_baseline = "baseline" if allocator == 'default' else f"{pct:+.1f}%"
        print(f"{allocator:<12} {format_time(norm_sum):>16} {vs_baseline:>12}")

    # Generate graph if requested
    if args.graph:
        metadata = {
            'commit': args.commit,
            'git_status': args.git_status,
            'cpu': args.cpu,
            'os': args.os,
            'source': args.source
        }
        generate_graph(sorted_allocators, arith_mean_ratios, normalized_sums, metadata, args.graph, args.title_suffix)

if __name__ == '__main__':
    main()
