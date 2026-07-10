#!/usr/bin/env python3
import argparse, csv, math, random, statistics

W = 8.0
P = 256
HEADER = 16
CRC = 4
TAG = 12
M = 32
P_GOOD = 1e-6
P_BAD = 0.1
BETA = 0.2
SEEDS = range(5)
EPOCHS = 20000
PIBS = [0.0,0.01,0.02,0.03,0.04,0.05,0.075,0.10]

schemes = ["crc_arq", "modeA", "modeB_flush", "modeB_selective_retry"]

class GE:
    def __init__(self, pi_b, beta, seed):
        self.pi_b=pi_b; self.beta=beta; self.r=random.Random(seed)
        self.alpha = 0.0 if pi_b <= 0 else (pi_b*beta)/(1.0-pi_b)
        self.bad = self.r.random() < pi_b
    def tx_corrupt(self):
        p = P_BAD if self.bad else P_GOOD
        corrupt = self.r.random() < p
        if self.bad:
            if self.r.random() < self.beta: self.bad = False
        else:
            if self.r.random() < self.alpha: self.bad = True
        return corrupt

def ci95(xs):
    if len(xs) < 2: return 0.0
    return 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))

def sim_per_frame(pi_b, seed, frame_bytes, secure=True):
    ge = GE(pi_b, BETA, 100000 + 1000*seed + int(pi_b*10000))
    total_cycles = 0.0; lat=[]; delivered=0
    for _ in range(EPOCHS*M):
        attempts=0
        while True:
            attempts += 1
            total_cycles += frame_bytes / W
            if not ge.tx_corrupt():
                delivered += 1
                # p99 latency includes one AEAD verification for Mode A but not throughput stalls.
                extra = 8.0 if secure else 1.0
                lat.append(attempts * (frame_bytes/W) + extra)
                break
    goodput = (delivered*P)/(total_cycles*W)
    return goodput, percentile(lat, 99)

def sim_epoch_flush(pi_b, seed):
    ge = GE(pi_b, BETA, 200000 + 1000*seed + int(pi_b*10000))
    frameB = HEADER + P + CRC
    total_cycles=0.0; lat=[]; delivered=0
    for _ in range(EPOCHS):
        epoch_cycles=0.0
        while True:
            failed=False
            for _ in range(M):
                total_cycles += frameB/W; epoch_cycles += frameB/W
                if ge.tx_corrupt(): failed=True
            total_cycles += TAG/W; epoch_cycles += TAG/W
            if not failed:
                total_cycles += 0.0
                lat.append(epoch_cycles + 8.0)
                delivered += M
                break
            # flush-all: retransmit all M frames on any CRC failure
    goodput=(delivered*P)/(total_cycles*W)
    return goodput, percentile(lat, 99)

def sim_epoch_sr(pi_b, seed):
    ge = GE(pi_b, BETA, 300000 + 1000*seed + int(pi_b*10000))
    frameB = HEADER + P + CRC
    total_cycles=0.0; lat=[]; delivered=0
    for _ in range(EPOCHS):
        epoch_cycles=0.0
        missing=list(range(M))
        while missing:
            next_missing=[]
            for _ in missing:
                total_cycles += frameB/W; epoch_cycles += frameB/W
                if ge.tx_corrupt(): next_missing.append(_)
            # one epoch tag verification per full/repair round; bitmap NAK assumed sideband/credit path
            total_cycles += TAG/W; epoch_cycles += TAG/W
            missing = next_missing
        lat.append(epoch_cycles + 8.0)
        delivered += M
    goodput=(delivered*P)/(total_cycles*W)
    return goodput, percentile(lat, 99)

def percentile(xs, p):
    xs=sorted(xs)
    if not xs: return float('nan')
    k=(len(xs)-1)*p/100.0
    f=math.floor(k); c=math.ceil(k)
    if f==c: return xs[int(k)]
    return xs[f]*(c-k)+xs[c]*(k-f)

rows=[]
for pi in PIBS:
    for scheme in schemes:
        gps=[]; lats=[]
        for seed in SEEDS:
            if scheme == 'crc_arq': gp,lat = sim_per_frame(pi, seed, HEADER+P+CRC-8, secure=False) # 268B baseline from paper
            elif scheme == 'modeA': gp,lat = sim_per_frame(pi, seed, HEADER+P+CRC+TAG, secure=True)
            elif scheme == 'modeB_flush': gp,lat = sim_epoch_flush(pi, seed)
            else: gp,lat = sim_epoch_sr(pi, seed)
            gps.append(gp); lats.append(lat)
        rows.append({
            'piB': pi,
            'scheme': scheme,
            'goodput_mean': statistics.mean(gps),
            'goodput_ci95': ci95(gps),
            'p99_latency_cycles_mean': statistics.mean(lats),
            'p99_latency_cycles_ci95': ci95(lats)
        })

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='data/selective_retry_followup_results.csv')
args = ap.parse_args()

with open(args.out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

print(f'Wrote: {args.out}')
# representative compact markdown table
for r in rows:
    if r['piB'] in (0.01,0.04,0.05,0.10):
        print(f"{r['piB']:.2f} {r['scheme']:24s} gp={r['goodput_mean']:.3f}±{r['goodput_ci95']:.3f} p99={r['p99_latency_cycles_mean']:.0f}±{r['p99_latency_cycles_ci95']:.0f}")
