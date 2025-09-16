from CFG.cfg_builder import CFGBuilder

code = """
c = "L"
y = 0 # Initialize y
match c:
    case 'N':
        y = 25
        print("Case N")
    case 'Y':
        y = 50
        print("Case Y")
    case 'M':
        y = 75
        print("Case M")
    case _:
        y = 0  # Default case
        print("Default Case")
print(y) # Statement after match
"""

builder = CFGBuilder()
cfg = builder.build_cfg(code)
if cfg:
    dot_output = builder.to_dot()
    with open("match_case_example.dot", "w") as f:
        f.write(dot_output)
    print("match_case_example.dot generated successfully.")
else:
    print("Failed to build CFG for the match-case example.")
