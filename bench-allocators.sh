#!/bin/bash

set -e

BNAME="rebar"

# Collect metadata
GITCOMMIT=$(git rev-parse HEAD)
GITCLEANSTATUS=$( [ -z "$( git status --porcelain )" ] && echo \"Clean\" || echo \"Uncommitted changes\" )
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# CPU type on linuxy
CPUTYPE=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d':' -f2-)
if [ -z "${CPUTYPE}" ] ; then
    # CPU type on macos
    CPUTYPE=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
fi
CPUTYPESTR="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"
ARGS=$*
CPUSTR_DOT_OSSTR="${CPUTYPESTR}.${OSTYPESTR}"
OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
rm -f $RESF $GRAPHF
mkdir -p tmp

echo "GITCOMMIT: ${GITCOMMIT}" 2>&1 | tee -a $RESF
echo "GITCLEANSTATUS: ${GITCLEANSTATUS}" 2>&1 | tee -a $RESF
echo "CPUTYPE: ${CPUTYPE}" 2>&1 | tee -a $RESF
echo "OSTYPE: ${OSTYPE}" 2>&1 | tee -a $RESF

if [ "x${OSTYPE}" = "xmsys" ]; then
    # no jemalloc or snmalloc on windows
    ALLOCATORS="(mi|rp|s)malloc"
else
    ALLOCATORS="(je|sn|mi|rp|s)malloc"
fi

CSVFILE=tmp/res.csv

cargo build --locked --release
./target/release/rebar build -e "^rust/regex(-${ALLOCATORS})?$"
./target/release/rebar measure -e "^rust/regex(-${ALLOCATORS})?$" -f curated ${ARGS} | tee tmp/res.csv
./target/release/rebar rank $CSVFILE 2>&1 | tee -a $RESF

# Generate comparison with metadata passed as arguments
./sumstats.py "$CSVFILE" \
    --commit "$GITCOMMIT" \
    --git-status "$GITCLEANSTATUS" \
    --cpu "$CPUTYPE" \
    --os "$OSTYPESTR" \
    --graph "$GRAPHF" \
    2>&1 | tee -a $RESF


echo "# Data results (text) are in \"${RESF}\" ."
echo "# Graph is in \"${GRAPHF}\" ."
