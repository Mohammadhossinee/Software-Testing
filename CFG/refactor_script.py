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
true_branch_replacement_code = """
        # True Branch
        true_branch_head = self.new_node(node_type="statement_block")
        source_node.branch_node = true_branch_head

        if ast_node.body:
            branch_loose_ends = self._process_statement_list_in_block(ast_node.body, [true_branch_head])
            loose_ends.extend(branch_loose_ends)
        else: # No body statements, true_branch_head itself is a loose end
            loose_ends.append(true_branch_head)
"""
false_branch_replacement_code = """
        # False Branch
        if ast_node.orelse:
            false_branch_head = self.new_node(node_type="statement_block")
            source_node.else_node = false_branch_head

            branch_loose_ends = self._process_statement_list_in_block(ast_node.orelse, [false_branch_head])
            loose_ends.extend(branch_loose_ends)
        else: # No 'orelse' clause for the If statement
            source_node.else_node = None
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
while_body_replacement_code = """
        # 2. Process loop body
        body_head_placeholder = self.new_node(node_type="statement_block")
        condition_node.branch_node = body_head_placeholder
        last_node_in_body_list: list[CFGNode] = []

        if ast_node.body:
            branch_loose_ends = self._process_statement_list_in_block(ast_node.body, [body_head_placeholder])
            if body_head_placeholder.next_node and body_head_placeholder.next_node != body_head_placeholder :
                condition_node.branch_node = body_head_placeholder.next_node
            last_node_in_body_list = branch_loose_ends
            if not branch_loose_ends or \
               (len(branch_loose_ends) == 1 and branch_loose_ends[0] == body_head_placeholder and not body_head_placeholder.statements and not body_head_placeholder.next_node):
                condition_node.branch_node = condition_node
                if body_head_placeholder.id in self.nodes: self.nodes.pop(body_head_placeholder.id, None)
                last_node_in_body_list = [condition_node]
        else:
            condition_node.branch_node = condition_node
            if body_head_placeholder.id in self.nodes: self.nodes.pop(body_head_placeholder.id, None)
            last_node_in_body_list = [condition_node]
"""
while_linking_adjustment_code_replace = """
        # Link all loose ends of the loop body robustly back to condition_node
        if last_node_in_body_list:
            for body_end_node in last_node_in_body_list:
                if body_end_node == condition_node:
                    continue
                if body_end_node.is_branch_point_no_else and body_end_node.else_node is None:
                     body_end_node.else_node = condition_node
                elif body_end_node.next_node is None and \\
                     not (body_end_node.branch_node or \\
                         (body_end_node.else_node and body_end_node.false_condition_label)):
                     body_end_node.next_node = condition_node
