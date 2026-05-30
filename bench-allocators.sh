#!/bin/bash
set -e

source "$(dirname "$0")/tools.sh"

BNAME="rebar"

# Output files
RESF="${OUTPUT_DIR}/${BNAME}.result.txt"
GRAPHF="${OUTPUT_DIR}/${BNAME}.graph.svg"

mkdir -p ${OUTPUT_DIR}
mkdir -p tmp
rm -f $RESF $GRAPHF

echo "TIMESTAMP: ${TIMESTAMP}" 2>&1 | tee -a $RESF
gather_and_print_git_metadata 2>&1 | tee -a $RESF
print_machine_metadata 2>&1 | tee -a $RESF

allocator_regex() {
    local out=""
    local a short

    for a in "$@"; do
        case "$a" in
            jemalloc)  short="je" ;;
            snmalloc)  short="sn" ;;
            mimalloc)  short="mi" ;;
            rpmalloc)  short="rp" ;;
            smalloc)   short="s"  ;;
            *)         short="$a" ;;
        esac

        if [ -z "$out" ]; then
            out="$short"
        else
            out="$out|$short"
        fi
    done

    printf '(%s)malloc\n' "$out"
}

ALLOCATOR_LIST+=("smalloc")
ALLOCATOR_REGEX="$(allocator_regex "${ALLOCATOR_LIST[@]}")"

CSVFILE=tmp/res.csv

cargo "${CARGO_CONFIG_ARGS[@]}" build --offline --release 
./target/release/rebar build -e "^rust/regex(-${ALLOCATOR_REGEX})?$" -- "${CARGO_CONFIG_ARGS[@]}"

# Measure ONLY compile benchmarks by adding -m compile
./target/release/rebar measure -e "^rust/regex(-${ALLOCATOR_REGEX})?$" -m compile -f curated ${*} -- "${CARGO_CONFIG_ARGS[@]}" | tee $CSVFILE

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
