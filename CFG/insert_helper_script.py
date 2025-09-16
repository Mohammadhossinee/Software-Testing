import ast

# Read cfg_builder.py
with open("cfg_builder.py", "r") as f:
    content = f.read()

# Helper string for the new body processing logic
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

lines = content.split('\n')
processed_lines = []
inserted_helper = False
# Ensure this marker exactly matches the line in cfg_builder.py
simple_join_types_marker = "SIMPLE_JOIN_TYPES = (ast.Assign, ast.Expr, ast.Pass)" # No leading spaces for matching with strip()

for line_content in lines:
    processed_lines.append(line_content)
    # Use strip() for robust matching against the content of the line
    if simple_join_types_marker == line_content.strip() and not inserted_helper:
        processed_lines.append("")
        for helper_line in new_block_processor_func_str.split('\n'):
            processed_lines.append("    " + helper_line) # Prepend 4 spaces for class method indent
        processed_lines.append("")
        inserted_helper = True
content = "\n".join(processed_lines)

with open("cfg_builder.py", "w") as f:
    f.write(content)

if inserted_helper:
    print("Helper function _process_statement_list_in_block inserted successfully.")
else:
    print("ERROR: Helper function _process_statement_list_in_block not inserted. Marker not found or other issue.")
    # For debugging, print if marker was found in general content
    if any(simple_join_types_marker in l.strip() for l in lines): # Check if marker (without leading space) is in any stripped line
        print(f"DEBUG: Marker '{simple_join_types_marker}' was found in the file content (when stripped).")
    else:
        print(f"DEBUG: Marker '{simple_join_types_marker}' was NOT found in the file content (even when stripped).")
