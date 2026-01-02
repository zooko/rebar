#!/opt/homebrew/bin/pypy3
"""
Add regex allocator variants to rebar benchmark TOML files.

Usage: python add_regex_variants.py benchmarks/definitions/test/func/*.toml
"""

import sys
import tomlkit

VARIANTS = [
    "rust/regex-mimalloc",
    "rust/regex-jemalloc",
    "rust/regex-smalloc",
    "rust/regex-rpmalloc",
    "rust/regex-snmalloc",
]

def process_engines_array(engines):
    """Add variants to an engines array if rust/regex is present."""
    if 'rust/regex' not in engines:
        return False

    modified = False
    idx = list(engines).index('rust/regex') + 1

    for variant in reversed(VARIANTS):
        if variant not in engines:
            engines.insert(idx, variant)
            modified = True

    return modified

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    data = tomlkit.parse(content)
    modified = False

    # Handle top-level engines array
    if 'engines' in data:
        if process_engines_array(data['engines']):
            modified = True

    # Handle [[bench]] sections
    if 'bench' in data:
        for bench in data['bench']:
            if 'engines' in bench:
                if process_engines_array(bench['engines']):
                    modified = True

    if modified:
        with open(filepath, 'w') as f:
            f.write(tomlkit.dumps(data))
        print(f"Updated: {filepath}")
    else:
        print(f"No changes: {filepath}")

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.toml> [file2.toml ...]")
        sys.exit(1)

    for filepath in sys.argv[1:]:
        try:
            process_file(filepath)
        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
