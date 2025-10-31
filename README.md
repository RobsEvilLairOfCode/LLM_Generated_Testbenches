## LLM Generated Finite State Machien Verilog Testbench Program

# Overview
This project is a python implementation of a methodology for generating finite state machine Verilog testbenches using an LLM. When supplied with the design file and design specification, the program will utilize an LLM (ChatGPT-5-mini by default) to generate and iteratively refine a testbench until it is able to cover all possible states and state transitions.

# How to use
In order to operate, start.py must be called with the Verilog design file and specification text file
```bash 
    python3 start.py ./demo_materials/design.v ./demo_materials/spec.txt
```
For the demo, the module is "myFSM" and the state variable to track is "state"

An example of what the LLM can generate is seen in "demo_materials/example_LLM_testbench.v"