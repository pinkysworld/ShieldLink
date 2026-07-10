#!/usr/bin/env bash
set -euo pipefail

OUT_DIR=${1:-synth/out}
mkdir -p "$OUT_DIR"

if ! command -v yosys >/dev/null 2>&1; then
  echo "ERROR: yosys not found. Install Yosys first, then rerun this script." >&2
  exit 127
fi

run_one() {
  local name="$1"
  local top="$2"
  shift 2
  local sources=("$@")
  local ys="$OUT_DIR/${name}.ys"
  local log="$OUT_DIR/${name}.log"

  {
    echo "read_verilog -sv ${sources[*]}"
    echo "hierarchy -check -top ${top}"
    echo "proc; opt; fsm; opt; memory; opt"
    echo "techmap; opt"
    echo "stat"
  } > "$ys"

  echo "[yosys] ${name} top=${top}"
  yosys -q -s "$ys" > "$log"
  grep -E "Number of cells:|Number of wires:|Number of wire bits:|Number of memories:|Number of memory bits:" "$log" > "$OUT_DIR/${name}.summary.txt" || true
}

run_one baseline_crc_arq top_fpga_baseline \
  rtl/baseline_ctrl_crc_arq.sv rtl/top_fpga_baseline.sv

run_one shieldlink_modeA top_fpga_shieldlink \
  rtl/shieldlink_ctrl_modeA.sv rtl/top_fpga_shieldlink.sv

run_one shieldlink_modeB_flush top_fpga_modeB_flush \
  rtl/shieldlink_ctrl_modeB.sv rtl/top_fpga_modeB_flush.sv

run_one shieldlink_modeB_selective_retry top_fpga_shieldlink_sr \
  rtl/shieldlink_ctrl_modeB_sr.sv rtl/top_fpga_shieldlink_sr.sv

python3 - <<'PY' "$OUT_DIR"/synthesis_summary.csv "$OUT_DIR"/*.summary.txt
import csv, re, sys, pathlib
out = pathlib.Path(sys.argv[1])
rows=[]
for p in map(pathlib.Path, sys.argv[2:]):
    text=p.read_text(errors='ignore') if p.exists() else ''
    row={'target': p.name.replace('.summary.txt','')}
    for label,key in [
        ('Number of wires:', 'wires'),
        ('Number of wire bits:', 'wire_bits'),
        ('Number of memories:', 'memories'),
        ('Number of memory bits:', 'memory_bits'),
        ('Number of cells:', 'cells'),
    ]:
        m=re.search(re.escape(label)+r'\s+(\d+)', text)
        row[key]=m.group(1) if m else ''
    rows.append(row)
with out.open('w', newline='') as f:
    w=csv.DictWriter(f, fieldnames=['target','wires','wire_bits','memories','memory_bits','cells'])
    w.writeheader(); w.writerows(rows)
print(f'Wrote {out}')
PY

echo "Synthesis logs and summaries are in $OUT_DIR"
