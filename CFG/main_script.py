"""
main_script.py - Main script for Control Flow Graph (CFG) Generation

This script serves as the entry point for generating a Control Flow Graph (CFG)
from Python code. It utilizes the CFGBuilder to parse the code, build the CFG,
and then uses Graphviz (if installed) to output a visual representation of the
CFG as a DOT file and a PNG image.

The script can be run directly, optionally taking a Python file path as a
command-line argument to process that file. If no argument is provided,
it processes a default sample code snippet.
"""

import sys  # For potential future CLI argument parsing
import subprocess  # For calling Graphviz dot
import os # Added

# Add the parent directory (project root) to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from CFG.cfg_builder import CFGBuilder # Changed to absolute import from package CFG
from for_to_while_converter import convert_for_to_while_code # Added import


def main():
    builder = CFGBuilder()

    output_basename = "cfg_output"
    code_to_process = """
# Control flow demonstration with for, while, and match-case (Python 3.10+)

# For loop example
for i in range(5):
    print("For loop iteration:", i)

# While loop example
count = 0
while count < 5:
    print("While loop count:", count)
    count += 1

# Switch case simulation using match-case
switch_case = 2

match switch_case:
    case 1:
        print("Switch case: Case 1 executed")
    case 2:
        print("Switch case: Case 2 executed")
    case 3:
        print("Switch case: Case 3 executed")
    case _:
        print("Switch case: Default case executed")
"""
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg.endswith(".py") and first_arg != "main_script.py":
            try:
                with open(first_arg, "r") as f:
                    code_to_process = f.read()
                output_basename = first_arg[:-3]
                print(f"Processing code from file: {first_arg}")
            except IOError as e:
                print(
                    f"Error reading file {first_arg}: {e}. Using default sample code."
                )
        elif first_arg != "main_script.py":
            output_basename = first_arg
            print(f"Using output basename: {output_basename}")

    # --- Modification starts ---
    print("\n--- Original Code ---")
    print(code_to_process)
    print("--- Converting for loops to while loops ---")
    code_to_process = convert_for_to_while_code(code_to_process)
    print("\n--- Code After For-Loop Conversion (Input to CFG) ---")
    print(code_to_process)
    print("----------------------------------------------------\n")
    # --- Modification ends ---

    # The following print statement is now redundant due to the new detailed prints.
    # print(
    #     f"Processing Python code:\n------------------------\n{code_to_process}\n------------------------\n"
    # )
    entry_node = builder.build_cfg(code_to_process)

    if entry_node:
        print("CFG generated successfully.")

        # Find and print prime paths
        prime_paths = builder.find_prime_paths()
        print("\n--- Prime Paths ---")
        if prime_paths:
            for i, path in enumerate(prime_paths):
                path_str = " -> ".join(str(node.id) for node in path)
                print(f"Path {i+1}: {path_str}")
        else:
            print("No prime paths found.")
        print("--------------------\n")

        dot_output = builder.to_dot()

        dot_filename = output_basename + ".dot"
        png_filename = output_basename + ".png"

        try:
            with open(dot_filename, "w") as f:
                f.write(dot_output)
            print(f"DOT output saved to {dot_filename}")

            try:
                cmd = ["dot", "-Tpng", dot_filename, "-o", png_filename]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"PNG image saved to {png_filename}")
            except FileNotFoundError:
                print(
                    "Graphviz 'dot' command not found. Please install Graphviz to generate PNG images."
                )
            except subprocess.CalledProcessError as e:
                print(f"Error generating PNG with dot: {e}")
                if e.stderr:
                    print(f"Dot stderr:\n{e.stderr}")

        except IOError as e:
            print(f"Error writing DOT file: {e}")
    else:
        print(
            "Failed to generate CFG. Check input code for syntax errors or other issues."
        )


if __name__ == "__main__":
    main()
