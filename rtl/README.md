# ShieldLink RTL / FPGA Teaser

This directory contains a minimal, synthesizable SystemVerilog control-plane prototype that makes
implementation costs of the Deliverability Invariant (D-Inv) explicit. It is intended to be synthesized
on a reader toolchain (Yosys+nextpnr or vendor tools).

## Files
- `shieldlink_ctrl_modeA.sv`: Mode A receiver control plane (D-Inv gating).
- `shieldlink_ctrl_modeB.sv`: Mode B receiver control plane (epoch buffer + flush-all baseline).
- `shieldlink_retry_buffer.sv`: Parameterized TX retry buffer.
- `baseline_ctrl_crc_arq.sv`: CRC+ARQ baseline (ACK on CRC only).
- `top_fpga_baseline.sv`: Synthesis top for baseline.
- `top_fpga_shieldlink.sv`: Synthesis top for ShieldLink Mode A.

## Synthesis hint
If you have Yosys installed:
```
yosys -p "read_verilog -sv *.sv; synth -top top_fpga_shieldlink"
```

Reference parameters used in the paper: payload=256 B, header=16 B, CRC=4 B, tag=12 B, N_win=64, M=32.
