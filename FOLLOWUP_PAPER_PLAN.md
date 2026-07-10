# Follow-up paper plan: ShieldLink-SR

Working title:

**ShieldLink-SR: Selective-Retry Epoch Authentication for Low-Latency Secure Chiplet Interconnects**

## Motivation

The IJRC ShieldLink paper defines the deliverability invariant and evaluates Mode A and Mode B. Mode B improves wire efficiency by amortizing authentication across an epoch, but the accepted paper intentionally uses a conservative flush-all retransmission policy: if any frame in the epoch fails CRC, the entire epoch is retransmitted. This makes the Mode B goodput and p99 latency sensitive to burst errors.

## New contribution

ShieldLink-SR replaces Mode B's flush-all recovery with bitmap selective retry. The receiver retains CRC-clean epoch slots and emits a bitmap NAK requesting only missing or CRC-failed slots. The epoch is committed only after all slots are present, all CRC failures have been repaired, and the epoch AEAD tag verifies.

The security invariant is unchanged:

```text
commit(epoch) iff all frames are present AND no CRC failures remain AND epoch AEAD verifies
```

Thus, selective retry improves reliability efficiency without turning CRC success into authenticated delivery.

## Artifact additions in this branch

- `rtl/shieldlink_ctrl_modeB_sr.sv`: synthesizable control-plane skeleton for selective-retry epoch authentication.
- `rtl/top_fpga_shieldlink_sr.sv`: synthesis top for Mode B-SR.
- `rtl/top_fpga_modeB_flush.sv`: synthesis top for the original Mode B flush-all baseline.
- `code/sim_selective_retry_followup.py`: Monte Carlo follow-up simulator comparing CRC+ARQ, Mode A, Mode B flush-all, and Mode B-SR.
- `data/selective_retry_followup_results.csv`: generated five-seed simulation results.
- `code/resource_estimator_selective_retry.py`: analytic resource-sizing helper for Mode B-SR.
- `data/modeB_sr_resource_sizing.csv`: generated structural sizing data.
- `synth/run_yosys_synthesis.sh`: open-flow Yosys synthesis helper.
- `.github/workflows/yosys-synthesis.yml`: manual/PR-triggered Yosys workflow.

## Preliminary result pattern

The preliminary follow-up simulation indicates that Mode B-SR preserves most of Mode B's low-overhead wire efficiency while avoiding the flush-all goodput cliff. Under the same Gilbert-Elliott-style stress model used for the first paper, Mode B-SR remains above Mode A in normalized goodput at the tested bad-state probabilities, while p99 epoch-commit latency stays close to one epoch plus a small number of repair frames instead of full epoch replay.

These are preliminary model results, not final paper claims. The next step is to run Yosys and, ideally, vendor FPGA synthesis to quantify the control-plane cost of the bitmap NAK path.

## Proposed paper outline

1. Introduction: why epoch authentication needs selective repair.
2. Background: ShieldLink D-Inv, Mode A, Mode B, and the flush-all limitation.
3. ShieldLink-SR design: bitmap NAKs, retained clean slots, repair rounds, commit rules, security drops.
4. Safety argument: selective retry preserves authenticated deliverability.
5. Evaluation model: Gilbert-Elliott burst errors, five-seed sweeps, latency and goodput metrics.
6. RTL and synthesis: baseline, Mode A, Mode B flush-all, Mode B-SR.
7. Results: goodput, p99 latency, buffer pressure, FF/LUT/memory summaries.
8. Discussion: adaptive epoch size, failure telemetry, DoS/reset policy, multi-hop chiplet fabrics.
9. Conclusion.
