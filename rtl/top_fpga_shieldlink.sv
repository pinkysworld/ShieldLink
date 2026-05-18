// SPDX-License-Identifier: MIT
// FPGA/synthesis top for ShieldLink Mode A control (D-Inv gating).

module top_fpga_shieldlink #(
    parameter int SEQ_W = 64
) (
    input  logic clk,
    input  logic rst_n,
    input  logic rx_valid,
    input  logic [SEQ_W-1:0] rx_seq,
    input  logic rx_crc_ok,
    input  logic rx_aead_ok,
    output logic ack_valid,
    output logic nak_valid,
    output logic security_drop_pulse
);
    logic [SEQ_W-1:0] next_expected;
    logic [SEQ_W-1:0] ack_seq, nak_seq;
    logic deliver_pulse;

    shieldlink_ctrl_modeA #(.SEQ_W(SEQ_W)) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .rx_valid(rx_valid),
        .rx_seq(rx_seq),
        .rx_crc_ok(rx_crc_ok),
        .rx_aead_ok(rx_aead_ok),
        .next_expected(next_expected),
        .ack_valid(ack_valid),
        .ack_seq(ack_seq),
        .nak_valid(nak_valid),
        .nak_seq(nak_seq),
        .deliver_pulse(deliver_pulse),
        .security_drop_pulse(security_drop_pulse)
    );
endmodule
