# ShieldLink IJRC Supplementary Materials

This bundle accompanies the IJRC manuscript **ShieldLink: Retry-Aware Authenticated Encryption for Secure and Reliable Chiplet Interconnects**.

## Contents

- `code/generate_assets.py` regenerates the Gilbert-Elliott simulation sweeps, plots, analytic Mode B figures, and crossover tables. The revised artifact uses five Monte Carlo seeds (`seeds = range(5)`) for the main sweep.
- `code/resource_estimator.py` regenerates the RTL/resource-sizing CSV values.
- `code/formal_sanity_check.py` runs the bounded safety sanity check for the ACK-gating invariant. It is a bounded safety check only, not a liveness proof or full formal verification.
- `data/` contains the regenerated five-seed simulation CSVs, representative Table 3 values, targeted beta-sweep crossover table, and RTL sizing data.
- `figures/` contains the regenerated figures used by the revised manuscript and appendix.
- `rtl/` contains the SystemVerilog RTL skeleton for the ShieldLink control plane and baseline blocks.

## Reproduction notes

Python dependencies used by `generate_assets.py` include `numpy`, `pandas`, and `matplotlib`. Graphviz is required for the architecture/FSM diagrams. The simulator uses an effective frame-corruption Gilbert-Elliott model with `p_good = 1e-6`, `p_bad = 0.1`, and default `beta = 0.2` unless otherwise specified.

```bash
python code/generate_assets.py
python code/formal_sanity_check.py
python code/resource_estimator.py
```

## Scope

The RTL files are synthesizable skeleton/control-plane artifacts intended for independent evaluation and extension. They are not post-place-and-route timing or power results.
