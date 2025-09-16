# This script re-opens and verifies cfg_builder.py based on the previous overwrite
# It's essentially the verification part of the user's last script.

with open("cfg_builder.py", "r") as f:
    final_code = f.read()

errors = []
if "_process_statement_list_in_block" not in final_code:
    errors.append("'_process_statement_list_in_block' method is missing.")
if "initial_node_ids_in_for = set(self.nodes.keys())" not in final_code: # Check for part 1 of For loop fix
    errors.append("'initial_node_ids_in_for' is missing from visit_For.")
# Corrected check for the specific line defining newly_created_node_ids_in_body for "For"
if "newly_created_node_ids_in_body = current_node_ids_after_body - initial_node_ids_in_for" not in final_code:
    errors.append("'newly_created_node_ids_in_body = current_node_ids_after_body - initial_node_ids_in_for' logic is missing from visit_For.")
if "initial_node_ids_in_while = set(self.nodes.keys())" not in final_code: # Check for part 1 of While loop fix
    errors.append("'initial_node_ids_in_while' is missing from visit_While.")
# Corrected check for the specific line defining newly_created_node_ids_in_while_body for "While"
if "newly_created_node_ids_in_while_body = current_node_ids_after_body - initial_node_ids_in_while" not in final_code:
    errors.append("'newly_created_node_ids_in_while_body = current_node_ids_after_body - initial_node_ids_in_while' logic is missing from visit_While.")
if "def visit_If(self, ast_node: ast.If, source_node: CFGNode)" not in final_code: # Check for presence of visit_If using a more specific part of its signature
    errors.append("visit_If method is missing or signature incorrect.")
if "def to_dot(self) -> str:" not in final_code:
    errors.append("to_dot method is missing or signature incorrect.")


if not errors:
    print("Verification successful: Loop fix and helper method appear to be correctly included.")
else:
    print("Verification FAILED for the combined initial setup:")
    for error in errors:
        print(f"- {error}")
