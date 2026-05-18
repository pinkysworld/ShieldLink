import math
import random
import heapq
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

OUT_DIR = Path('/mnt/data/shieldlink_bundle')
FIG_DIR = OUT_DIR / 'figures'
DATA_DIR = OUT_DIR / 'data'
CODE_DIR = OUT_DIR / 'code'

for d in [FIG_DIR, DATA_DIR, CODE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class GEParams:
    p_good: float
    p_bad: float
    alpha: float  # G->B
    beta: float   # B->G
    init_state: str = 'G'


@dataclass
class LinkParams:
    W_link: int  # bytes per cycle
    d_prop: int
    d_crc: int
    d_aead: int
    d_ctrl: int = 1
    N_win: int = 64
    payload_bytes: int = 256


@dataclass
class Scheme:
    name: str
    frame_bytes: int
    aead_delay: int
    ack_on_crc_only: bool = False
    epoch_size: Optional[int] = None
    epoch_tag_bytes: int = 12
    epoch_verify_delay: Optional[int] = None


def mean_ci95(vals: List[float]) -> Tuple[float, float]:
    arr = np.array(vals, dtype=float)
    mean = float(arr.mean())
    if len(arr) < 2:
        return mean, 0.0
    sem = float(arr.std(ddof=1) / math.sqrt(len(arr)))
    return mean, 1.96 * sem


def simulate_link(num_frames: int, scheme: Scheme, link: LinkParams, ge: GEParams, seed: int = 0) -> Dict:
    """Discrete-event simulation.

    - Mode A-like: per-frame ACK after (CRC + optional AEAD delay).
    - Mode B: epoch-based commit. Receiver may buffer up to K epochs where
      K = ceil(N_win/M). ACKs are only sent at epoch boundaries when an
      epoch is verified and committed. On any CRC error in buffered region,
      receiver flushes buffered epochs and sends NAK for next_expected.

    Time unit: cycles.
    """
    rng = random.Random(seed)

    # Sender state
    base = 0
    next_seq = 0
    plan_id = 0

    # Receiver state
    next_expected = 0
    nak_outstanding = False

    # Mode B receiver buffering
    M = scheme.epoch_size
    if M is not None:
        if num_frames % M != 0:
            raise ValueError('For Mode B, num_frames must be a multiple of M in this simplified model.')
        K = math.ceil(link.N_win / M)
        buf_counts = [0] * K
        verified = [False] * K
        verify_scheduled = [False] * K
        rx_gen = 0

    # Stats
    first_tx_time: Dict[int, int] = {}
    delivered_time: Dict[int, int] = {}
    epoch_latency_samples: List[float] = []

    total_tx_frames = 0
    total_tx_bytes = 0
    last_tx_end_time = 0

    # Channel state
    ch_state = ge.init_state

    # Event heap: (time, eid, type, data)
    heap: List[Tuple[int, int, str, dict]] = []
    eid_counter = 0

    def push_event(t: int, typ: str, data: dict):
        nonlocal eid_counter
        heapq.heappush(heap, (t, eid_counter, typ, data))
        eid_counter += 1

    # Sender TX_READY chain tracking
    tx_chain_active = True
    push_event(0, 'TX_READY', {'plan': plan_id})

    def channel_corrupt_and_advance() -> bool:
        nonlocal ch_state
        p = ge.p_good if ch_state == 'G' else ge.p_bad
        corrupt = rng.random() < p
        if ch_state == 'G':
            if rng.random() < ge.alpha:
                ch_state = 'B'
        else:
            if rng.random() < ge.beta:
                ch_state = 'G'
        return corrupt

    def modeb_try_commit(time_now: int):
        """Commit as many verified+complete epochs from the head as possible."""
        nonlocal next_expected, buf_counts, verified, verify_scheduled, nak_outstanding
        while buf_counts[0] == M and verified[0]:
            epoch_start = next_expected
            epoch_latency_samples.append(time_now - first_tx_time[epoch_start])
            for s in range(epoch_start, epoch_start + M):
                delivered_time[s] = time_now
            next_expected += M
            buf_counts = buf_counts[1:] + [0]
            verified = verified[1:] + [False]
            verify_scheduled = verify_scheduled[1:] + [False]
            nak_outstanding = False
            push_event(time_now + link.d_ctrl + link.d_prop, 'ACK_ARRIVE', {'ack_next': next_expected})

    while heap:
        time, _, typ, data = heapq.heappop(heap)

        if typ == 'TX_READY':
            if data.get('plan') != plan_id:
                continue
            if next_seq < num_frames and next_seq < base + link.N_win:
                seq = next_seq
                next_seq += 1
                if seq not in first_tx_time:
                    first_tx_time[seq] = time

                fb = scheme.frame_bytes
                if M is not None and (seq % M) == (M - 1):
                    fb = scheme.frame_bytes + scheme.epoch_tag_bytes

                tx_cycles = math.ceil(fb / link.W_link)
                tx_end = time + tx_cycles
                last_tx_end_time = max(last_tx_end_time, tx_end)

                total_tx_frames += 1
                total_tx_bytes += fb

                corrupt = channel_corrupt_and_advance()
                push_event(tx_end + link.d_prop, 'RX_ARRIVE', {'seq': seq, 'crc_ok': not corrupt})
                push_event(tx_end, 'TX_READY', {'plan': plan_id})
                tx_chain_active = True
            else:
                tx_chain_active = False

        elif typ == 'RX_ARRIVE':
            # CRC completes after fixed latency
            push_event(time + link.d_crc, 'RX_DECIDE', data)

        elif typ == 'RX_DECIDE':
            seq = data['seq']
            crc_ok = data['crc_ok']

            # If the expected seq is seen again, clear NAK suppression to avoid deadlock
            if nak_outstanding and seq == next_expected:
                nak_outstanding = False

            if M is None:
                # Mode A-like
                if not crc_ok:
                    if seq == next_expected and (not nak_outstanding):
                        push_event(time + link.d_ctrl + link.d_prop, 'NAK_ARRIVE', {'nack_seq': next_expected})
                        nak_outstanding = True
                else:
                    deliver_time = time if scheme.ack_on_crc_only else (time + scheme.aead_delay)
                    push_event(deliver_time, 'RX_DELIVER', {'seq': seq})

            else:
                # Mode B
                if not crc_ok:
                    buf_counts = [0] * K
                    verified = [False] * K
                    verify_scheduled = [False] * K
                    rx_gen += 1
                    if not nak_outstanding:
                        push_event(time + link.d_ctrl + link.d_prop, 'NAK_ARRIVE', {'nack_seq': next_expected})
                        nak_outstanding = True
                else:
                    buffered_total = sum(buf_counts)
                    expected_seq = next_expected + buffered_total
                    if seq != expected_seq:
                        buf_counts = [0] * K
                        verified = [False] * K
                        verify_scheduled = [False] * K
                        rx_gen += 1
                        if not nak_outstanding:
                            push_event(time + link.d_ctrl + link.d_prop, 'NAK_ARRIVE', {'nack_seq': next_expected})
                            nak_outstanding = True
                    else:
                        epoch_index = (seq - next_expected) // M
                        if epoch_index >= K:
                            buf_counts = [0] * K
                            verified = [False] * K
                            verify_scheduled = [False] * K
                            rx_gen += 1
                            if not nak_outstanding:
                                push_event(time + link.d_ctrl + link.d_prop, 'NAK_ARRIVE', {'nack_seq': next_expected})
                                nak_outstanding = True
                        else:
                            buf_counts[epoch_index] += 1
                            if buf_counts[epoch_index] == M and not verify_scheduled[epoch_index]:
                                verify_scheduled[epoch_index] = True
                                vdelay = scheme.epoch_verify_delay if scheme.epoch_verify_delay is not None else scheme.aead_delay
                                push_event(time + vdelay, 'RX_EPOCH_VERIFIED', {'epoch_index': epoch_index, 'gen': rx_gen})

        elif typ == 'RX_DELIVER':
            seq = data['seq']
            if seq == next_expected:
                delivered_time[seq] = time
                next_expected += 1
                nak_outstanding = False
                push_event(time + link.d_ctrl + link.d_prop, 'ACK_ARRIVE', {'ack_next': next_expected})
            else:
                if not nak_outstanding:
                    push_event(time + link.d_ctrl + link.d_prop, 'NAK_ARRIVE', {'nack_seq': next_expected})
                    nak_outstanding = True

        elif typ == 'RX_EPOCH_VERIFIED':
            if M is None:
                continue
            if data['gen'] != rx_gen:
                continue
            idx = data['epoch_index']
            if 0 <= idx < len(verified):
                verified[idx] = True
            modeb_try_commit(time)

        elif typ == 'ACK_ARRIVE':
            ack_next = data['ack_next']
            if ack_next > base:
                base = ack_next
                if next_seq < base:
                    next_seq = base
            if not tx_chain_active:
                tx_chain_active = True
                push_event(time, 'TX_READY', {'plan': plan_id})

        elif typ == 'NAK_ARRIVE':
            nack_seq = data['nack_seq']
            if nack_seq == base and next_seq == base:
                continue
            if nack_seq < base or nack_seq > num_frames:
                continue
            base = nack_seq
            next_seq = nack_seq
            plan_id += 1
            tx_chain_active = True
            push_event(time, 'TX_READY', {'plan': plan_id})

        if next_expected >= num_frames:
            break

    if len(delivered_time) < num_frames:
        return {'error': 'deadlock', 'delivered': len(delivered_time)}

    latencies = np.array([delivered_time[s] - first_tx_time[s] for s in range(num_frames)], dtype=float)
    mean_lat = float(np.mean(latencies))
    p99_lat = float(np.percentile(latencies, 99))

    payload_bytes = num_frames * link.payload_bytes
    goodput_norm = (payload_bytes / last_tx_end_time) / link.W_link
    eff_payload_over_tx = payload_bytes / total_tx_bytes

    out = {
        'mean_latency': mean_lat,
        'p99_latency': p99_lat,
        'total_commit_time': float(max(delivered_time.values())),
        'last_tx_end_time': float(last_tx_end_time),
        'goodput_norm': float(goodput_norm),
        'eff_payload_over_tx': float(eff_payload_over_tx),
        'retransmissions': int(total_tx_frames - num_frames),
        'total_tx_frames': int(total_tx_frames),
        'total_tx_bytes': int(total_tx_bytes),
    }

    if M is not None:
        epoch_lat = np.array(epoch_latency_samples, dtype=float)
        out['p99_epoch_latency'] = float(np.percentile(epoch_lat, 99))
        out['mean_epoch_latency'] = float(np.mean(epoch_lat))
        out['epochs'] = int(len(epoch_latency_samples))

    return out


def run_sweep(pi_B_values, beta, p_good, p_bad, num_frames, seeds, schemes_and_links):
    rows = []
    for pi_B in pi_B_values:
        alpha = 0.0 if pi_B == 0 else (pi_B * beta / (1.0 - pi_B))
        ge = GEParams(p_good=p_good, p_bad=p_bad, alpha=alpha, beta=beta)
        for scheme, link, latency_metric in schemes_and_links:
            results = [simulate_link(num_frames, scheme, link, ge, seed=int(s)) for s in seeds]
            if any(('error' in r) for r in results):
                raise RuntimeError(f'Deadlock in simulation at pi_B={pi_B}, scheme={scheme.name}')
            p99_vals = [r[latency_metric] for r in results]
            gp_vals = [r['goodput_norm'] for r in results]
            eff_vals = [r['eff_payload_over_tx'] for r in results]
            retr_vals = [r['retransmissions'] for r in results]

            rows.append({
                'pi_B': pi_B,
                'beta': beta,
                'scheme': scheme.name,
                'lat_p99_mean': mean_ci95(p99_vals)[0],
                'lat_p99_ci': mean_ci95(p99_vals)[1],
                'goodput_mean': mean_ci95(gp_vals)[0],
                'goodput_ci': mean_ci95(gp_vals)[1],
                'eff_payload_over_tx_mean': mean_ci95(eff_vals)[0],
                'eff_payload_over_tx_ci': mean_ci95(eff_vals)[1],
                'retransmissions_mean': mean_ci95(retr_vals)[0],
                'retransmissions_ci': mean_ci95(retr_vals)[1],
            })
    return pd.DataFrame(rows)


def save_plot_latency(df: pd.DataFrame, schemes: List[str], path: Path, title: str):
    plt.figure(figsize=(6.5, 4.0))
    for sch in schemes:
        sub = df[df['scheme'] == sch].sort_values('pi_B')
        plt.errorbar(sub['pi_B'], sub['lat_p99_mean'], yerr=sub['lat_p99_ci'], marker='o', linestyle='-', capsize=3, label=sch)
    plt.xlabel('Bad-state probability π_B')
    plt.ylabel('p99 deliverability latency (cycles)')
    plt.title(title)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def save_plot_goodput(df: pd.DataFrame, schemes: List[str], path: Path, title: str):
    plt.figure(figsize=(6.5, 4.0))
    for sch in schemes:
        sub = df[df['scheme'] == sch].sort_values('pi_B')
        plt.errorbar(sub['pi_B'], sub['goodput_mean'], yerr=sub['goodput_ci'], marker='o', linestyle='-', capsize=3, label=sch)
    plt.xlabel('Bad-state probability π_B')
    plt.ylabel('Normalized goodput (payload / link capacity)')
    plt.title(title)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def save_modeb_eff_vs_M(path: Path):
    Ms = np.array([1, 2, 4, 8, 16, 32, 64, 128])
    payload = 256
    header_crc = 16 + 4
    tag = 12
    avg_bytes = payload + header_crc + (tag / Ms)
    eff = payload / avg_bytes
    plt.figure(figsize=(6.5, 4.0))
    plt.plot(Ms, eff, marker='o')
    plt.xscale('log', base=2)
    plt.xticks(Ms, [str(m) for m in Ms])
    plt.xlabel('Epoch size M (frames)')
    plt.ylabel('Wire efficiency η_wire')
    plt.title('Mode B wire efficiency vs epoch size')
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def save_modeb_latency_vs_M(path: Path, W_link=8, d_prop=2, d_crc=1, verify=8):
    Ms = np.array([4, 8, 16, 32, 64, 128])
    payload = 256
    header_crc = 16 + 4
    base_bytes = payload + header_crc
    tag = 12
    base_cycles = int(math.ceil(base_bytes / W_link))
    last_cycles = int(math.ceil((base_bytes + tag) / W_link))
    epoch_tx = (Ms - 1) * base_cycles + last_cycles
    lat = epoch_tx + d_prop + d_crc + verify

    plt.figure(figsize=(6.5, 4.0))
    plt.plot(Ms, lat, marker='o')
    plt.xscale('log', base=2)
    plt.xticks(Ms, [str(m) for m in Ms])
    plt.xlabel('Epoch size M (frames)')
    plt.ylabel('Head-of-epoch latency (cycles)')
    plt.title('Mode B baseline latency vs epoch size (no errors)')
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(path, dpi=300)
    plt.close()


def write_graphviz(dot_text: str, out_png: Path):
    dot_path = out_png.with_suffix('.dot')
    dot_path.write_text(dot_text)
    subprocess.run(['dot', '-Tpng', str(dot_path), '-o', str(out_png)], check=True)


def generate_architecture_diagram(out_png: Path):
    dot_arch = r'''
    digraph G {
      rankdir=LR;
      fontsize=12;
      labelloc="t";
      label="Protocol layering vs co-design (conceptual)";
      node [shape=box, fontsize=10, style="rounded,filled", fillcolor="white"];
      edge [fontsize=9];

      subgraph cluster_naive {
        label="Naive layered stack";
        style="rounded";
        color="gray50";
        n_tx [label="TX: AEAD\n(AES-GCM / Ascon)\n+ Tag"];
        n_crc [label="TX: CRC + ARQ header"];
        n_link [label="Link", shape=oval];
        n_rx_crc [label="RX: CRC check\n(ACK/NAK)"];
        n_rx_aead [label="RX: AEAD verify"];
        n_app [label="Upper layer consumes\npayload"];
        n_tx -> n_crc -> n_link -> n_rx_crc -> n_rx_aead -> n_app;
        n_rx_crc -> n_app [label="(BUG) early ACK / buffer free\nbefore verify", style=dashed, color="red3"];
      }

      subgraph cluster_shield {
        label="ShieldLink (deliverability-invariant)";
        style="rounded";
        color="gray50";
        s_tx [label="TX: CRC + AEAD\nco-designed header"];
        s_link [label="Link", shape=oval];
        s_rx [label="RX: CRC+AEAD gate\nACK only after deliverable"];
        s_app [label="Upper layer consumes\npayload"];
        s_tx -> s_link -> s_rx -> s_app;
      }
    }
    '''
    write_graphviz(dot_arch, out_png)


def generate_receiver_fsm(out_png: Path):
    dot_fsm = r'''
    digraph FSM {
      rankdir=LR;
      fontsize=12;
      labelloc="t";
      label="Receiver-side gating for deliverability invariant (Mode A)";
      node [shape=ellipse, fontsize=10, style="filled", fillcolor="white"];
      edge [fontsize=9];

      S0 [label="Idle / Waiting\nfor next_expected"];
      S1 [label="CRC Check"];
      S2 [label="AEAD Verify"];
      S3 [label="Deliver + ACK"];
      S4 [label="Reliability NAK\n(request retransmit)"];
      S5 [label="Security Drop\n(silent discard)"];

      S0 -> S1 [label="frame arrives"];
      S1 -> S4 [label="CRC fail"];
      S1 -> S2 [label="CRC ok"];
      S2 -> S3 [label="tag ok, seq ok"];
      S2 -> S5 [label="tag fail (active attack)"];
      S4 -> S0 [label="wait"];
      S3 -> S0 [label="advance seq"];
      S5 -> S0 [label="(optional) reset/alert"];
    }
    '''
    write_graphviz(dot_fsm, out_png)


def generate_timing_diagram(out_png: Path):
    # Simple timeline illustrating validity-before-verification race
    plt.figure(figsize=(7.0, 3.5))
    ax = plt.gca()
    ax.set_axis_off()

    lanes = ['Sender', 'Receiver', 'ARQ/Buffer', 'AEAD']
    y = [3, 2, 1, 0]
    for yi, lane in zip(y, lanes):
        ax.text(0.0, yi, lane, va='center', ha='left', fontsize=10)
        ax.hlines(yi, 0.15, 0.95)

    # Events
    # Sender sends frame
    ax.annotate('', xy=(0.30, 3), xytext=(0.20, 3), arrowprops=dict(arrowstyle='->'))
    ax.text(0.21, 3.15, 'send frame', fontsize=8)

    # Receiver CRC ok
    ax.vlines(0.45, 1.9, 2.1)
    ax.text(0.43, 2.25, 'CRC ok', fontsize=8)

    # Naive: ACK early
    ax.annotate('', xy=(0.55, 2), xytext=(0.47, 2), arrowprops=dict(arrowstyle='->'))
    ax.text(0.48, 2.15, 'ACK (too early)', fontsize=8)
    ax.vlines(0.58, 0.9, 1.1)
    ax.text(0.56, 1.25, 'buffer freed', fontsize=8)

    # AEAD verifies later and fails
    ax.vlines(0.75, -0.1, 0.1)
    ax.text(0.70, 0.25, 'AEAD fail', fontsize=8)
    ax.text(0.62, -0.35, 'payload not deliverable\n(but already ACKed)', fontsize=8)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.8, 3.8)
    plt.tight_layout()
    plt.savefig(out_png, dpi=300)
    plt.close()


