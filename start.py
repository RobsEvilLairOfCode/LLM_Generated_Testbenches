import os
import sys
import time
import subprocess
import shutil
from openai import OpenAI

# ---------------------------------------------------------------------
# Global constants
# ---------------------------------------------------------------------

#The work folder the program uses.
WORK_FOLDER = "./program_work_folder"

OPENAI_API_KEY_FILE_PATH = "./OpenAI_key.txt"
OPENAI_API_KEY = open(OPENAI_API_KEY_FILE_PATH,"r").read().strip()

MAX_ATTEMPTS = 10

#Testbench file path
TESTBENCH_FILE = "./testbench.sv"

# ---------------------------------------------------------------------
# Global state variables (populated during runtime)
# ---------------------------------------------------------------------

# Global variable to track ongoing conversation
conversation_history = []

#A list of Verilog files supplied by the user. If only one file is supplied via the command line
#Then the length of this list will be one.
input_code_files = []

#The file path of the specification file
input_spec_file = None

#Module names of the code files
modules = []

#The file path of the main module
main_module_file_path = None

#The name of the main module
main_module_name = None

#The names of the state that will be tracked
state_variable = None


#list of covered states
covered_states = []
#list of covered Transitions
covered_transitions = []

#list of transitions the testbench missed
missed_transitions = []

#text used in prompt
design_spec = ""
#text used in prompt
states = ""

states_list = []
#text used in prompt
blacklisted_states = ""

blacklisted_states_list = []

#text used in prompt
blacklisted_transitions = ""

blacklisted_transitions_list = []

all_transitions_list = []

possible_transitions_list = []

error = ""
def main():
    intro()
    #first, get the files from the command line and put them in the "input_code_files" array
    get_files()
    check_files_validity()
    extract_spec_file()
    open_work_folder()
    get_module_names()
    prompt_for_main_module()
    prompt_for_reg()
    insert_monitor_statement()
    import_design_spec()
    get_possible_transitions()
    intro_prompt = get_intro_prompt()
    print(intro_prompt)
    testbench = LLM(intro_prompt)

    attempts = 0
    begin = False
    while ((attempts < MAX_ATTEMPTS) and (len(missed_transitions) > 0)) or not begin:
        if not begin: begin = True
        print("[Info] Starting Attempt " + str(attempts))
        attempts = attempts + 1
        log(testbench)
        return_code = run_against_testbench()
        get_states_coverage()
        get_transitions_coverage()
        get_missed_transitions()
        print("Covered States "+str(covered_states))
        print("Covered Transitions "+str(covered_transitions))
        print("Attempts Boolean",str(attempts < MAX_ATTEMPTS))
        print("Transitions Boolean",str(len(missed_transitions) > 0))
        print("Code")
        print(testbench)
        if not (return_code == 0):
            print("[Error] Testbench contains syntax errors")
            error_prompt = get_error_prompt().replace("\\n","\n")
            print(error_prompt)
            reset()
            testbench = LLM(error_prompt)
            begin = False
            time.sleep(10)

        elif len(missed_transitions) > 0:
            retry_prompt = get_retry_prompt()
            reset()
            print(retry_prompt)
            testbench = LLM(retry_prompt)
            begin = False
            time.sleep(10)
        else:
            print(testbench)
            print(covered_transitions)
    print("[Info] End of Program")
    print("Attempts Boolean",str(attempts < MAX_ATTEMPTS))
    print("Transitions Boolean",str(len(missed_transitions) > 0))




def intro():
    print("Setting up...")
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

