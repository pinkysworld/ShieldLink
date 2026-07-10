# ShieldLink IJRC Publication Snapshot

This repository snapshot accompanies the IJRC article:

**ShieldLink: Retry-Aware Authenticated Encryption for Secure and Reliable Chiplet Interconnects**  
Michél Nguyen, *International Journal of Research in Computing*, Volume 5, Issue 2, 2026.

## Artifact contents

- `code/generate_assets.py`: regenerates the Gilbert-Elliott simulation sweeps, plots, analytic Mode B figures, and crossover tables.
- `code/formal_sanity_check.py`: runs the bounded safety sanity check for the ACK-gating invariant.
- `code/resource_estimator.py`: regenerates RTL/resource-sizing CSV values.
- `data/`: contains regenerated five-seed simulation CSVs, representative table values, targeted beta-sweep crossover values, and RTL sizing data.
- `figures/`: contains generated figures used by the manuscript and appendix.
- `rtl/`: contains synthesizable SystemVerilog skeletons for the ShieldLink control plane and baseline CRC+ARQ blocks.

## Reproduction

```bash
python code/generate_assets.py
python code/formal_sanity_check.py
python code/resource_estimator.py
```

## Scope and limitations

The RTL files are intended as synthesizable control-plane skeletons for independent evaluation and extension. They are not final post-place-and-route timing, power, or fmax results.

The formal exploration is a bounded safety sanity check of the ACK-gating invariant. It is not a complete liveness proof or exhaustive formal verification of all possible implementation schedules.

## Suggested GitHub release title

`ShieldLink IJRC publication snapshot`

## Suggested tag

`v1.0-ijrc-2026`