def main():
    # --- Simulation parameters used in the paper plots ---
    # NOTE: these are stress-regime effective *frame* corruption rates in the Bad state.
    beta = 0.2
    p_good = 1e-6
    p_bad = 0.1

    link = LinkParams(W_link=8, d_prop=2, d_crc=1, d_aead=8, N_win=64, payload_bytes=256)

    scheme_modeA = Scheme(name='ShieldLink Mode A', frame_bytes=288, aead_delay=8)
    scheme_naive = Scheme(name='Naive Stacking (secure)', frame_bytes=296, aead_delay=10)
    scheme_modeB = Scheme(name='ShieldLink Mode B (M=32)', frame_bytes=276, aead_delay=8, epoch_size=32, epoch_verify_delay=8)

    schemes = [
        (scheme_modeA, link, 'p99_latency'),
        (scheme_naive, link, 'p99_latency'),
        (scheme_modeB, link, 'p99_epoch_latency'),
    ]

    pi_B_values = [0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1]
    # Keep runtime bounded for artifact generation.
    # 16k frames (multiple of M=32) and 5 Monte-Carlo seeds support the revised confidence intervals.
    seeds = list(range(5))
    num_frames = 16384

    df = run_sweep(pi_B_values, beta=beta, p_good=p_good, p_bad=p_bad, num_frames=num_frames, seeds=seeds, schemes_and_links=schemes)
    out_csv = DATA_DIR / 'simulation_sweep_beta0.2_pbad0.1.csv'
    df.to_csv(out_csv, index=False)

    # Plots
    save_plot_latency(df, [s[0].name for s in schemes], FIG_DIR / 'fig_p99_latency_vs_piB.png',
                      'Tail latency vs burstiness (Gilbert–Elliott)')
    save_plot_goodput(df, [s[0].name for s in schemes], FIG_DIR / 'fig_goodput_vs_piB.png',
                      'Goodput vs burstiness (Gilbert–Elliott)')

    save_modeb_eff_vs_M(FIG_DIR / 'fig_modeB_eff_vs_M.png')
    save_modeb_latency_vs_M(FIG_DIR / 'fig_modeB_latency_vs_M.png', W_link=link.W_link, d_prop=link.d_prop, d_crc=link.d_crc, verify=8)

    # Beta sweep crossover table (coarse)
    betas = [0.05, 0.1, 0.2, 0.5]
    pi_vals = [round(x, 3) for x in np.arange(0.0, 0.1001, 0.005)]
    rows = []
    for b in betas:
        df_b = run_sweep(pi_vals, beta=b, p_good=p_good, p_bad=p_bad, num_frames=16384, seeds=list(range(5)), schemes_and_links=schemes)
        modeA_gp = df_b[df_b.scheme == scheme_modeA.name].set_index('pi_B')['goodput_mean']
        modeB_gp = df_b[df_b.scheme == scheme_modeB.name].set_index('pi_B')['goodput_mean']
        cross = None
        for pi in pi_vals:
            if modeB_gp.loc[pi] < modeA_gp.loc[pi]:
                cross = pi
                break
        rows.append({'beta': b, 'mean_bad_burst_len_frames': (1.0 / b), 'crossover_pi_B': cross})
    df_cross = pd.DataFrame(rows)
    df_cross.to_csv(DATA_DIR / 'crossover_table_beta_sweep.csv', index=False)

    # Diagrams
    generate_architecture_diagram(FIG_DIR / 'fig_architecture.png')
    generate_receiver_fsm(FIG_DIR / 'fig_receiver_fsm.png')
    generate_timing_diagram(FIG_DIR / 'fig_timing_race.png')

    print('Assets generated into', OUT_DIR)


if __name__ == '__main__':
    main()
