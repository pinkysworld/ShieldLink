#!/usr/bin/env python3
"""ShieldLink follow-up resource-sizing helper for Mode B selective retry.

This is an analytic/structural estimator, not a vendor synthesis report. It sizes the
state added by bitmap selective retry and maps epoch storage to common FPGA BRAM blocks.
"""

import argparse
import csv
import math


def bram_blocks(bits: int, bram_bits: int) -> int:
    return math.ceil(bits / bram_bits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', type=int, default=256)
    ap.add_argument('--header', type=int, default=16)
    ap.add_argument('--crc', type=int, default=4)
    ap.add_argument('--m', type=int, default=32)
    ap.add_argument('--seq-w', type=int, default=64)
    ap.add_argument('--out', type=str, default='modeB_sr_resource_sizing.csv')
    args = ap.parse_args()

    frame_b = args.header + args.payload + args.crc
    epoch_buffer_bits = frame_b * args.m * 8
    bitmap_bits = args.m * 3  # received, crc_fail, outgoing NAK bitmap
    counter_bits = math.ceil(math.log2(args.m)) if args.m > 1 else 1
    seq_state_bits = args.seq_w * 2  # next_expected, epoch_start_seq
    control_state_bits = bitmap_bits + counter_bits + seq_state_bits + 8

    rows = [
        {
            'Item': 'Mode B-SR RX epoch buffer',
            'Quantity': f'{args.m} frames x {frame_b} bytes',
            'Bits': epoch_buffer_bits,
            'KiB': epoch_buffer_bits / 8 / 1024,
            '18Kb BRAM blocks (18,432b)': bram_blocks(epoch_buffer_bits, 18432),
            '36Kb BRAM blocks (36,864b)': bram_blocks(epoch_buffer_bits, 36864),
            'Notes': 'Same data buffer as flush-all Mode B; good frames are retained across repair rounds.',
        },
        {
            'Item': 'Selective-retry bitmaps',
            'Quantity': f'3 x {args.m} bits',
            'Bits': bitmap_bits,
            'KiB': bitmap_bits / 8 / 1024,
            '18Kb BRAM blocks (18,432b)': 0,
            '36Kb BRAM blocks (36,864b)': 0,
            'Notes': 'received_bitmap, crc_fail_bitmap, and emitted nak_bitmap.',
        },
        {
            'Item': 'Approximate control state',
            'Quantity': 'sequence state, index, pulses, bitmaps',
            'Bits': control_state_bits,
            'KiB': control_state_bits / 8 / 1024,
            '18Kb BRAM blocks (18,432b)': 0,
            '36Kb BRAM blocks (36,864b)': 0,
            'Notes': 'Structural FF estimate only; excludes memory macro implementation and cipher core.',
        },
    ]

    for row in rows:
        print(f"{row['Item']}: {row['Bits']} bits ({row['KiB']:.4f} KiB)")

    with open(args.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote: {args.out}')


if __name__ == '__main__':
    main()
