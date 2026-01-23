#!/bin/bash

BNAME="rebar"

# Collect metadata
GITCOMMIT="$(git log -1 | head -1 | cut -d' ' -f2)"
GITCLEANSTATUS=$( [ -z "$( git status --porcelain )" ] && echo \"Clean\" || echo \"Uncommitted changes\" )
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")

# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`
if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi
CPUTYPESTR="${CPUTYPE//[^[:alnum:]]/}"
OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"
ARGS=$*
CPUSTR_DOT_OSSTR="${CPUTYPESTR}.${OSTYPESTR}"
OUTPUT_DIR="${OUTPUT_DIR:-./benchmark-results}/${CPUSTR_DOT_OSSTR}"

RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

echo "# Saving result into \"${RESF}\""
echo "# Saving graph into \"${GRAPHF}\""
rm -f $RESF $GRAPHF
mkdir -p tmp

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


echo "# Results are in \"${RESF}\" ."
echo "# Graph is in \"${GRAPHF}\" ."
