#!/usr/bin/env python3
"""Bounded safety sanity check for the ShieldLink ACK gate.

This executable model checks that receiver state advances and ACKs are emitted
only for deliverable frames. It is deliberately a bounded safety explorer, not
an unbounded proof or liveness verification.
"""
from __future__ import annotations
from collections import deque, namedtuple
from typing import Tuple

MOD = 8
N_WIN = 4
DEPTH = 14
Frame = namedtuple('Frame', 'seq crc_ok aead_ok')
Feedback = namedtuple('Feedback', 'kind seq')
State = namedtuple('State', 'base next_seq next_expected chan fb delivered')

def dist(a: int, b: int) -> int:
    return (b - a) % MOD

def in_window(base: int, seq: int) -> bool:
    return dist(base, seq) < N_WIN

def delivered_contains(delivered: Tuple[int, ...], seq: int) -> bool:
    return seq in delivered

def step_transmit(s: State):
    if not in_window(s.base, s.next_seq):
        return
    for crc_ok in (False, True):
        for aead_ok in (False, True):
            f = Frame(s.next_seq, crc_ok, aead_ok)
            yield State(s.base, (s.next_seq + 1) % MOD, s.next_expected,
                        s.chan + (f,), s.fb, s.delivered)

def step_receive(s: State):
    if not s.chan:
        return
    f = s.chan[0]
    rest = s.chan[1:]
    fb = s.fb
    delivered = s.delivered
    next_expected = s.next_expected
    seq_ok_new = (f.seq == next_expected)
    seq_ok_dup = delivered_contains(delivered, f.seq)
    seq_ok = seq_ok_new or seq_ok_dup
    deliverable = f.crc_ok and f.aead_ok and seq_ok
    if not f.crc_ok:
        yield State(s.base, s.next_seq, next_expected, rest, fb + (Feedback('NAK', next_expected),), delivered)
        return
    if not f.aead_ok:
        yield State(s.base, s.next_seq, next_expected, rest, fb, delivered)
        return
    if seq_ok_new:
        assert deliverable, 'ACK emitted without deliverability'
        new_expected = (next_expected + 1) % MOD
        new_delivered = tuple(sorted(set(delivered + (f.seq,))))
        yield State(s.base, s.next_seq, new_expected, rest, fb + (Feedback('ACK', new_expected),), new_delivered)
    elif seq_ok_dup:
        assert deliverable, 'Duplicate ACK emitted without deliverability'
        yield State(s.base, s.next_seq, next_expected, rest, fb + (Feedback('ACK', next_expected),), delivered)
    else:
        yield State(s.base, s.next_seq, next_expected, rest, fb + (Feedback('NAK', next_expected),), delivered)

def step_feedback(s: State):
    if not s.fb:
        return
    msg = s.fb[0]
    rest = s.fb[1:]
    base, next_seq = s.base, s.next_seq
    if msg.kind == 'ACK':
        if dist(base, msg.seq) <= N_WIN:
            base = msg.seq
    else:
        base = msg.seq
        next_seq = msg.seq
    yield State(base, next_seq, s.next_expected, s.chan, rest, s.delivered)

def explore(depth: int = DEPTH):
    initial = State(0, 0, 0, tuple(), tuple(), tuple())
    seen = {initial}
    frontier = deque([(initial, 0)])
    transitions = 0
    while frontier:
        s, d = frontier.popleft()
        if d >= depth:
            continue
        for gen in (step_transmit, step_receive, step_feedback):
            for ns in gen(s) or ():
                transitions += 1
                if ns not in seen:
                    seen.add(ns)
                    frontier.append((ns, d + 1))
    return seen, transitions

if __name__ == '__main__':
    states, transitions = explore()
    print(f'Configuration: MOD={MOD}, N_WIN={N_WIN}, DEPTH={DEPTH}')
    print(f'Reachable states explored: {len(states)}')
    print(f'Transitions examined: {transitions}')
    print('Safety result: PASS (no ACK/state-advance counterexample reached)')
    print('Scope: bounded safety sanity check only; not a liveness proof.')
