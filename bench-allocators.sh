# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`

if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi

CPUTYPE="${CPUTYPE//[^[:alnum:]]/}"

OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"

ARGS=$*
ARGSSTR="${ARGS//[^[:alnum:]]/}"

BNAME="rebar.bench-allocators"
FNAME="${BNAME}.result.${CPUTYPE}.${OSTYPESTR}.${ARGSSTR}.txt"
TMPF="tmp/${FNAME}"
RESF="${FNAME}"

echo "# Saving result into a tmp file (in ./tmp) which will be moved to \"${RESF}\" when complete..."

rm -f $TMPF
mkdir -p tmp

echo "# git log -1 | head -1" 2>&1 | tee -a $TMPF
git log -1 | head -1 2>&1 | tee -a $TMPF
echo 2>&1 | tee -a $TMPF

echo "( [ -z \"\$(git status --porcelain)\" ] && echo \"Clean\" || echo \"Uncommitted changes\" )" 2>&1 | tee -a $TMPF
( [ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Uncommitted changes" ) 2>&1 | tee -a $TMPF
echo 2>&1 | tee -a $TMPF

echo CPU type: 2>&1 | tee -a $TMPF
echo $CPUTYPE 2>&1 | tee -a $TMPF
echo 2>&1 | tee -a $TMPF

echo OS type: 2>&1 | tee -a $TMPF
echo $OSTYPE 2>&1 | tee -a $TMPF
echo 2>&1 | tee -a $TMPF

cargo build --locked --release
./target/release/rebar build -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$'
./target/release/rebar measure -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$' -f curated ${ARGS} | tee tmp/res.csv
./target/release/rebar rank tmp/res.csv 2>&1 | tee -a $TMPF

mv -f "${TMPF}" "${RESF}"
