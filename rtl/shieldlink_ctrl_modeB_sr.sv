// SPDX-License-Identifier: MIT
// ShieldLink Mode B-SR: epoch authentication with selective retry.
//
// This module extends the original Mode B flush-all baseline with a bitmap NAK path.
// CRC-failed or missing SLFs are retried selectively, while epoch commit remains gated
// on the original ShieldLink deliverability invariant at epoch granularity:
//   commit iff every SLF is present, no CRC failures remain, and the epoch AEAD tag verifies.
//
// Scope: synthesizable control-plane skeleton. CRC, AEAD, PHY, timeout, and sender-side
// retry scheduling are assumed to be pipelined blocks around this controller.

module shieldlink_ctrl_modeB_sr #(
    parameter int SEQ_W = 64,
    parameter int M     = 32,
    parameter int FRAME_BITS = 276*8  // Header(16B)+Payload(256B)+CRC(4B)
) (
    input  logic                  clk,
    input  logic                  rst_n,

    // Streamed SLFs. Retransmitted SLFs reuse their original sequence numbers.
    input  logic                  rx_valid,
    input  logic [SEQ_W-1:0]      rx_seq,
    input  logic                  rx_crc_ok,
    input  logic [FRAME_BITS-1:0] rx_frame_bits,

    // Epoch tag verification result. The verifier should assert this after the
    // receiver has a candidate complete epoch, including repaired SLFs.
    input  logic                  epoch_tag_valid,
    input  logic                  epoch_aead_ok,

    output logic [SEQ_W-1:0]      next_expected,

    // Cumulative ACK when the authenticated epoch commits.
    output logic                  ack_valid,
    output logic [SEQ_W-1:0]      ack_seq,

    // Bitmap NAK: bit i requests retransmission of epoch_start_seq+i.
    output logic                  nak_valid,
    output logic [SEQ_W-1:0]      nak_seq,
    output logic [M-1:0]          nak_bitmap,

    output logic                  epoch_commit_pulse,
    output logic                  epoch_repair_pulse,
    output logic                  security_drop_pulse
);

    localparam int IDX_W = (M <= 1) ? 1 : $clog2(M);

    // Epoch buffer (SRAM/BRAM inference in vendor flows).
    logic [FRAME_BITS-1:0] epoch_mem [0:M-1];

    logic [M-1:0] received_bitmap;
    logic [M-1:0] crc_fail_bitmap;
    logic [M-1:0] repair_bitmap;

    logic [SEQ_W-1:0] epoch_start_seq;
    logic [SEQ_W-1:0] seq_delta;
    logic [IDX_W-1:0] rx_idx;
    logic             in_epoch;
    logic             epoch_active;
    logic             epoch_complete;
    logic             epoch_clean;

    always_comb begin
        seq_delta      = rx_seq - epoch_start_seq;
        rx_idx         = seq_delta[IDX_W-1:0];
        in_epoch       = (seq_delta < M);
        repair_bitmap  = (~received_bitmap) | crc_fail_bitmap;
        epoch_complete = (&received_bitmap);
        epoch_clean    = (crc_fail_bitmap == '0);
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            next_expected       <= '0;
            epoch_start_seq     <= '0;
            received_bitmap     <= '0;
            crc_fail_bitmap     <= '0;
            epoch_active        <= 1'b0;

            ack_valid           <= 1'b0;
            ack_seq             <= '0;
            nak_valid           <= 1'b0;
            nak_seq             <= '0;
            nak_bitmap          <= '0;
            epoch_commit_pulse  <= 1'b0;
            epoch_repair_pulse  <= 1'b0;
            security_drop_pulse <= 1'b0;
        end else begin
            ack_valid           <= 1'b0;
            nak_valid           <= 1'b0;
            epoch_commit_pulse  <= 1'b0;
            epoch_repair_pulse  <= 1'b0;
            security_drop_pulse <= 1'b0;

            if (!epoch_active) begin
                epoch_active    <= 1'b1;
                epoch_start_seq <= next_expected;
                received_bitmap <= '0;
                crc_fail_bitmap <= '0;
                nak_bitmap      <= '0;
            end

            if (epoch_active && rx_valid && in_epoch) begin
                if (rx_crc_ok) begin
                    epoch_mem[rx_idx]       <= rx_frame_bits;
                    received_bitmap[rx_idx] <= 1'b1;
                    crc_fail_bitmap[rx_idx] <= 1'b0;
                end else begin
                    // Keep any prior good copy if present, but request repair for this slot.
                    crc_fail_bitmap[rx_idx] <= 1'b1;
                end
            end

            if (epoch_active && epoch_tag_valid) begin
                if (epoch_complete && epoch_clean && epoch_aead_ok) begin
                    next_expected      <= epoch_start_seq + M;
                    ack_valid          <= 1'b1;
                    ack_seq            <= epoch_start_seq + M;
                    epoch_commit_pulse <= 1'b1;
                    epoch_active       <= 1'b0;
                end else if (epoch_complete && epoch_clean && !epoch_aead_ok) begin
                    // Authentication failure after all frames passed CRC: security event.
                    // Do not emit a reliability NAK that could become an oracle.
                    security_drop_pulse <= 1'b1;
                    epoch_active        <= 1'b0;
                end else begin
                    // Selective repair: ask only for absent or CRC-failed slots.
                    nak_valid          <= 1'b1;
                    nak_seq            <= epoch_start_seq;
                    nak_bitmap         <= repair_bitmap;
                    epoch_repair_pulse <= 1'b1;
                    // Keep epoch_active and retain good slots.
                end
            end
        end
    end

endmodule