def get_files():
    #Get the arguments from the CLI
    args = sys.argv
    
    #If the user did not supply any arguments, then print out the usage tip and exit
    if(len(args) == 1):
       print("Usage: \'python3 start.py <code file> ...  <specification file>\'")
       os._exit(1)

    #The current working directory should be the directy that the file is currently in
    current_working_dir = os.getcwd()
    
    #Iterate through all of the arguments
    for arg_index in range(1,len(args),1):
        
        #Get the argument at the index
        arg = args[arg_index]
        
        #If the input starts with ~/ or /, then the specified file is outside of the scope of the CWD
        if(arg.find("~/") == 0 or arg.find("./") == 0 or arg.find("/") == 0):
            #the input filepath is standalone
            input_code_files.append(arg)
            
        else:
            #append the current working directory to the beginning of the filepath
            input_code_files.append(current_working_dir + "/" + arg)
        
    #end for loop
    
    #ensures the inputted files are all code files. I might upgrade this function later to actually
    #check the contents of each files to ensure they are proper and have no syntax errors.
def check_files_validity():
    global input_spec_file
    #iterate through the files...
    found_spec_file = False

    for file_path in input_code_files:
        #If the file ends with txt (spec file)
        if(file_path.endswith(".txt")):
            #The txt file should be the spec file
            if(found_spec_file == False):
                found_spec_file = True
            #There cannot be more that one spec file
            else:
                #print the error message and exit
                print("[Error] There should only be one specification file. Only one file in the command can have the extention /'.txt/'.")
                os._exit(4)
        
        #if the file the does not end with a .v, .sv or .txt
        if(not (file_path.endswith(".v") or file_path.endswith(".sv") or file_path.endswith(".txt"))):
            #print the error message and exit
            print("[Error] " + file_path + " is not a Verilog Code File or Text File. Exiting....")
            os._exit(2)
    #print an error and exit if the spec file is not found
    if(not found_spec_file):
        print("[Error] No spec file. One file in the command should have the the extention /'.txt/'. that include the design specification.")
        os._exit(3)

#Gets the spec file from input_code_files and seperates it into input_spec_file. Also removes it from the list
def extract_spec_file():
    global input_spec_file
    for file_path in input_code_files:
        if(file_path.endswith(".txt")):
            input_spec_file = file_path
            input_code_files.remove(file_path)
            break


def open_work_folder():
    #if the work folder exists, clear it out. if it doesn't make a new one
    if(os.path.exists(WORK_FOLDER)):
        for file_name in os.listdir(WORK_FOLDER):
            try:
                os.remove(WORK_FOLDER + "/" + file_name)
            except FileNotFoundError:
                #no further action needed
                1 == 1
    else:
        os.mkdir(WORK_FOLDER)
        
    #copy the code files in the list into the work folder.
    for file_path in input_code_files:
        
        #get the name of the file from the filepath
        file_path_split = file_path.split("/")
        file_name = file_path_split[len(file_path_split) - 1]
        
        #make a copy of the input code files into the work folder
        shutil.copy(file_path, WORK_FOLDER + "/" + file_name)

#A function that gets the names of the modules in the code files by reading passed the "module" keyword
def get_module_names():
    #iterate through the code files
    for file_path in input_code_files:
        #Load the contents of a file
        file = open(file_path,"r")
        #get the lines of the files
        file_lines = file.readlines()
        #iterate through the lines of find the keywork module
        for line in file_lines:

            #Pylance is sometimes unable to identify that line is intended to be a string
            line = str(line)

            #continue if the line is a comment
            if(line.startswith("//")):
                continue
            
            #Get the index of the module keyword,
            module_keyword_index = line.find("module ")
            
            #check if the module keyword exists
            if(module_keyword_index != -1):
                #Extract the module name
                module_name_index = module_keyword_index + len("module ")
                module_name = line[module_name_index: line.find("(")].strip()

                #Add the module name to the module list
                modules.append(module_name)
    
    if len(modules) == 0:
        print("[Error] Found no modules. Ensure that the code files are valid")
        os._exit(5)


#Get the name of the main module from the user
def prompt_for_main_module():
    
    print("Found Modules: ")
    for module_name in modules:
        print(module_name, end=" ")
        print()

    success = False
    while not success:
        user_input = input("Please specify which of these is the main module: ")
        
        if user_input in modules:
            success = True
            global main_module_name
            main_module_name = user_input
        if not success:
            print("Invalid module name, try again")
            print()
    
    global main_module_file_path
    main_module_file_path = input_code_files[modules.index(main_module_name)]
    
    
       
