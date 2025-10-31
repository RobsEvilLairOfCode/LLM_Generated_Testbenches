module myFSM(input in, input clk, input reset, output reg out);
  
  //IDLE = 00
  //LOW = 01
  //HIGH = 10


  reg[1:0] state = 2'b00;
  
  always begin
    #1;
      case (state)
      	2'b00: begin
          out = in;
        end
        2'b01: begin
          out = 1'b0;
        end
        2'b10: begin
          out = 1'b1;
        end
       default: begin
          out = in;
        end
      endcase
  end
  always @ (posedge clk) begin
    case (state)
      2'b00: begin
        state = 2'b01;
      end
      2'b01: begin
        state = 2'b10;
      end
      2'b10: begin
        state = 2'b00;
      end
      default: begin
        state = 2'b00;
      end
    endcase
  end
  
  always @ (posedge reset) begin
    state = 2'b00;
  end
endmodule