// SPDX-License-Identifier: MIT
// ShieldLink control-plane teaser (Mode B: epoch MAC aggregation)
// Baseline behavior evaluated in the paper: "flush-all epoch" on any CRC/AEAD failure.
// Selective retry (bitmap NAK) is left as an obvious optimization.

module shieldlink_ctrl_modeB #(
    parameter int SEQ_W = 64,
    parameter int M     = 32,
    parameter int FRAME_BITS = 276*8  // Header(16B)+Payload(256B)+CRC(4B)
) (
    input  logic               clk,
    input  logic               rst_n,

    // Streamed SLFs (per-frame, no per-frame tag)
    input  logic               rx_valid,
    input  logic [SEQ_W-1:0]   rx_seq,
    input  logic               rx_crc_ok,
    input  logic [FRAME_BITS-1:0] rx_frame_bits,

    // Epoch tag verification result (arrives after M frames + tag)
    input  logic               epoch_tag_valid,
    input  logic               epoch_aead_ok,

    output logic [SEQ_W-1:0]   next_expected,

    // Outputs
    output logic               ack_valid,
    output logic [SEQ_W-1:0]   ack_seq,
    output logic               nak_valid,
    output logic [SEQ_W-1:0]   nak_seq,
    output logic               epoch_commit_pulse,
    output logic               epoch_flush_pulse,
    output logic               security_drop_pulse
);

    // Epoch buffer (SRAM/BRAM inference)
    logic [FRAME_BITS-1:0] epoch_mem [0:M-1];
    logic [M-1:0] crc_ok_bitmap;

    logic [$clog2(M)-1:0] idx;
    logic epoch_any_crc_fail;
    logic seq_eq;
    logic epoch_active;

    logic [SEQ_W-1:0] epoch_start_seq;

    always_comb begin
        epoch_any_crc_fail = |(~crc_ok_bitmap);
        seq_eq = (rx_seq == (epoch_start_seq + idx));
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            next_expected <= '0;
            epoch_start_seq <= '0;
            idx <= '0;
            crc_ok_bitmap <= {M{1'b1}};
            epoch_active <= 1'b0;

            ack_valid <= 1'b0;
            ack_seq   <= '0;
            nak_valid <= 1'b0;
            nak_seq   <= '0;
            epoch_commit_pulse <= 1'b0;
            epoch_flush_pulse  <= 1'b0;
            security_drop_pulse <= 1'b0;
        end else begin
            ack_valid <= 1'b0;
            nak_valid <= 1'b0;
            epoch_commit_pulse <= 1'b0;
            epoch_flush_pulse  <= 1'b0;
            security_drop_pulse <= 1'b0;

            if (!epoch_active) begin
                epoch_active <= 1'b1;
                epoch_start_seq <= next_expected;
                idx <= '0;
                crc_ok_bitmap <= {M{1'b1}};
            end

            if (epoch_active && rx_valid) begin
                if (rx_crc_ok && seq_eq) begin
                    epoch_mem[idx] <= rx_frame_bits;
                    crc_ok_bitmap[idx] <= 1'b1;
                    idx <= idx + 1'b1;
                end else begin
                    crc_ok_bitmap[idx] <= 1'b0;
                    idx <= idx + 1'b1;
                end
            end

            if (epoch_active && epoch_tag_valid) begin
                if (!epoch_any_crc_fail && epoch_aead_ok) begin
                    next_expected <= next_expected + M;
                    ack_valid <= 1'b1;
                    ack_seq   <= next_expected + M;
                    epoch_commit_pulse <= 1'b1;
                end else if (!epoch_aead_ok) begin
                    security_drop_pulse <= 1'b1;
                end else begin
                    nak_valid <= 1'b1;
                    nak_seq   <= epoch_start_seq;
                    epoch_flush_pulse <= 1'b1;
                end
                epoch_active <= 1'b0;
            end
        end
    end

endmodule
