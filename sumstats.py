#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import csv
import argparse
from collections import defaultdict

# Allocator colors
ALLOCATOR_COLORS = {
    'default': '#78909c',   # blue-grey (distinct from smalloc green)
    'glibc': '#5c6bc0',     # indigo
    'jemalloc': '#66bb6a',  # green
    'snmalloc': '#ab47bc',  # purple
    'mimalloc': '#ffca28',  # amber
    'rpmalloc': '#ff7043',  # deep orange
    'smalloc': '#42a5f5',   # blue
    'smalloc + ffi': '#93c2f9', # light blue
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

def escape_xml(text):
    """Escape special XML characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def rounded_rect_path(x, y, width, height, radius):
    """Generate SVG path for rectangle with only top corners rounded."""
    # Ensure radius doesn't exceed half the width or height
    r = min(radius, width / 2, height / 2)

    # Start at bottom-left, go clockwise
    # Bottom-left corner (sharp)
    path = f"M {x} {y + height}"
    # Bottom edge to bottom-right (sharp corner)
    path += f" L {x + width} {y + height}"
    # Right edge up to where top-right curve starts
    path += f" L {x + width} {y + r}"
    # Top-right rounded corner (arc)
    path += f" A {r} {r} 0 0 0 {x + width - r} {y}"
    # Top edge to where top-left curve starts
    path += f" L {x + r} {y}"
    # Top-left rounded corner (arc)
    path += f" A {r} {r} 0 0 0 {x} {y + r}"
    # Left edge back to start
    path += f" Z"

    return path

def generate_graph(allocators, arith_mean_ratios, normalized_sums, metadata, output_file, title_suffix=''):
    """Generate SVG bar chart comparing allocator performance."""

    # Calculate percentages (baseline = 100%)
    baseline_ratio = arith_mean_ratios.get('default', 1.0)
    percentages = [(arith_mean_ratios[a] / baseline_ratio) * 100 for a in allocators]

    # Get baseline absolute time for y-axis label
    baseline_time_ns = normalized_sums.get('default', 0)
    baseline_time_str = format_time(baseline_time_ns)

    # SVG dimensions and layout
    svg_width = 800
    svg_height = 450
    margin_left = 80
    margin_right = 40
    margin_top = 60
    margin_bottom = 100

    chart_width = svg_width - margin_left - margin_right
    chart_height = svg_height - margin_top - margin_bottom

    n_allocators = len(allocators)
    bar_spacing = chart_width / n_allocators
    bar_width = bar_spacing * 0.7
    corner_radius = 8

    # Y-axis scale
    max_pct = max(percentages)
    y_max = max(max_pct * 1.15, 115)

    # Build SVG
    svg_parts = []
    svg_parts.append('<?xml version="1.0" encoding="UTF-8"?>')

    # SVG header
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}">')

    # Background
    svg_parts.append(f'  <rect width="{svg_width}" height="{svg_height}" fill="white"/>')

    # Styles
    svg_parts.append('''  <style>
    .title { font-family: Arial, Helvetica, sans-serif; font-size: 18px; font-weight: bold; fill: #333333; }
    .axis-label { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #666666; }
    .tick-label { font-family: Arial, Helvetica, sans-serif; font-size: 11px; fill: #666666; }
    .bar-label-name { font-family: Arial, Helvetica, sans-serif; font-size: 12px; fill: #333333; }
    .bar-label-value { font-family: monospace; font-size: 11px; fill: #555555; }
    .bar-label-pct { font-family: Arial, Helvetica, sans-serif; font-size: 12px; font-weight: bold; fill: white; }
    .metadata { font-family: monospace; font-size: 10px; fill: #666666; }
    .grid-line { stroke: #cccccc; stroke-width: 0.5; }
  </style>''')

    # Title
    base_title = "Performance of rust/regex with different allocators"
    if title_suffix:
        title = f"{base_title}{title_suffix}"
    else:
        title = f"{base_title}—time (lower is better)"
    title_x = svg_width / 2
    title_y = 35
    svg_parts.append(f'  <text x="{title_x}" y="{title_y}" class="title" text-anchor="middle">{escape_xml(title)}</text>')

    # Y-axis label (rotated)
    y_label = f"Time vs Baseline (%, baseline = {baseline_time_str})"
    y_label_x = 20
    y_label_y = margin_top + chart_height / 2
    svg_parts.append(f'  <text x="{y_label_x}" y="{y_label_y}" class="axis-label" text-anchor="middle" transform="rotate(-90 {y_label_x} {y_label_y})">{escape_xml(y_label)}</text>')

    # Grid lines and Y-axis ticks
    y_ticks = [0, 20, 40, 60, 80, 100]
    if y_max > 100:
        y_ticks.append(int(y_max // 20 * 20))

    for tick in y_ticks:
        if tick > y_max:
            continue
        y_pos = margin_top + chart_height - (tick / y_max * chart_height)
        # Grid line
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y_pos}" x2="{margin_left + chart_width}" y2="{y_pos}" class="grid-line"/>')
        # Tick label
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y_pos + 4}" class="tick-label" text-anchor="end">{tick}</text>')

    # Bars
    for i, (allocator, pct) in enumerate(zip(allocators, percentages)):
        color = get_color(allocator)

        # Bar position
        bar_x = margin_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_height = (pct / y_max) * chart_height
        bar_y = margin_top + chart_height - bar_height

        # Draw bar with rounded top corners
        path = rounded_rect_path(bar_x, bar_y, bar_width, bar_height, corner_radius)
        svg_parts.append(f'  <path d="{path}" fill="{color}"/>')

        # Allocator name below bar
        name_x = bar_x + bar_width / 2
        name_y = margin_top + chart_height + 20
        svg_parts.append(f'  <text x="{name_x}" y="{name_y}" class="bar-label-name" text-anchor="middle">{escape_xml(allocator)}</text>')

        # Time value above bar
        time_label = format_time(normalized_sums[allocator])
        value_y = bar_y - 8
        svg_parts.append(f'  <text x="{name_x}" y="{value_y}" class="bar-label-value" text-anchor="middle">{escape_xml(time_label)}</text>')

        # Percentage inside bar (near top)
        if allocator == 'default':
            pct_label = "baseline"
        else:
            pct_label = format_pct_diff(arith_mean_ratios[allocator])
        pct_y = bar_y + 18
        # Only show if bar is tall enough
        if bar_height > 35:
            svg_parts.append(f'  <text x="{name_x}" y="{pct_y}" class="bar-label-pct" text-anchor="middle">{escape_xml(pct_label)}</text>')

    # Metadata
    meta_y = svg_height - 50

    meta_parts = []
    if metadata.get('timestamp'):
        meta_parts.append(f"Timestamp: {metadata['timestamp']}")

    if meta_parts:
        svg_parts.append(f'  <text x="{svg_width/2}" y="{meta_y}" class="metadata" text-anchor="middle">{escape_xml(" · ".join(meta_parts))}</text>\n')

    line2_parts = []
    if metadata.get('source'):
        line2_parts.append(f"Source: {metadata['source']}")
    if metadata.get('commit'):
        line2_parts.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        line2_parts.append(f"Git status: {metadata['git_status']}")

    if line2_parts:
        svg_parts.append(f'  <text x="{svg_width/2}" y="{meta_y + 15}" class="metadata" text-anchor="middle">{escape_xml(" · ".join(line2_parts))}</text>\n')

    line3_parts = []
    if metadata.get('cpu'):
        line3_parts.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        line3_parts.append(f"OS: {metadata['os']}")
    if metadata.get('cpucount'):
        line3_parts.append(f"CPU Count: {metadata['cpucount']}")

    if line3_parts:
        svg_parts.append(f'  <text x="{svg_width/2}" y="{meta_y + 30}" class="metadata" text-anchor="middle">{escape_xml(" · ".join(line3_parts))}</text>\n')

    svg_parts.append('</svg>')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_parts))

    print(f"\nGraph saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Analyze rebar benchmark results and generate comparison graphs')
    parser.add_argument('csv_file', help='CSV file from rebar measure')
    parser.add_argument('--timestamp', help='When the benchmarking process started')
    parser.add_argument('--source', help='Source URL')
    parser.add_argument('--commit', help='Git commit hash')
    parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
    parser.add_argument('--cpu', help='CPU type')
    parser.add_argument('--os', help='OS type')
    parser.add_argument('--cpucount', help='Number of CPUs')
    parser.add_argument('--graph', help='Output SVG graph to this file')
    parser.add_argument('--title-suffix', default='', help='Suffix to add to graph title')

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
    allocator_normalized_times = defaultdict(list)

    for test_name in valid_tests:
        results = test_data[test_name]
        baseline_time = results['default']
        iterations = 1e9 / baseline_time

        for allocator, time_ns in results.items():
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
            'timestamp': args.timestamp,
            'commit': args.commit,
            'git_status': args.git_status,
            'cpu': args.cpu,
            'os': args.os,
            'cpucount': args.cpucount,
            'source': args.source
        }
        generate_graph(sorted_allocators, arith_mean_ratios, normalized_sums, metadata, args.graph, args.title_suffix)

if __name__ == '__main__':
    main()
