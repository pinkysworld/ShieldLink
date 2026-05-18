// SPDX-License-Identifier: MIT
// Ascon AEAD interface stub (placeholder).
// Replace this with a reference Ascon-128a RTL core for FPGA prototyping.
// The stub models latency only: after LAT cycles, it asserts 'valid_out' and
// passes through aead_ok_in.

module ascon_aead_stub #(
    parameter int LAT = 8
) (
    input  logic clk,
    input  logic rst_n,
    input  logic valid_in,
    input  logic aead_ok_in,
    output logic valid_out,
    output logic aead_ok_out
);

    logic [LAT-1:0] vpipe;
    logic [LAT-1:0] opipe;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vpipe <= '0;
            opipe <= '0;
        end else begin
            vpipe <= {vpipe[LAT-2:0], valid_in};
            opipe <= {opipe[LAT-2:0], aead_ok_in};
        end
    end

    assign valid_out   = vpipe[LAT-1];
    assign aead_ok_out = opipe[LAT-1];

endmodule
