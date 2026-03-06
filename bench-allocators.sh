#!/bin/bash
set -e

source "$(dirname "$0")/gather-metadata.sh"

BNAME="rebar"

ARGS=$*

OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

# Output files
RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "TIMESTAMP: ${TIMESTAMP}" 2>&1 | tee -a $RESF
gather_and_print_git_metadata 2>&1 | tee -a $RESF
print_machine_metadata 2>&1 | tee -a $RESF

if [ "x${OSTYPE}" = "xmsys" ]; then
    # no jemalloc or snmalloc on windows
    ALLOCATORS="(mi|rp|s)malloc"
else
    ALLOCATORS="(je|sn|mi|rp|s)malloc"
fi

CSVFILE=tmp/res.csv

cargo build --locked --release
./target/release/rebar build -e "^rust/regex(-${ALLOCATORS})?$"

# Measure ONLY compile benchmarks by adding -m compile
./target/release/rebar measure -e "^rust/regex(-${ALLOCATORS})?$" -m compile -f curated ${ARGS} | tee $CSVFILE

# Rank compile benchmarks
echo "" | tee -a $RESF
echo "========================================" | tee -a $RESF
echo "COMPILE BENCHMARKS ONLY" | tee -a $RESF
echo "========================================" | tee -a $RESF
./target/release/rebar rank $CSVFILE 2>&1 | tee -a $RESF

# Generate graph for compile-only benchmarks
./sumstats.py "$CSVFILE" --graph "$GRAPHF" --title-suffix "—compile benchmarks only" "${METADATA_ARGS_TO_PASS_TO_PYTHON_SCRIPT[@]}" 2>&1 | tee -a $RESF

echo | tee -a $RESF
cat $CSVFILE >> $RESF

echo "# Compile-only results are in \"${RESF}\" ."
echo "# Compile-only graph is in \"${GRAPHF}\" ."
