import sys
# Add the parent directory to sys.path to allow imports from CFG
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from CFG.cfg_builder import CFGBuilder
from CFG.cfg_node import CFGNode # Though not directly used, good for context
import ast

example_code = """
value=3
match value:
    case 1:
        print("You selected case 1.")
    case 2:
        print("You selected case 2.")
    case 3:
        print("You selected case 3.")
    case 4:
        print("You selected case 4.")
    case 5:
        print("You selected case 5.")
    case _:
        print("You selected an unknown case.")
print("Amirali Toori")

score=40
if score >= 90:
    print("Grade: A")
elif score >= 80:
    print("Grade: B")
elif score >= 70:
    print("Grade: C")
elif score >= 60:
    print("Grade: D")
else:
    print("Grade: F")
print("Amirali Toori")
x=30
x=20
"""

if __name__ == "__main__":
    builder = CFGBuilder()
    entry_node = builder.build_cfg(example_code, graph_name="example_test")

    if not entry_node:
        print("Failed to build CFG.")
        sys.exit(1)

    print("Generated Node Order (ID: First Statement):")
    # Sort nodes by ID for printing
    sorted_nodes = sorted(builder.nodes.values(), key=lambda node: node.id)
    for node in sorted_nodes:
        first_statement = node.statements[0] if node.statements else "EMPTY_NODE"
        print(f"{node.id}: {first_statement} (Type: {node.node_type})")

    # For debugging, print the DOT representation
    # dot_output = builder.to_dot()
    # print("\nDOT Output:\n")
    # print(dot_output)
