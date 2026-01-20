#!/usr/bin/env python3
# Thanks to Claude (Opus 4.5 & Sonnet 4.5) for writing this to my specifications.

import sys
import re
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('result_file', help='Result file from rebar bench-allocators.sh')
parser.add_argument('--graph', help='Output SVG graph to this file')
args = parser.parse_args()

# Hardcoded allocator ordering (excluding 'default' which is always first and 'smalloc' which is always last)
ALLOCATOR_ORDER = ['jemalloc', 'snmalloc', 'mimalloc', 'rpmalloc']

def parse_rebar_result(filename):
    """Parse rebar bench-allocators.sh output and return metadata + engine data."""
    metadata = {}
    engines = []

    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Parse metadata
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('commit '):
            metadata['commit'] = line.split()[1]
        elif line in ['Clean', 'Uncommitted changes']:
            metadata['git_status'] = line
        elif i > 0 and lines[i-1].strip() == 'CPU type:':
            metadata['cpu'] = line
        elif i > 0 and lines[i-1].strip() == 'OS type:':
            metadata['os'] = line

    # Find the table section
    table_started = False
    for line in lines:
        line = line.strip()

        # Skip header lines
        if line.startswith('Engine') or line.startswith('---'):
            table_started = True
            continue

        if table_started and line:
            # Parse: "rust/regex-snmalloc 1.12.2 1.01 52"
            parts = line.split()
            if len(parts) >= 3:
                engine_name = parts[0]
                version = parts[1]
                geo_mean = float(parts[2])

                # Extract allocator name from engine name (e.g., "rust/regex-snmalloc" -> "snmalloc")
                allocator = 'default'
                if '-' in engine_name:
                    allocator = engine_name.split('-')[-1]
                elif 'rust/regex' == engine_name:
                    allocator = 'default'

                engines.append({
                    'name': engine_name,
                    'allocator': allocator,
                    'version': version,
                    'geo_mean': geo_mean
                })

    return metadata, engines

def sort_engines(engines):
    """Sort engines: default first, then ALLOCATOR_ORDER, then unknown, then smalloc last."""
    def sort_key(engine):
        name = engine['allocator']
        if name == 'default':
            return (0, 0, name)
        elif name == 'smalloc':
            return (3, 0, name)
        elif name in ALLOCATOR_ORDER:
            return (1, ALLOCATOR_ORDER.index(name), name)
        else:
            # Unknown allocators go between known and smalloc
            return (2, 0, name)

    return sorted(engines, key=sort_key)

def generate_svg_graph(engines, metadata, output_file):
    """Generate an SVG bar chart comparing allocator performance."""

    # Graph dimensions
    width = 800
    height = 500
    margin_top = 60
    margin_bottom = 120  # Space for metadata below
    margin_left = 80
    margin_right = 40

    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    # Calculate percentages (baseline = 100%, others relative to baseline)
    baseline_geo_mean = engines[0]['geo_mean']
    percentages = [(e['geo_mean'] / baseline_geo_mean * 100) for e in engines]

    # Find max for scaling
    max_pct = max(percentages)
    scale_max = max_pct * 1.1  # 10% padding at top

    # Calculate bar properties
    bar_width = chart_width / len(engines)
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
    svg_parts.append(f'  <text x="{width/2}" y="30" class="title" text-anchor="middle">Performance of rust/regex with different allocators—time (lower is better)</text>\n')

    # Y-axis
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + chart_height}" class="axis"/>\n')
    svg_parts.append(f'  <line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>\n')

    # Grid lines and labels (every 20% from 0% to 120%)
    for pct in [0, 20, 40, 60, 80, 100, 120]:
        if pct > scale_max:
            break
        y = margin_top + chart_height * (1 - pct/scale_max)
        svg_parts.append(f'  <line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" class="grid"/>\n')
        svg_parts.append(f'  <text x="{margin_left - 10}" y="{y + 4}" class="label" text-anchor="end">{pct:.0f}%</text>\n')

    # Bars and labels
    for i, (engine, pct) in enumerate(zip(engines, percentages)):
        x = margin_left + i * bar_width + padding/2
        bar_height = (pct / scale_max) * chart_height
        y = margin_top + chart_height - bar_height

        color = colors[i % len(colors)]

        # Bar
        svg_parts.append(f'  <rect x="{x}" y="{y}" width="{actual_bar_width}" height="{bar_height}" class="bar" fill="{color}"/>\n')

        # Value above bar (delta percentage rounded to whole number)
        if i == 0:
            label = "100% (baseline)"
        else:
            delta = round(pct - 100)
            label = f"{pct:.0f}%"
        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{y - 5}" class="value" text-anchor="middle">{label}</text>\n')

        # Allocator name below
        text_y = margin_top + chart_height + 20
        allocator_name = engine['allocator']
        svg_parts.append(f'  <text x="{x + actual_bar_width/2}" y="{text_y}" class="label" text-anchor="middle">{allocator_name}</text>\n')

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

# Parse the result file
metadata, engines = parse_rebar_result(args.result_file)

# Sort engines by allocator order
engines = sort_engines(engines)

# Extract column names
col_names = [e['allocator'] for e in engines]
geo_means = [e['geo_mean'] for e in engines]

assert len(geo_means) > 0, (engines, args.result_file)

# Calculate percentages
baseline_geo_mean = geo_means[0]
percentages = [(g / baseline_geo_mean * 100) for g in geo_means]

# Print table
max_name_len = max(len(e['name']) for e in engines)
max_alloc_len = max(len(e['allocator']) for e in engines)

print(f"{'Allocator':<{max_alloc_len}}  {'Engine':<{max_name_len}}  {'Geo Mean':>10}  {'Relative':>10}")
print("-" * (max_alloc_len + max_name_len + 26))

for i, engine in enumerate(engines):
    if i == 0:
        relative = "baseline"
    else:
        delta = round(percentages[i] - 100)
        relative = f"{delta:+d}%"

    print(f"{engine['allocator']:<{max_alloc_len}}  {engine['name']:<{max_name_len}}  {engine['geo_mean']:>10.2f}  {relative:>10}")

# Generate graph if requested
if args.graph:
    generate_svg_graph(engines, metadata, args.graph)
