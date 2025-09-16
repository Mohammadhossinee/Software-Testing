import ast
import re
from typing import List, Union, Optional

# Step 1: Get current content of cfg_builder.py
with open("cfg_builder.py", "r") as f:
    current_cfg_builder_content = f.read()

# Step 2: Define the new visit_While method
new_visit_while_method_str = """
    def visit_While(self, ast_node: ast.While, source_node: CFGNode) -> Union[List[CFGNode], None]:
        if source_node is None: return None

        # 1. Create condition node (loop header)
        condition_node = self.new_node(statements=[ast.unparse(ast_node.test).strip()], node_type="condition")
        if source_node.node_type == "condition" and source_node.is_branch_point_no_else and source_node.else_node is None:
            source_node.else_node = condition_node
        elif not (source_node.branch_node or (source_node.else_node and source_node.false_condition_label)):
            source_node.next_node = condition_node

        condition_node.true_condition_label = "loop body"
        condition_node.false_condition_label = "loop exit"
        condition_node.is_branch_point_no_else = not ast_node.orelse

        initial_node_ids_in_while = set(self.nodes.keys()) # LOOP FIX PART 1 - Stays here

        # 2. Process loop body
        body_head_placeholder = self.new_node(node_type="statement_block")
        condition_node.branch_node = body_head_placeholder

        body_loose_ends: list[CFGNode] = []
        if ast_node.body:
            body_loose_ends = self._process_statement_list_in_block(ast_node.body, [body_head_placeholder])

            # If body_head_placeholder was used as the initial source for _process_statement_list_in_block,
            # and the block was empty or only contained pass, body_loose_ends might just be [body_head_placeholder].
            # If body_head_placeholder is still linked from condition_node and is empty, make condition_node loop to itself.
            if condition_node.branch_node == body_head_placeholder and not body_head_placeholder.statements and not body_head_placeholder.next_node:
                 # This implies that _process_statement_list_in_block did not attach any actual statements to body_head_placeholder
                 # nor did it link body_head_placeholder to any subsequent node from the body.
                 # This can happen if ast_node.body was empty, or contained only 'pass' that didn't advance.
                 self.nodes.pop(body_head_placeholder.id, None) # Remove empty placeholder
                 condition_node.branch_node = condition_node # Loop directly back
                 body_loose_ends = [condition_node] # The condition itself is the "end" of this empty path
            elif not body_loose_ends and body_head_placeholder.id in self.nodes and condition_node.branch_node == body_head_placeholder:
                 # Path terminated in body, and placeholder is still the branch_node.
                 # This means the body started but terminated (e.g. return), and placeholder is now an empty unlinked node.
                 self.nodes.pop(body_head_placeholder.id, None)
                 # body_loose_ends remains empty, indicating termination.
        else: # No ast_node.body (empty while body)
            self.nodes.pop(body_head_placeholder.id, None) # Remove placeholder
            condition_node.branch_node = condition_node # Empty body loops directly to condition
            body_loose_ends = [condition_node] # The condition itself is the "end"

        # Link all loose ends of the loop body back to condition_node
        if body_loose_ends:
            for body_end_node in body_loose_ends:
                if body_end_node == condition_node:
                    continue
                if body_end_node.is_branch_point_no_else and body_end_node.else_node is None:
                     body_end_node.else_node = condition_node
                elif body_end_node.next_node is None and \\
                     not (body_end_node.branch_node or \\
                         (body_end_node.else_node and body_end_node.false_condition_label)):
                     body_end_node.next_node = condition_node

        # LOOP FIX PART 2 (Ensure open conditions *created within* the body also loop back their else path)
        current_node_ids_after_body = set(self.nodes.keys())
        newly_created_node_ids_in_while_body = current_node_ids_after_body - initial_node_ids_in_while
        for node_id in newly_created_node_ids_in_while_body:
            node_in_body = self.nodes.get(node_id)
            # is_a_main_body_loose_end = node_in_body in body_loose_ends # Not strictly needed with current logic

            if node_in_body and \\
               node_in_body.node_type == "condition" and \\
               node_in_body.is_branch_point_no_else and \\
               node_in_body.else_node is None:
                # If this node's else_node is still None (wasn't set by being a main body_end_node), set it.
                node_in_body.else_node = condition_node # Loop back to the while condition
        # LOOP FIX PART 2 (End)

        # 3. Handle orelse block
        nodes_after_loop: List[CFGNode] = []
        if ast_node.orelse:
            orelse_head_placeholder = self.new_node(node_type="statement_block")
            condition_node.else_node = orelse_head_placeholder

            orelse_loose_ends = self._process_statement_list_in_block(ast_node.orelse, [orelse_head_placeholder])

            if orelse_loose_ends == [orelse_head_placeholder] and not orelse_head_placeholder.statements and orelse_head_placeholder.next_node is None and orelse_head_placeholder.branch_node is None:
                self.nodes.pop(orelse_head_placeholder.id, None)
                condition_node.else_node = None
                nodes_after_loop.append(condition_node)
            elif orelse_loose_ends:
                 nodes_after_loop.extend(orelse_loose_ends)
            else:
                 if condition_node.else_node == orelse_head_placeholder and not orelse_head_placeholder.statements:
                    self.nodes.pop(orelse_head_placeholder.id, None)
                    condition_node.else_node = None
                    nodes_after_loop.append(condition_node)
        else:
            condition_node.else_node = None
            nodes_after_loop.append(condition_node)

        return nodes_after_loop
"""