#Get the name of the state reg from the user
def prompt_for_reg():
    #Load the contents of a file
    file = open(main_module_file_path,"r")
    #get the lines of the files
    file_contents = file.read()

    success = False
    while not success:
        user_input = input("Please enter the name of the register that controls the state: ")
        
        if not(file_contents.find(user_input) == -1):
            success = True
            global state_variable
            state_variable = user_input
        if not success:
            print("Could not find "+ user_input +" in the code file, try again")
            print()

def insert_monitor_statement():
    #get the name of the file from the filepath
    file_path_split = main_module_file_path.split("/")
    file_name = file_path_split[len(file_path_split) - 1]

    #Load the contents of a original file
    file_read = open(main_module_file_path,"r")

    file_lines = file_read.readlines()

    file_contents = ""

    #removes all comments
    for line in file_lines:
        if(line.strip().startswith("//")):
            #ignore
            pass
        else:
            file_contents = file_contents + line


    #find where the module keyword is
    module_keyword_index = file_contents.find("module " + main_module_name)
    next_escape_char_index = file_contents[module_keyword_index:].find("\n")
    insert_index = module_keyword_index + next_escape_char_index

    montior_text = "\ninitial begin\n\t$monitor (\"[$monitor] time=%0t state_var=0x%0h\", $time, "+state_variable+");\nend\n"
    
    header_text = "//this file has been edited\n"

    new_file_contents = header_text + file_contents[:insert_index] + montior_text + file_contents[insert_index:]

    #write to the copied file
    file_write = open(WORK_FOLDER + "/" + file_name,"w")
    file_write.write(new_file_contents)

def run_against_testbench():
    #get a list of the files in the folder
    work_file_list = os.listdir(WORK_FOLDER)
    #version of the work file list cleared of pesky hidden files
    work_file_list_clean = []
    #remove hidden files
    for file_path_index in range(len(work_file_list)):
        file_name = work_file_list[file_path_index]
        #file_name = file_path[file_path.rfind("/") + 1:]
        if not file_name.startswith("."):
            work_file_list_clean.append(WORK_FOLDER + "/" + file_name)
        

    #run iverilog with the testbench and work files
    result = subprocess.run(["iverilog" , TESTBENCH_FILE] + work_file_list_clean, capture_output=True)

    print("iverilog return code: ",result.returncode)
    if(result.returncode == 0):
        #run the executable file and write the output to a text file
        result_2 = subprocess.run(["./a.out"],capture_output=True)

        output_results = open("./monitor_results.txt","w")
        output_results.write(str(result_2.stdout).replace("\\n","\n"))
        output_results.close()
    else:
        print("iverilog error:\n",result.stderr)
        global error 
        error = result.stderr

    return result.returncode

#gets the state and transition coverage from the recently outputted file
def get_states_coverage():
    monitor_file = open("./monitor_results.txt","r")
    monitor_lines = monitor_file.readlines()

    #remove lines without monitor
    for line_index in range(len(monitor_lines)):
        line = monitor_lines[line_index]
        if not line.strip().startswith("[$monitor]"):
            pass
        else:
            state_index = line.find("state_var=0x") + len("state_var=0x")
            global covered_states
            covered_states.append("0x" + line[state_index:state_index+1])

def get_transitions_coverage():
    global covered_transitions
    for index in range(len(covered_states) - 1):
        covered_transitions.append(str(covered_states[index]) +"->"+ str(covered_states[index + 1]))
    covered_transitions = list(set(covered_transitions))

