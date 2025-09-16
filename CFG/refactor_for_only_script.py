import ast

# Read cfg_builder.py
with open("cfg_builder.py", "r") as f:
    content = f.read()

# --- ALL CODE STRING DEFINITIONS ---
new_block_processor_func_str = """
    def _process_statement_list_in_block(self, stmts_list: list[ast.AST], initial_sources_in_block: list[CFGNode]) -> list[CFGNode]:
        active_block_sources = list(initial_sources_in_block)
        if not active_block_sources:
            return []

        for stmt_idx, current_ast_stmt in enumerate(stmts_list):
            if not active_block_sources:
                break

            current_stmt_processing_sources = list(active_block_sources)
            active_block_sources = []

            if len(current_stmt_processing_sources) > 1:
                is_simple_join_target = isinstance(current_ast_stmt, self.__class__.SIMPLE_JOIN_TYPES)

                if is_simple_join_target:
                    description = ast.unparse(current_ast_stmt).strip()
                    node_type_str = "statement_block"
                    if isinstance(current_ast_stmt, ast.Assign): node_type_str = "assignment"
                    elif isinstance(current_ast_stmt, ast.Expr):
                        node_type_str = "expression_statement"
                        if isinstance(current_ast_stmt.value, ast.Call): node_type_str = "function_call"
                    elif isinstance(current_ast_stmt, ast.Pass): node_type_str = "pass_statement"

                    join_node_for_stmt = self.new_node(statements=[description], node_type=node_type_str)
                    for s_node in current_stmt_processing_sources:
                        self._link_predecessor_to_successor(s_node, join_node_for_stmt)

                    active_block_sources.append(join_node_for_stmt)
                    continue
                else:
                    merge_node_for_stmt = self.new_node(statements=[], node_type="merge_point")
                    for s_node in current_stmt_processing_sources:
                        self._link_predecessor_to_successor(s_node, merge_node_for_stmt)
                    current_stmt_processing_sources = [merge_node_for_stmt]

            for source_node_for_stmt in current_stmt_processing_sources:
                if source_node_for_stmt is None: continue

                path_results = self.visit(current_ast_stmt, source_node_for_stmt)

                if path_results:
                    active_block_sources.extend(path_results)

                if source_node_for_stmt.node_type == "condition" and \\
                   source_node_for_stmt.is_branch_point_no_else and \\
                   source_node_for_stmt.else_node is None:
                    if source_node_for_stmt not in active_block_sources:
                        active_block_sources.append(source_node_for_stmt)

            active_block_sources = [n for n in active_block_sources if n is not None]

        return active_block_sources
"""
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

# Stage 1: Insert Helper Function
lines = content.split('\n')
processed_lines_stage1 = []
inserted_helper = False
simple_join_types_marker = "SIMPLE_JOIN_TYPES = (ast.Assign, ast.Expr, ast.Pass)"
for line_content in lines:
    processed_lines_stage1.append(line_content)
    if simple_join_types_marker in line_content and not inserted_helper:
        processed_lines_stage1.append("")
        for helper_line in new_block_processor_func_str.split('\n'):
            processed_lines_stage1.append("    " + helper_line)
        processed_lines_stage1.append("")
        inserted_helper = True
content = "\n".join(processed_lines_stage1)

# --- Stage 3: Modify visit_For --- (Skipping Stage 2 for visit_If)
visit_for_marker = "def visit_For(self, ast_node: ast.For, source_node: CFGNode) -> Union[List[CFGNode], None]:"
for_body_process_start_marker = "# 4. Process loop body, starting from next_call_node"
for_linking_adjustment_code_search_marker = "# 5. Link last statement in loop body robustly back to loop_header_node"
for_next_major_block_marker = "# Added fix: Ensure all open-ended conditions"

lines = content.split('\n')
processed_lines_stage3 = []
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
                processed_lines_stage3.append(indentation + rep_line)
            added_for_body_replacement = True
            line_consumed = True # The current line (marker) is consumed by the replacement.
            # Advance idx to the line that IS for_linking_adjustment_code_search_marker
            while idx < len(lines) and for_linking_adjustment_code_search_marker not in lines[idx]:
                idx += 1
            # idx is now on the target line or at the end. The outer loop will handle processing lines[idx].
            continue
        elif for_linking_adjustment_code_search_marker in line and added_for_body_replacement and not adjusted_for_linking:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in for_linking_adjustment_code_replace.strip('\n').split('\n'):
                processed_lines_stage3.append(indentation + rep_line)
            adjusted_for_linking = True
            line_consumed = True # The current line (marker) is consumed.
            # Advance idx to the line that IS for_next_major_block_marker
            while idx < len(lines) and for_next_major_block_marker not in lines[idx]:
                idx += 1
            # idx is now on the target line or at the end.
            # Explicitly add this target line because in_visit_for_method will be false next,
            # and we want to ensure this line is included before general processing takes over.
            if idx < len(lines): # Check if marker was found
                 processed_lines_stage3.append(lines[idx]) # Add the for_next_major_block_marker line itself
                 # This line is now "consumed" in terms of special handling for visit_For

            in_visit_for_method = False # Done with specific replacements for visit_For for this script
            idx +=1 # Manually advance idx because we are appending lines[idx] and then continuing
            continue

    if not line_consumed:
        processed_lines_stage3.append(line)
    idx += 1
content = "\n".join(processed_lines_stage3)

with open("cfg_builder.py", "w") as f:
    f.write(content)

print("cfg_builder.py modified with helper and visit_For.")
if not inserted_helper: print("ERROR: Helper function not inserted.")
if not added_for_body_replacement or not adjusted_for_linking: print("ERROR: visit_For not fully modified.")
else: print("SUCCESS: visit_For appears to be modified correctly.")
