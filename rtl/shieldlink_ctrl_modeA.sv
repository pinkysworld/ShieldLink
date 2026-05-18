// SPDX-License-Identifier: MIT
// ShieldLink control-plane teaser (Mode A)
// Minimal, synthesizable SystemVerilog describing D-Inv ACK/NAK gating.
//
// NOTE: AEAD/CRC computation is assumed to be pipelined elsewhere; inputs are
// registered results for a received SLF at this cycle.

module shieldlink_ctrl_modeA #(
    parameter int SEQ_W = 64
) (
    input  logic               clk,
    input  logic               rst_n,

    // One SLF decision point per cycle (after parsing)
    input  logic               rx_valid,
    input  logic [SEQ_W-1:0]   rx_seq,
    input  logic               rx_crc_ok,
    input  logic               rx_aead_ok,

    // Receiver-side state
    output logic [SEQ_W-1:0]   next_expected,

    // Outputs
    output logic               ack_valid,
    output logic [SEQ_W-1:0]   ack_seq,      // cumulative ACK: next_expected after commit
    output logic               nak_valid,
    output logic [SEQ_W-1:0]   nak_seq,      // request retransmit from expected
    output logic               deliver_pulse,
    output logic               security_drop_pulse
);

    logic seq_eq;
    logic deliverable;

    // Equality check: accept only in-order for go-back-N
    always_comb begin
        seq_eq = (rx_seq == next_expected);
        // Deliverability Invariant (Mode A):
        // deliverable iff CRC_ok AND AEAD_ok AND Seq_valid
        deliverable = rx_crc_ok && rx_aead_ok && seq_eq;
    end

    // Default outputs
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            next_expected <= '0;
            ack_valid <= 1'b0;
            ack_seq   <= '0;
            nak_valid <= 1'b0;
            nak_seq   <= '0;
            deliver_pulse <= 1'b0;
            security_drop_pulse <= 1'b0;
        end else begin
            // pulses default low
            ack_valid <= 1'b0;
            nak_valid <= 1'b0;
            deliver_pulse <= 1'b0;
            security_drop_pulse <= 1'b0;

            if (rx_valid) begin
                if (!rx_crc_ok) begin
                    // Reliability failure: fast NAK (benign corruption)
                    nak_valid <= 1'b1;
                    nak_seq   <= next_expected;
                end else if (deliverable) begin
                    // Commit + ACK: only here do we advance NEXT_EXPECTED
                    next_expected <= next_expected + 1'b1;
                    ack_valid <= 1'b1;
                    ack_seq   <= next_expected + 1'b1;
                    deliver_pulse <= 1'b1;
                end else if (rx_crc_ok && !rx_aead_ok) begin
                    // Security failure: silent drop (no oracle), log event
                    security_drop_pulse <= 1'b1;
                    // No ACK/NAK emitted; sender recovers via timeout/link policy
                end else begin
                    // CRC ok, AEAD ok, but out-of-order: duplicate ACK
                    ack_valid <= 1'b1;
                    ack_seq   <= next_expected;
                end
            end
        end
    end

endmodule
