// SPDX-License-Identifier: MIT
// FPGA/synthesis top for original ShieldLink Mode B flush-all epoch control.

module top_fpga_modeB_flush #(
    parameter int SEQ_W = 64,
    parameter int M = 32,
    parameter int FRAME_BITS = 276*8
) (
    input  logic                  clk,
    input  logic                  rst_n,
    input  logic                  rx_valid,
    input  logic [SEQ_W-1:0]      rx_seq,
    input  logic                  rx_crc_ok,
    input  logic [FRAME_BITS-1:0] rx_frame_bits,
    input  logic                  epoch_tag_valid,
    input  logic                  epoch_aead_ok,
    output logic                  ack_valid,
    output logic                  nak_valid,
    output logic                  security_drop_pulse
);
    logic [SEQ_W-1:0] next_expected;
    logic [SEQ_W-1:0] ack_seq, nak_seq;
    logic epoch_commit_pulse, epoch_flush_pulse;

    shieldlink_ctrl_modeB #(
        .SEQ_W(SEQ_W), .M(M), .FRAME_BITS(FRAME_BITS)
    ) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .rx_valid(rx_valid),
        .rx_seq(rx_seq),
        .rx_crc_ok(rx_crc_ok),
        .rx_frame_bits(rx_frame_bits),
        .epoch_tag_valid(epoch_tag_valid),
        .epoch_aead_ok(epoch_aead_ok),
        .next_expected(next_expected),
        .ack_valid(ack_valid),
        .ack_seq(ack_seq),
        .nak_valid(nak_valid),
        .nak_seq(nak_seq),
        .epoch_commit_pulse(epoch_commit_pulse),
        .epoch_flush_pulse(epoch_flush_pulse),
        .security_drop_pulse(security_drop_pulse)
    );
endmodule
