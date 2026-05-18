#!/usr/bin/env python3
"""ShieldLink FPGA/Synthesis Teaser: resource sizing helper.

This script reproduces the buffer sizing numbers used in the paper's RTL feasibility section.
It is *not* a substitute for synthesis; it computes exact memory bits and maps them to common
FPGA block RAM sizes (18Kb and 36Kb) as an intuition aid.

License: MIT
"""

import argparse
import csv
import math


def bram_blocks(bits: int, bram_bits: int) -> int:
    return math.ceil(bits / bram_bits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', type=int, default=256, help='Payload bytes (P)')
    ap.add_argument('--header', type=int, default=16, help='Header bytes (H)')
    ap.add_argument('--crc', type=int, default=4, help='CRC bytes')
    ap.add_argument('--tag', type=int, default=12, help='Tag bytes (Mode A)')
    ap.add_argument('--nwin', type=int, default=64, help='ARQ window size (N_win)')
    ap.add_argument('--m', type=int, default=32, help='Mode B epoch length (M)')
    ap.add_argument('--out', type=str, default='rtl_resource_sizing.csv', help='Output CSV')
    args = ap.parse_args()

    P, H, CRC, TAG, N, M = args.payload, args.header, args.crc, args.tag, args.nwin, args.m

    frameA = H + P + CRC + TAG
    frameB = H + P + CRC

    bufA_bytes = frameA * N
    bufB_bytes = frameB * M
    delta_tag_bytes = TAG * N

    rows = [
        {
            'Item': 'Mode A TX retry buffer (N_win)',
            'Per-frame bytes': frameA,
            'Frames': N,
            'Total bytes': bufA_bytes,
            'Total KiB': bufA_bytes / 1024,
            'Total bits': bufA_bytes * 8,
            '18Kb BRAM blocks (18,432b)': bram_blocks(bufA_bytes * 8, 18432),
            '36Kb BRAM blocks (36,864b)': bram_blocks(bufA_bytes * 8, 36864),
        },
        {
            'Item': 'Mode B RX epoch buffer (M)',
            'Per-frame bytes': frameB,
            'Frames': M,
            'Total bytes': bufB_bytes,
            'Total KiB': bufB_bytes / 1024,
            'Total bits': bufB_bytes * 8,
            '18Kb BRAM blocks (18,432b)': bram_blocks(bufB_bytes * 8, 18432),
            '36Kb BRAM blocks (36,864b)': bram_blocks(bufB_bytes * 8, 36864),
        },
        {
            'Item': 'Incremental storage for tags (Mode A vs. no-tag)',
            'Per-frame bytes': TAG,
            'Frames': N,
            'Total bytes': delta_tag_bytes,
            'Total KiB': delta_tag_bytes / 1024,
            'Total bits': delta_tag_bytes * 8,
            '18Kb BRAM blocks (18,432b)': bram_blocks(delta_tag_bytes * 8, 18432),
            '36Kb BRAM blocks (36,864b)': bram_blocks(delta_tag_bytes * 8, 36864),
        },
    ]

    # Pretty print
    print('\nResource sizing (bytes/bits):')
    for r in rows:
        print(f"- {r['Item']}: {r['Total KiB']:.3f} KiB ({r['Total bits']} bits), BRAM18={r['18Kb BRAM blocks (18,432b)']}, BRAM36={r['36Kb BRAM blocks (36,864b)']}")

    # Write CSV
    with open(args.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote: {args.out}")


if __name__ == '__main__':
    main()
