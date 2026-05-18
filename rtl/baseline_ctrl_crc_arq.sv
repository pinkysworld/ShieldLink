// SPDX-License-Identifier: MIT
// Baseline reliability-only receiver control (CRC + go-back-N).
// Models an unsafe early-ACK integration hazard when paired with separate AEAD.

module baseline_ctrl_crc_arq #(
    parameter int SEQ_W = 64
) (
    input  logic clk,
    input  logic rst_n,
    input  logic rx_valid,
    input  logic [SEQ_W-1:0] rx_seq,
    input  logic rx_crc_ok,

    output logic [SEQ_W-1:0] next_expected,
    output logic ack_valid,
    output logic [SEQ_W-1:0] ack_seq,
    output logic nak_valid,
    output logic [SEQ_W-1:0] nak_seq,
    output logic deliver_pulse
);

    logic seq_eq;
    always_comb seq_eq = (rx_seq == next_expected);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            next_expected <= '0;
            ack_valid <= 1'b0;
            ack_seq <= '0;
            nak_valid <= 1'b0;
            nak_seq <= '0;
            deliver_pulse <= 1'b0;
        end else begin
            ack_valid <= 1'b0;
            nak_valid <= 1'b0;
            deliver_pulse <= 1'b0;

            if (rx_valid) begin
                if (!rx_crc_ok) begin
                    nak_valid <= 1'b1;
                    nak_seq   <= next_expected;
                end else if (rx_crc_ok && seq_eq) begin
                    next_expected <= next_expected + 1'b1;
                    ack_valid <= 1'b1;
                    ack_seq   <= next_expected + 1'b1;
                    deliver_pulse <= 1'b1;
                end else begin
                    ack_valid <= 1'b1;
                    ack_seq   <= next_expected;
                end
            end
        end
    end

endmodule
