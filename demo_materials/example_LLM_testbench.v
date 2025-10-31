module tb() ;
  reg in;
  reg clk;
  reg reset;
  wire out;

  // Instantiate DUT
  myFSM dut(.in(in), .clk(clk), .reset(reset), .out(out));

  // Clock generator
  initial begin
    clk = 0;
    forever #5 clk = ~clk; // 10 time-unit period
  end

  // First initial block must contain $dumpfile and $dumpvars
  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, tb);

    // init signals
    in = 0;
    reset = 0;

    // Allow initial conditions to settle
    #1;

    // At time of first posedge clk DUT state goes: 00 -> 01
    @(posedge clk);
    #1; // small settle
    $display("%0t: After 1st posedge: state=%b out=%b in=%b", $time, dut.state, out, in);

    // Pulse reset (posedge) while in state 01 to force 01 -> 00
    #1; reset = 1;
    #1; reset = 0;
    #1;
    $display("%0t: After reset pulse: state=%b out=%b in=%b", $time, dut.state, out, in);

    // Next posedge: 00 -> 01
    @(posedge clk);
    #1;
    $display("%0t: After next posedge: state=%b out=%b in=%b", $time, dut.state, out, in);

    // Change input while in 01 (force low state) to verify output stays 0
    in = 1;
    #2;
    $display("%0t: While in 01 (force low): state=%b out=%b in=%b", $time, dut.state, out, in);

    // Next posedge: 01 -> 10
    @(posedge clk);
    #1;
    $display("%0t: After posedge (01->10): state=%b out=%b in=%b", $time, dut.state, out, in);

    // Change input while in 10 (force high) to verify output stays 1
    in = 0;
    #2;
    $display("%0t: While in 10 (force high): state=%b out=%b in=%b", $time, dut.state, out, in);

    // Next posedge: 10 -> 00
    @(posedge clk);
    #1;
    $display("%0t: After posedge (10->00): state=%b out=%b in=%b", $time, dut.state, out, in);

    // Verify idle behavior: out should follow in
    in = 1;
    #2;
    $display("%0t: Idle behavior: state=%b out=%b in=%b", $time, dut.state, out, in);

    // Run a few more cycles to ensure no forbidden transitions occur
    repeat (3) begin
      @(posedge clk);
      #1;
      $display("%0t: Cycle check: state=%b out=%b in=%b", $time, dut.state, out, in);
      // toggle input to exercise output only-in-idle behavior when in state 00
      in = ~in;
    end

    $finish;
  end
endmodule