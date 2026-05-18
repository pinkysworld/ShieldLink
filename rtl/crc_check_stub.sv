// SPDX-License-Identifier: MIT
// CRC check stub (placeholder).
// Replace with a real CRC32 implementation if desired.

module crc_check_stub #(
    parameter int LAT = 1
) (
    input  logic clk,
    input  logic rst_n,
    input  logic valid_in,
    input  logic crc_ok_in,
    output logic valid_out,
    output logic crc_ok_out
);

    logic [LAT-1:0] vpipe;
    logic [LAT-1:0] opipe;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            vpipe <= '0;
            opipe <= '0;
        end else begin
            vpipe <= {vpipe[LAT-2:0], valid_in};
            opipe <= {opipe[LAT-2:0], crc_ok_in};
        end
    end

    assign valid_out  = vpipe[LAT-1];
    assign crc_ok_out = opipe[LAT-1];

endmodule
