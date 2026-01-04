echo CPU type:

# print out CPU type on macos
sysctl -n machdep.cpu.brand_string 2>/dev/null

# print out CPU type on linux
grep "model name" /proc/cpuinfo 2>/dev/null | uniq

cargo build --release
./target/release/rebar build -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$'
./target/release/rebar measure -e '^rust/regex(-(s|mi|sn|je|rp)malloc)?$' -f curated | tee res.csv
./target/release/rebar rank res.csv
