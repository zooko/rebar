#!/bin/bash
set -e

BNAME="rebar"

# Collect metadata
GITCOMMIT=$(git rev-parse HEAD)
GITCLEANSTATUS=$([ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Uncommitted changes")
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Detect CPU type
# try Linux first
if command -v lscpu >/dev/null 2>&1; then
    CPUTYPE=$(lscpu 2>/dev/null | grep -i "model name" | cut -d':' -f2-)
elif command -v sysctl >/dev/null 2>&1; then
    # macOS
    CPUTYPE=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
fi
CPUTYPE=${CPUTYPE:-Unknown}
CPUTYPE=${CPUTYPE## }  # Trim leading space

CPUTYPESTR="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"

CPUCOUNT=$(nproc 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo "${NUMBER_OF_PROCESSORS:-unknown}")

ARGS=$*

CPUSTR_DOT_OSSTR="${CPUTYPESTR}.${OSTYPESTR}"
OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

# Output files
RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "GITCOMMIT: ${GITCOMMIT}" 2>&1 | tee -a $RESF
echo "GITCLEANSTATUS: ${GITCLEANSTATUS}" 2>&1 | tee -a $RESF
echo "CPUTYPE: ${CPUTYPE}" 2>&1 | tee -a $RESF
echo "OSTYPE: ${OSTYPE}" 2>&1 | tee -a $RESF
echo "CPUCOUNT: ${CPUCOUNT}" 2>&1 | tee -a $RESF

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
./sumstats.py "$CSVFILE" \
    --title-suffix "—compile benchmarks only" \
    --commit "$GITCOMMIT" \
    --git-status "$GITCLEANSTATUS" \
    --cpu "$CPUTYPE" \
    --os "$OSTYPESTR" \
    --cpucount "$CPUCOUNT" \
    --graph "$GRAPHF" \
    2>&1 | tee -a $RESF

echo | tee -a $RESF
cat $CSVFILE >> $RESF

echo "# Compile-only results are in \"${RESF}\" ."
echo "# Compile-only graph is in \"${GRAPHF}\" ."
