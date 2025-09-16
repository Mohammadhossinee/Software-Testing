import ast

# Read cfg_builder.py (which should now contain the helper method)
with open("cfg_builder.py", "r") as f:
    content = f.read()

# --- Code string definitions for visit_For modification ---
for_body_replacement_code = """
        # 4. Process loop body, starting from next_call_node
        last_node_in_body_list: list[CFGNode] = []
        if ast_node.body:
            last_node_in_body_list = self._process_statement_list_in_block(ast_node.body, [next_call_node])
        else:
            last_node_in_body_list = [next_call_node]
"""
for_linking_adjustment_code_replace = """
        # 5. Link all loose ends of the loop body robustly back to loop_header_node
        if last_node_in_body_list:
            for body_end_node in last_node_in_body_list:
                if body_end_node.is_branch_point_no_else and body_end_node.else_node is None:
                     body_end_node.else_node = loop_header_node
                elif body_end_node.next_node is None and \\
                     not (body_end_node.branch_node or \\
                         (body_end_node.else_node and body_end_node.false_condition_label)):
                     body_end_node.next_node = loop_header_node
"""

# --- Logic to Modify visit_For ---
visit_for_marker = "def visit_For(self, ast_node: ast.For, source_node: CFGNode) -> Union[List[CFGNode], None]:"
for_body_process_start_marker = "# 4. Process loop body, starting from next_call_node"
for_linking_adjustment_code_search_marker = "# 5. Link last statement in loop body robustly back to loop_header_node"
# This is the start of the "Added fix" block (loop-internal if handling) which should follow the linking logic.
for_end_of_linking_marker = "# Added fix: Ensure all open-ended conditions"

lines = content.split('\n')
processed_lines = []
in_visit_for_method = False
added_for_body_replacement = False
adjusted_for_linking = False
idx = 0

while idx < len(lines):
    line = lines[idx]
    line_consumed = False

    if not in_visit_for_method and visit_for_marker in line:
        in_visit_for_method = True
        # Fall through to append this line via 'if not line_consumed'

    if in_visit_for_method:
        if for_body_process_start_marker in line and not added_for_body_replacement:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in for_body_replacement_code.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            added_for_body_replacement = True
            line_consumed = True
            # Advance idx to the line that IS for_linking_adjustment_code_search_marker
            while idx < len(lines) and for_linking_adjustment_code_search_marker not in lines[idx]:
                idx += 1
            # Loop continues; idx is now set for the next iteration, pointing at the target marker.
            continue
        elif for_linking_adjustment_code_search_marker in line and added_for_body_replacement and not adjusted_for_linking:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in for_linking_adjustment_code_replace.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            adjusted_for_linking = True
            line_consumed = True
            # Advance idx to the line that IS for_end_of_linking_marker (start of the next logical block)
            while idx < len(lines) and for_end_of_linking_marker not in lines[idx]:
                idx += 1
            # All specific replacements for visit_For are done.
            # The rest of the method (including for_end_of_linking_marker line and orelse part)
            # will be handled by the default append.
            in_visit_for_method = False # Signal that specific processing for this method is complete.
            continue

    if not line_consumed:
        processed_lines.append(line)
    idx += 1
content = "\n".join(processed_lines)

with open("cfg_builder.py", "w") as f:
    f.write(content)

if added_for_body_replacement and adjusted_for_linking:
    print("SUCCESS: visit_For method appears to be modified correctly.")
else:
    print("ERROR: visit_For method not fully modified.")
    if not added_for_body_replacement: print(" - Body replacement failed.")
    if not adjusted_for_linking: print(" - Linking adjustment failed.")
