#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import csv
import argparse
import math
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument('csv_file', help='CSV file from rebar measure output')
parser.add_argument('--commit', help='Git commit hash')
parser.add_argument('--git-status', help='Git status (Clean or Uncommitted changes)')
parser.add_argument('--cpu', help='CPU type')
parser.add_argument('--os', help='OS type')
parser.add_argument('--graph', help='Output SVG graph to this file')
args = parser.parse_args()

# Hardcoded allocator ordering
ALLOCATOR_ORDER = ['jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc']

def parse_time(time_str):
    """Parse a time string like '24.67us' or '1.42ms' and return nanoseconds."""
    if not time_str:
        return None

    # Handle values that already look like floats
    try:
        return float(time_str)
    except ValueError:
        pass

    # Parse formatted times
    import re
    match = re.match(r'([\d.]+)(ns|us|ms|s)', time_str)
    if not match:
        raise ValueError(f"Cannot parse time: {time_str}")

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {
        'ns': 1,
        'us': 1_000,
        'ms': 1_000_000,
        's': 1_000_000_000,
    }

    return value * multipliers[unit]

def get_allocator_name(engine_name):
    """Extract allocator name from engine name."""
    if engine_name == 'rust/regex':
        return 'default'
    elif '-' in engine_name:
        return engine_name.split('-')[-1]
    return 'unknown'

def sort_allocators(allocators):
    """Sort allocators: default first, then ALLOCATOR_ORDER, then unknown, then smalloc last."""
    def sort_key(name):
        if name == 'default':
            return (0, 0, name)
        elif name == 'smalloc':
            return (3, 0, name)
        elif name in ALLOCATOR_ORDER:
            return (1, ALLOCATOR_ORDER.index(name), name)
        else:
            return (2, 0, name)

    return sorted(allocators, key=sort_key)