def import_design_spec():
    design_spec_file = open(input_spec_file,"r")
    spec_file_text = design_spec_file.read().replace("\n","")

    spec_opening_tag = spec_file_text.find("<specification>")
    spec_closing_tag = spec_file_text.find("</specification>")

    if spec_opening_tag == -1:
        print("[Error] Could not find /'<specification>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    if spec_closing_tag == -1:
        print("[Error] Could not find /'</specification>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)
    
    states_opening_tag = spec_file_text.find("<state_list>")
    states_closing_tag = spec_file_text.find("</state_list>")

    if states_opening_tag == -1:
        print("[Error] Could not find /'<state_list>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    if states_closing_tag == -1:
        print("[Error] Could not find /'</state_list>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    b_states_opening_tag = spec_file_text.find("<blacklisted_states>")
    b_states_closing_tag = spec_file_text.find("</blacklisted_states>")

    if b_states_opening_tag == -1:
        print("[Error] Could not find /'<blacklisted_states>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    if b_states_closing_tag == -1:
        print("[Error] Could not find /'</blacklisted_states>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)
    
    b_transitions_opening_tag = spec_file_text.find("<blacklisted_transitions>")
    b_transitions_closing_tag = spec_file_text.find("</blacklisted_transitions>")

    if b_transitions_opening_tag == -1:
        print("[Error] Could not find /'<blacklisted_transitions>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    if b_transitions_closing_tag == -1:
        print("[Error] Could not find /'</blacklisted_transitions>/' tag in specification file. Ensure it is present and spelled correctly.")
        os._exit(6)

    global design_spec
    design_spec = spec_file_text[spec_opening_tag + len("<specification>"):spec_closing_tag]

    global states
    global states_list
    states = spec_file_text[states_opening_tag + len("<state_list>"):states_closing_tag]
    states_list = states.replace(" ","").split(",")
    for state_index in range(len(states_list)):
        state = states_list[state_index]
        states_list[state_index] = state[:state.find(":")]

    global blacklisted_states
    global blacklisted_states_list
    blacklisted_states = spec_file_text[b_states_opening_tag + len("<blacklisted_states>"):b_states_closing_tag]
    blacklisted_states_list = blacklisted_states.replace(" ","").split(",")

    global blacklisted_transitions
    global blacklisted_transitions_list
    blacklisted_transitions = spec_file_text[b_transitions_opening_tag + len("<blacklisted_transitions>"):b_transitions_closing_tag]
    blacklisted_transitions_list = blacklisted_transitions.replace(" ","").split(",")

def get_possible_transitions():
    global all_transitions_list
    #highest state id number
    highest_value = 0
    for state in states_list:
        i = int(state[2:],16)
        if i > highest_value:
            highest_value = i
    
    #find the smallest power of 2 that is higher that highest value
    max_value = 0
    for i in range(10):
        if pow(2,i) > highest_value:
            max_value = pow(2,i) - 1
            break
    

    for i in range(max_value + 1):
        for j in range(max_value + 1):
            if(i == j): continue
            all_transitions_list.append(hex(i) + "->" + hex(j))
    

    #removes blackliisted states and transitions
    for i in range(len(all_transitions_list)).__reversed__():
        value = all_transitions_list[i]
        should_continue = False
        for blacklisted_state in blacklisted_states_list:
            if( not (value.find(blacklisted_state) == -1)):
                del all_transitions_list[i]
                should_continue = True
                break
        
        if should_continue: continue

        for blacklisted_transition in blacklisted_transitions_list:
            if(value == blacklisted_transition):
                del all_transitions_list[i]
                should_continue = True
                break

        if should_continue: continue
    
    global possible_transitions_list
    possible_transitions_list = all_transitions_list

def reset():
    global covered_states
    global covered_transitions
    global missed_transitions
    covered_states = []
    covered_transitions = []
    missed_transitions = []

def get_missed_transitions():
    global missed_transitions
    missed_transitions = all_transitions_list

    for transition_index in range(len(missed_transitions)).__reversed__():
        transition = missed_transitions[transition_index]
        for covered_transition in covered_transitions:
            if transition == covered_transition:
                del missed_transitions[transition_index]
    
    print("Missed Transitions " + str(missed_transitions))

def get_intro_prompt():
    intro_prompt_file_path = "./opening_prompt.txt"
    intro_prompt_file = open(intro_prompt_file_path,"r")
    intro_prompt_text = intro_prompt_file.read()

    code_file = open(main_module_file_path,"r")
    code_file_text = code_file.read()

    intro_prompt_text = intro_prompt_text.replace("<design_spec>",design_spec)

    intro_prompt_text = intro_prompt_text.replace("<state_reg_name>",state_variable)

    intro_prompt_text = intro_prompt_text.replace("<state_list>",states)

    intro_prompt_text = intro_prompt_text.replace("<transition_list>",str(possible_transitions_list).replace("[","").replace("]",""))

    intro_prompt_text = intro_prompt_text.replace("<blacklisted_states>",blacklisted_states)

    intro_prompt_text = intro_prompt_text.replace("<blacklisted_transitions>",blacklisted_transitions)

    intro_prompt_text = intro_prompt_text.replace("<module_code>",code_file_text)


    return intro_prompt_text

def get_retry_prompt():
    retry_prompt_file_path = "./retry_prompt.txt"
    retry_prompt_file = open(retry_prompt_file_path,"r")
    retry_prompt_text = retry_prompt_file.read()

    retry_prompt_text = retry_prompt_text.replace("<state_reg_name>",state_variable)

    retry_prompt_text = retry_prompt_text.replace("<expected_transitions>",str(missed_transitions).replace("[","").replace("]",""))

    return retry_prompt_text

def get_error_prompt():
    error_prompt_file_path = "./error_prompt.txt"
    error_prompt_file = open(error_prompt_file_path,"r")
    error_prompt_text = error_prompt_file.read()

    error_prompt_text = error_prompt_text.replace("<error>",str(error))

    return error_prompt_text

#Sends the LLM a message
def LLM(msg, llm="gpt-5-mini-2025-08-07"):
    global conversation_history
    client = OpenAI()

    # Add the user's message to the conversation
    conversation_history.append({"role": "user", "content": msg})

    chat_completion = client.chat.completions.create(
        model=llm,
        messages=conversation_history
    )

    reply = chat_completion.choices[0].message.content

    reply = content_of_GPT_compleition(reply)

    # Append assistant's reply to the conversation
    conversation_history.append({"role": "assistant", "content": reply})

    return reply

def content_of_GPT_compleition(completion=None):
    #completion = SAMPLE_COMPLETION
    
    #cuts out the content and fixes the formatting
    if completion.find("```verilog") > -1:
        content = substring(completion,"```verilog","\'").replace("\\n","\n").replace("\\t","\t").replace("```","")#.replace("verilog","").replace("vhdl","")
    else:
        content = substring(completion,"content=\'","\'").replace("\\n","\n").replace("\\t","\t").replace("```","")#.replace("verilog","").replace("vhdl","")
    print("Before \n" + content)
    content = substring(completion,"module tb()","endmodule").replace("\\n","\n").replace("\\t","\t").replace("```","")#.replace("verilog","").replace("vhdl","")
    content = "module tb() "+ content+"\nendmodule"
    print("After \n" + content)
    content = content.replace("\\n","\n").replace("\\t","\t").replace("```","").replace("\\'","\'").replace("verilog","").replace("vhdl","").replace("systemverilog","")
    return content 

#gets the portion of the string between two given phrases
def substring(input,phrase1,phrase2):
    text_boundary1 = input.find(phrase1) + len(phrase1)
    input = input[text_boundary1:]
    text_boundary2 = input.find(phrase2)
    input = input[:text_boundary2].strip()
    return input

def append_to_file(text,name,dir):
    try:
        with open(dir + '/' + name,"w") as output_file:
            output_file.write(text)
    except (IOError, OSError) as e:
        print("Exception Occurred when writing to file. Is the file write-protected")
        print()

def log(text):
    append_to_file(text,"testbench.sv","./")

main()