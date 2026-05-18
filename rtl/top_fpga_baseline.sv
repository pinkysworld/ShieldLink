// SPDX-License-Identifier: MIT
// FPGA/synthesis top for baseline CRC+ARQ control (no AEAD gating).

module top_fpga_baseline #(
    parameter int SEQ_W = 64
) (
    input  logic clk,
    input  logic rst_n,
    input  logic rx_valid,
    input  logic [SEQ_W-1:0] rx_seq,
    input  logic rx_crc_ok,
    input  logic rx_aead_ok, // unused
    output logic ack_valid,
    output logic nak_valid
);
    logic [SEQ_W-1:0] next_expected;
    logic [SEQ_W-1:0] ack_seq, nak_seq;
    logic deliver_pulse;

    baseline_ctrl_crc_arq #(.SEQ_W(SEQ_W)) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .rx_valid(rx_valid),
        .rx_seq(rx_seq),
        .rx_crc_ok(rx_crc_ok),
        .next_expected(next_expected),
        .ack_valid(ack_valid),
        .ack_seq(ack_seq),
        .nak_valid(nak_valid),
        .nak_seq(nak_seq),
        .deliver_pulse(deliver_pulse)
    );
endmodule