# Step 3: Replace the old visit_While method
pattern_while = re.compile(r"    def visit_While\(self, ast_node: ast.While, source_node: CFGNode\) -> Union\[List\[CFGNode\], None]:.*?(?=^    def visit_FunctionDef|^    def to_dot|^\Z)", re.DOTALL | re.MULTILINE)

replacement_with_new_visit_while, num_replacements = pattern_while.subn(new_visit_while_method_str.rstrip() + "\n\n", current_cfg_builder_content, count=1)

if num_replacements == 0:
    print("ERROR: Original visit_While not found by regex or not replaced.")
    with open("cfg_builder.py", "w") as f:
        f.write(current_cfg_builder_content)
    print("Wrote baseline content back to cfg_builder.py due to replacement error.")
    exit()
else:
    print("visit_While method replaced by regex.")


# Step 4: Write the new full content to cfg_builder.py
with open("cfg_builder.py", "w") as f:
    f.write(replacement_with_new_visit_while)

print("cfg_builder.py has been updated: visit_While refactored.")

# Verification
with open("cfg_builder.py", "r") as f:
    final_code = f.read()

errors = []
if "_process_statement_list_in_block(ast_node.body, [body_head_placeholder])" not in final_code:
    errors.append("visit_While does not call _process_statement_list_in_block for ast_node.body.")
if "_process_statement_list_in_block(ast_node.orelse, [orelse_head_placeholder])" not in final_code:
    errors.append("visit_While does not call _process_statement_list_in_block for ast_node.orelse.")
if "initial_node_ids_in_while = set(self.nodes.keys())" not in final_code:
    errors.append("Loop fix (initial_node_ids_in_while) is missing from visit_While.")
if "newly_created_node_ids_in_while_body = current_node_ids_after_body - initial_node_ids_in_while" not in final_code:
    errors.append("Loop fix part 2 (newly_created_node_ids_in_while_body) is missing from visit_While.")
if "def visit_For(self, ast_node: ast.For, source_node: CFGNode)" not in final_code: # Check previous methods
    errors.append("visit_For method is missing (file truncation check).")

if not errors:
    print("Verification successful: visit_While refactored and other key parts intact.")
else:
    print("Verification FAILED for visit_While refactoring:")
    for error in errors:
        print(f"- {error}")
