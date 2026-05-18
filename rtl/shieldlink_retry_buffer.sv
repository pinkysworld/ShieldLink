// SPDX-License-Identifier: MIT
// Simple parameterized retry buffer (TX-side) for go-back-N ARQ.

module shieldlink_retry_buffer #(
    parameter int N_WIN = 64,
    parameter int FRAME_BITS = 288*8
) (
    input  logic clk,
    input  logic rst_n,

    input  logic             wr_en,
    input  logic [$clog2(N_WIN)-1:0] wr_addr,
    input  logic [FRAME_BITS-1:0] wr_data,

    input  logic             rd_en,
    input  logic [$clog2(N_WIN)-1:0] rd_addr,
    output logic [FRAME_BITS-1:0] rd_data
);

    logic [FRAME_BITS-1:0] mem [0:N_WIN-1];

    always_ff @(posedge clk) begin
        if (wr_en) mem[wr_addr] <= wr_data;
        if (rd_en) rd_data <= mem[rd_addr];
    end

endmodule