"""

# Stage 1: Insert Helper Function
lines = content.split('\n')
processed_lines = []
inserted_helper = False
simple_join_types_marker = "SIMPLE_JOIN_TYPES = (ast.Assign, ast.Expr, ast.Pass)"
for line_content in lines:
    processed_lines.append(line_content)
    if simple_join_types_marker in line_content and not inserted_helper:
        processed_lines.append("")
        for helper_line in new_block_processor_func_str.split('\n'):
            processed_lines.append("    " + helper_line)
        processed_lines.append("")
        inserted_helper = True
content = "\n".join(processed_lines)

# --- Stage 2: Modify visit_If ---
visit_if_marker = "def visit_If(self, ast_node: ast.If, source_node: CFGNode) -> Union[List[CFGNode], None]:"
true_branch_start_marker = "# True Branch"
false_branch_start_marker = "# False Branch"
visit_if_end_marker = "return loose_ends if loose_ends else []"
lines = content.split('\n')
processed_lines = []
in_visit_if_method = False
added_true_replacement = False
added_false_replacement = False
idx = 0
while idx < len(lines):
    line = lines[idx]
    line_consumed = False
    if not in_visit_if_method and visit_if_marker in line:
        in_visit_if_method = True
    if in_visit_if_method:
        if true_branch_start_marker in line and not added_true_replacement:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in true_branch_replacement_code.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            added_true_replacement = True
            line_consumed = True
            while idx < len(lines) and false_branch_start_marker not in lines[idx]:
                idx += 1
            continue
        elif false_branch_start_marker in line and added_true_replacement and not added_false_replacement:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in false_branch_replacement_code.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            added_false_replacement = True
            line_consumed = True
            while idx < len(lines) and visit_if_end_marker not in lines[idx]:
                idx += 1
            in_visit_if_method = False
            continue
    if not line_consumed:
        processed_lines.append(line)
    idx += 1
content = "\n".join(processed_lines)

# --- Stage 3: Modify visit_For ---
visit_for_marker = "def visit_For(self, ast_node: ast.For, source_node: CFGNode) -> Union[List[CFGNode], None]:"
for_body_process_start_marker = "# 4. Process loop body, starting from next_call_node"
for_linking_adjustment_code_search_marker = "# 5. Link last statement in loop body robustly back to loop_header_node"
for_next_major_block_marker = "# Added fix: Ensure all open-ended conditions"
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
    if in_visit_for_method:
        if for_body_process_start_marker in line and not added_for_body_replacement:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in for_body_replacement_code.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            added_for_body_replacement = True
            line_consumed = True
            while idx < len(lines) and for_linking_adjustment_code_search_marker not in lines[idx]:
                idx += 1
            continue
        elif for_linking_adjustment_code_search_marker in line and added_for_body_replacement and not adjusted_for_linking:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in for_linking_adjustment_code_replace.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            adjusted_for_linking = True
            line_consumed = True
            while idx < len(lines) and for_next_major_block_marker not in lines[idx]:
                idx += 1
            in_visit_for_method = False
            continue
    if not line_consumed:
        processed_lines.append(line)
    idx += 1
content = "\n".join(processed_lines)

# --- Stage 4: Modify visit_While ---
visit_while_marker = "def visit_While(self, ast_node: ast.While, source_node: CFGNode) -> Union[List[CFGNode], None]:"
while_body_process_start_marker = "# 2. Process loop body"
while_linking_adjustment_code_search_marker = "if last_node_in_body and last_node_in_body != condition_node :"
while_next_major_block_marker = "# Added fix: Ensure all open-ended conditions"
lines = content.split('\n')
processed_lines = []
in_visit_while_method = False
added_while_body_replacement = False
adjusted_while_linking = False
idx = 0
while idx < len(lines):
    line = lines[idx]
    line_consumed = False
    if not in_visit_while_method and visit_while_marker in line:
        in_visit_while_method = True
    if in_visit_while_method:
        if while_body_process_start_marker in line and not added_while_body_replacement:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in while_body_replacement_code.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            added_while_body_replacement = True
            line_consumed = True
            while idx < len(lines) and while_linking_adjustment_code_search_marker not in lines[idx]:
                idx += 1
            continue
        elif while_linking_adjustment_code_search_marker in line and added_while_body_replacement and not adjusted_while_linking:
            indentation = line[:len(line) - len(line.lstrip())]
            for rep_line in while_linking_adjustment_code_replace.strip('\n').split('\n'):
                processed_lines.append(indentation + rep_line)
            adjusted_while_linking = True
            line_consumed = True
            while idx < len(lines) and while_next_major_block_marker not in lines[idx]: # Skip to the line containing the marker
                idx += 1
            in_visit_while_method = False # Corrected typo from in_visit__while_method
            continue
    if not line_consumed:
        processed_lines.append(line)
    idx += 1
content = "\n".join(processed_lines)

with open("cfg_builder.py", "w") as f:
    f.write(content)

print("cfg_builder.py modified with new _process_statement_list_in_block and updated visit_If, visit_For, visit_While.")
if not inserted_helper: print("ERROR: Helper function _process_statement_list_in_block not inserted.")
if not added_true_replacement or not added_false_replacement: print("ERROR: visit_If not fully modified.")
if not added_for_body_replacement or not adjusted_for_linking: print("ERROR: visit_For not fully modified.")
if not added_while_body_replacement or not adjusted_while_linking: print("ERROR: visit_While not fully modified.")