def generate_svg_graph(allocator_stats, sorted_allocators, metadata, output_file):
    """Generate an SVG bar chart comparing allocator performance."""

    # Graph dimensions
    width = 800
    height = 500
    margin_top = 60
    margin_bottom = 100
    margin_left = 80
    margin_right = 40

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    # Calculate percentages (baseline = 100%, others relative)
    percentages = []
    for allocator in sorted_allocators:
        if allocator == 'default':
            percentages.append(100.0)
        else:
            # Convert ratio to percentage: 1.03 -> 103%
            pct = allocator_stats[allocator]['ratio'] * 100
            percentages.append(pct)

    # Find max for scaling
    max_pct = max(percentages)
    scale_max = max(max_pct * 1.1, 120)  # At least 120% for scale

    # Calculate bar properties
    bar_width = chart_width / len(sorted_allocators)
    padding = bar_width * 0.2
    actual_bar_width = bar_width - padding

    # Color scheme
    colors = ['#4285f4', '#ea4335', '#fbbc04', '#34a853', '#9333ea', '#ff6b9d', '#00bcd4']

    svg_parts = []
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
  <style>
    .bar {{ stroke: none; }}
    .axis {{ stroke: #333; stroke-width: 1; }}
    .grid {{ stroke: #ddd; stroke-width: 0.5; }}
    .label {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 12px; fill: #333; }}
    .value {{ font-family: monospace; font-size: 11px; fill: #999; }}
    .title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 16px; font-weight: 600; fill: #333; }}
    .metadata {{ font-family: monospace; font-size: 10px; fill: #666; }}
  </style>
''')

    # Title
    svg_parts.append(f'  <text x="{width/2}" y="30" class="title" text-anchor="middle">rust/regex Performance with Different Allocators (lower is better)</text>\n')

    # Y-axis
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + chart_height}" class="axis"/>\n')
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>\n')

    # Grid lines and labels (every 20% from 0% to 120%+)
    for pct in [0, 20, 40, 60, 80, 100, 120]:
        if pct > scale_max:
            break
        y = margin_top + chart_height * (1 - pct/scale_max)
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" class="grid"/>\n')
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y + 4}" class="label" text-anchor="end">{pct:.0f}%</text>\n')

    # Bars and labels
    for i, allocator in enumerate(sorted_allocators):
        pct = percentages[i]
        x = margin_left + i * bar_width + padding/2
        bar_height = (pct / scale_max) * chart_height
        y = margin_top + chart_height - bar_height

        color = colors[i % len(colors)]

        # Bar
        svg_parts.append(f'  <rect x="{x}" y="{y}" width="{actual_bar_width}" height="{bar_height}" class="bar" fill="{color}"/>\n')

        # Value above bar
        if allocator == 'default':
            label = "100% (baseline)"
        else:
            delta = round(pct - 100)
            label = f"{delta:+d}%"

        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{y - 5}" class="value" text-anchor="middle">{label}</text>\n')

        # Allocator name below
        text_y = margin_top + chart_height + 20
        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{text_y}" class="label" text-anchor="middle">{allocator}</text>\n')

    # Metadata below the graph
    metadata_y = margin_top + chart_height + 50
    metadata_lines = []

    metadata_lines.append("Source: https://github.com/zooko/rebar")
    if metadata.get('commit'):
        metadata_lines.append(f"Commit: {metadata['commit'][:12]}")
    if metadata.get('git_status'):
        metadata_lines.append(f"Git status: {metadata['git_status']}")
    if metadata.get('cpu'):
        metadata_lines.append(f"CPU: {metadata['cpu']}")
    if metadata.get('os'):
        metadata_lines.append(f"OS: {metadata['os']}")

    for i, line in enumerate(metadata_lines):
        y = metadata_y + i * 15
        svg_parts.append(f'  <text x="{width/2}" y="{y}" class="metadata" text-anchor="middle">{line}</text>\n')

    svg_parts.append('</svg>')

    with open(output_file, 'w') as f:
        f.write(''.join(svg_parts))

    print(f"\n📊 Graph saved to: {output_file}")

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

# Calculate normalized time differences for each allocator
allocator_deltas = defaultdict(list)

for test_name, results in test_data.items():
    if 'default' not in results:
        continue

    baseline_time = results['default']

    for allocator, time in results.items():
        if allocator == 'default':
            continue

        # Calculate percentage difference
        delta = (time - baseline_time) / baseline_time

        allocator_deltas[allocator].append(delta)

# Calculate geometric mean of deltas for each allocator
allocator_stats = {}

for allocator, deltas in allocator_deltas.items():
    if not deltas:
        continue

    # Geometric mean of (1 + delta) values, then subtract 1
    product = 1.0
    for delta in deltas:
        product *= (1.0 + delta)

    geo_mean_ratio = product ** (1.0 / len(deltas))
    geo_mean_delta = geo_mean_ratio - 1.0

    allocator_stats[allocator] = {
        'delta': geo_mean_delta,
        'ratio': geo_mean_ratio,
        'test_count': len(deltas)
    }

# Add default (baseline) stats
allocator_stats['default'] = {
    'delta': 0.0,
    'ratio': 1.0,
    'test_count': len(test_data)
}

# Sort allocators
sorted_allocators = ['default'] + sort_allocators([a for a in allocator_stats.keys() if a != 'default'])

# Print results
print(f"{'Allocator':<12} {'Geo Mean Ratio':>16} {'Geo Mean Delta':>16} {'Test Count':>12}")
print("-" * 60)

for allocator in sorted_allocators:
    stats = allocator_stats[allocator]
    ratio = stats['ratio']
    delta = stats['delta'] * 100  # Convert to percentage
    count = stats['test_count']

    print(f"{allocator:<12} {ratio:>16.4f} {delta:>+15.2f}% {count:>12}")

print()
print("Interpretation:")
print("- Geo Mean Ratio: If baseline takes 1.0s, candidate takes this many seconds (geometric mean)")
print("- Geo Mean Delta: Percentage difference from baseline (geometric mean)")
print("- Lower ratios/deltas are better (less overhead)")

# Generate graph if requested
if args.graph:
    metadata = {
        'commit': args.commit,
        'git_status': args.git_status,
        'cpu': args.cpu,
        'os': args.os
    }
    generate_svg_graph(allocator_stats, sorted_allocators, metadata, args.graph)
