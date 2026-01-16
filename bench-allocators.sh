# CPU type on linuxy
CPUTYPE=`grep "model name" /proc/cpuinfo 2>/dev/null | uniq | cut -d':' -f2-`

if [ "x${CPUTYPE}" = "x" ] ; then
    # CPU type on macos
    CPUTYPE=`sysctl -n machdep.cpu.brand_string 2>/dev/null`
fi

CPUTYPE="${CPUTYPE//[^[:alnum:]]/}"

OSTYPESTR="${OSTYPE//[^[:alnum:]]/}"

RESF=rebar.bench-allocators.result.${CPUTYPE}.${OSTYPESTR}.txt

echo "# Saving result into a file named \"${RESF}\" ..."

rm -f $RESF

echo "# git log -1 | head -1" 2>&1 | tee -a $RESF
git log -1 | head -1 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

echo CPU type: 2>&1 | tee -a $RESF
echo $CPUTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

echo OS type: 2>&1 | tee -a $RESF
echo $OSTYPE 2>&1 | tee -a $RESF
echo 2>&1 | tee -a $RESF

cargo build --locked --release
./target/release/rebar build -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$'
./target/release/rebar measure -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$' -f curated | tee res.csv
./target/release/rebar rank res.csv 2>&1 | tee -a $RESF
