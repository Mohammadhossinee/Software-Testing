import ast
from typing import List, Optional, Tuple, Union, Dict

from CFG.cfg_node import CFGNode # Import CFGNode from its actual file
# from .ast_utils import negate_condition_ast # Will be imported within methods that need it

class CFGBuilder(ast.NodeVisitor):
    def __init__(self):
        self.nodes: Dict[int, CFGNode] = {}
        self.current_id: int = 0
        self.entry_node: Optional[CFGNode] = None
        self.exit_node: Optional[CFGNode] = None

        self._loop_exit_stack: List[CFGNode] = []
        self._loop_start_stack: List[CFGNode] = []

    def _new_id(self) -> int:
        self.current_id += 1
        return self.current_id

    def new_node(self, statements: Optional[List[str]] = None, node_type: str = "statement_block") -> CFGNode:
        node_id = self._new_id()
        node = CFGNode(node_id, statements=statements, node_type=node_type)
        self.nodes[node_id] = node
        return node

    def _link_predecessor_to_successor(self, pred_node: Optional[CFGNode], succ_node: Optional[CFGNode], link_type: str = "next"):
        if not pred_node or not succ_node:
            return
        # Prevent linking FROM terminal nodes
        if pred_node.node_type in ("return_statement", "break_statement", "continue_statement", "raise_statement"):
            return

        if link_type == "next":
            pred_node.next_node = succ_node
        elif link_type == "branch":
            pred_node.branch_node = succ_node
        elif link_type == "else":
            pred_node.else_node = succ_node

    def build(self, ast_root: ast.AST, graph_name: str = "cfg") -> Dict[int, CFGNode]:
        self.nodes = {}
        self.current_id = 0
        self._loop_exit_stack = []
        self._loop_start_stack = []
        self.exit_node = None

        self.entry_node = self.new_node(statements=[f"Entry to {graph_name}"], node_type="entry")

        if isinstance(ast_root, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            self._process_statement_list_in_block(ast_root.body, [self.entry_node])
        else:
            self.visit(ast_root, self.entry_node)

        self._optimize_empty_blocks()
        self._renumber_nodes() # New call added here
        return self.nodes

    def build_cfg(self, code_string: str, graph_name: str = "cfg") -> Optional[CFGNode]:
        from .ast_utils import parse_code_to_ast

        ast_tree = parse_code_to_ast(code_string)
        if ast_tree is None:
            print(f"Error: Could not parse code string into AST for {graph_name}.")
            return None
        self.build(ast_tree, graph_name=graph_name)
        return self.entry_node

    def _process_statement_list_in_block(self, stmt_list: List[ast.AST], current_source_nodes: List[CFGNode]) -> List[CFGNode]:
        active_source_nodes = list(current_source_nodes)
        skip_next_iteration = False

        for stmt_idx, stmt_ast in enumerate(stmt_list):
            if skip_next_iteration:
                skip_next_iteration = False
                continue

            if not active_source_nodes:
                 # All prior paths terminated or no initial sources.
                 # If subsequent stmts in stmt_list exist, they are unreachable from original current_source_nodes.
                 # The main build() method is responsible for iterating all top-level statements if ast_root is Module.
                 # This function correctly returns empty list if all paths from current_source_nodes terminate.
                break

            current_iteration_next_active_sources = []

            live_sources_for_current_stmt = []
            if active_source_nodes:
                for source_node in active_source_nodes:
                    if source_node.node_type in ("return_statement", "break_statement", "continue_statement", "raise_statement"):
                        current_iteration_next_active_sources.append(source_node)
                    else:
                        live_sources_for_current_stmt.append(source_node)

            if not live_sources_for_current_stmt:
                # All paths leading to this point terminated.
                # Any remaining terminal nodes from previous iterations are carried over.
                active_source_nodes = list(dict.fromkeys(current_iteration_next_active_sources))
                continue # Effectively, remaining stmts in this list are unreachable from these specific prior paths.

            # Determine if current statement is If/Match and has a successor
            is_if_match_with_successor = False
            successor_ast_node = None
            if isinstance(stmt_ast, (ast.If, ast.Match)) and (stmt_idx + 1 < len(stmt_list)):
                is_if_match_with_successor = True
                successor_ast_node = stmt_list[stmt_idx + 1]
                # Do NOT create CFGNode for successor_ast_node here.

            loose_ends_from_current_stmt_processing = []
            for source_node_for_stmt in live_sources_for_current_stmt:
                # Visit the current statement (If, Match, or other)
                # For If/Match, self.visit will handle their internal logic and return loose ends.
                # For other statements, it processes them and returns the next active node(s).
                returned_nodes = self.visit(stmt_ast, source_node_for_stmt)
                if returned_nodes:
                    loose_ends_from_current_stmt_processing.extend(returned_nodes)

            # Deduplicate loose ends from processing the current statement across its live sources
            loose_ends_from_current_stmt_processing = list(dict.fromkeys(loose_ends_from_current_stmt_processing))

            if is_if_match_with_successor and successor_ast_node:
                # Create the CFGNode for the successor *after* If/Match has been processed
                successor_text = ast.unparse(successor_ast_node).strip()
                successor_type = self._determine_node_type_from_ast(successor_ast_node)
                actual_successor_node = self.new_node(statements=[successor_text], node_type=successor_type)

                next_active_sources_after_if_match = []
                was_successor_linked = False
                if not loose_ends_from_current_stmt_processing: # Implicit fall-through if If/Match had no explicit loose ends
                    # This case might be rare if If/Match always produces some end (e.g. condition node itself if orelse is missing)
                    # However, if truly empty, it implies a direct path not taken through the branches,
                    # which logically would go to the actual_successor_node.
                    # This should ideally be handled by the If/Match visit methods returning appropriate loose ends.
                    # For safety, if no loose ends, we can consider the actual_successor_node as a potential next step if no path explicitly led to it.
                    # This part might need refinement based on how visit_If/visit_Match return values in edge cases.
                    pass # Covered by later logic to add actual_successor_node if it's the next logical step

                for node in loose_ends_from_current_stmt_processing:
                    if node.node_type in ("return_statement", "break_statement", "continue_statement", "raise_statement"):
                        next_active_sources_after_if_match.append(node)
                    else:
                        # Link non-terminal loose ends from If/Match to the actual_successor_node
                        self._link_predecessor_to_successor(node, actual_successor_node)
                        was_successor_linked = True

                # Add actual_successor_node to next_active_sources if it was linked,
                # or if it's the direct fall-through from an empty If/Match,
                # or if no paths explicitly led to it but it's the next statement.
                if was_successor_linked or not loose_ends_from_current_stmt_processing:
                     # If any path linked to it, or if the If/Match block had no specific divergent paths (e.g. all paths returned/broke)
                     # but a successor statement exists, it should become active.
                    next_active_sources_after_if_match.append(actual_successor_node)

                # Ensure no duplicates if actual_successor_node was already added (e.g. via a path through if/match)
                current_iteration_next_active_sources.extend(list(dict.fromkeys(next_active_sources_after_if_match)))
                skip_next_iteration = True # Successor node processed, skip its turn in the main loop
            else:
                # Not an If/Match with a successor, or successor_ast_node was None
                # Simply add all collected loose ends from processing stmt_ast
                current_iteration_next_active_sources.extend(loose_ends_from_current_stmt_processing)
                skip_next_iteration = False

            active_source_nodes = list(dict.fromkeys(current_iteration_next_active_sources))
        return active_source_nodes

    def visit(self, stmt_ast: ast.AST, source_node: CFGNode) -> Union[List[CFGNode], None]:
        method_name = 'visit_' + stmt_ast.__class__.__name__
        visitor_method = getattr(self, method_name, self.generic_visit_statement_node)

        if visitor_method.__name__ != 'generic_visit_statement_node':
            return visitor_method(stmt_ast, source_node)
        else:
            return self.generic_visit_statement_node(stmt_ast, source_node)

    def generic_visit_statement_node(self, stmt_ast: ast.AST, source_node: CFGNode) -> List[CFGNode]:
        stmt_text = ast.unparse(stmt_ast).strip()
        node_type = self._determine_node_type_from_ast(stmt_ast)
        current_stmt_node = self.new_node(statements=[stmt_text], node_type=node_type)
        self._link_predecessor_to_successor(source_node, current_stmt_node)
        return [current_stmt_node]

    def _determine_node_type_from_ast(self, stmt_ast: ast.AST) -> str:
        if isinstance(stmt_ast, (ast.Assign, ast.AugAssign, ast.AnnAssign)): return "assignment"
        if isinstance(stmt_ast, ast.Expr):
            if isinstance(stmt_ast.value, ast.Call): return "function_call"
            return "expression_statement"
        if isinstance(stmt_ast, ast.Pass): return "pass_statement"
        if isinstance(stmt_ast, ast.Return): return "return_statement"
        if isinstance(stmt_ast, ast.Break): return "break_statement"
        if isinstance(stmt_ast, ast.Continue): return "continue_statement"
        if isinstance(stmt_ast, ast.If): return "condition"
        if isinstance(stmt_ast, (ast.For, ast.While)): return "condition"
        if isinstance(stmt_ast, ast.FunctionDef): return "function_definition"
        if isinstance(stmt_ast, ast.Match): return "match_dispatcher"
        return "statement_block"

    def visit_Expr(self, ast_node: ast.Expr, source_node: CFGNode) -> List[CFGNode]:
        expr_text = ast.unparse(ast_node).strip()
        node_type = "expression_statement"
        if isinstance(ast_node.value, ast.Call):
            node_type = "function_call"
        current_expr_node = self.new_node(statements=[expr_text], node_type=node_type)
        self._link_predecessor_to_successor(source_node, current_expr_node)
        return [current_expr_node]

    def visit_Assign(self, ast_node: ast.Assign, source_node: CFGNode) -> List[CFGNode]:
        assign_text = ast.unparse(ast_node).strip()
        current_assign_node = self.new_node(statements=[assign_text], node_type="assignment")
        self._link_predecessor_to_successor(source_node, current_assign_node)
        return [current_assign_node]

    def visit_AugAssign(self, ast_node: ast.AugAssign, source_node: CFGNode) -> List[CFGNode]:
        aug_assign_text = ast.unparse(ast_node).strip()
        current_aug_assign_node = self.new_node(statements=[aug_assign_text], node_type="assignment")
        self._link_predecessor_to_successor(source_node, current_aug_assign_node)
        return [current_aug_assign_node]

    def visit_AnnAssign(self, ast_node: ast.AnnAssign, source_node: CFGNode) -> List[CFGNode]:
        ann_assign_text = ast.unparse(ast_node).strip()
        current_ann_assign_node = self.new_node(statements=[ann_assign_text], node_type="assignment")
        self._link_predecessor_to_successor(source_node, current_ann_assign_node)
        return [current_ann_assign_node]

    def visit_Pass(self, ast_node: ast.Pass, source_node: CFGNode) -> List[CFGNode]:
        pass_node = self.new_node(statements=["pass"], node_type="pass_statement")
        self._link_predecessor_to_successor(source_node, pass_node)
        return [pass_node]

    def visit_Return(self, ast_node: ast.Return, source_node: CFGNode) -> List[CFGNode]:
        return_text = ast.unparse(ast_node).strip()
        return_node = self.new_node(statements=[return_text], node_type="return_statement")
        self._link_predecessor_to_successor(source_node, return_node)
        return [return_node]

    def visit_If(self, ast_node: ast.If, source_node: CFGNode) -> List[CFGNode]:
        condition_text = ast.unparse(ast_node.test).strip()
        if_condition_node = self.new_node(statements=[f"if {condition_text}"], node_type="condition")
        self._link_predecessor_to_successor(source_node, if_condition_node)

        from .ast_utils import negate_condition_ast
        if_condition_node.true_condition_label = condition_text
        negated_test_ast = negate_condition_ast(ast_node.test)
        if_condition_node.false_condition_label = ast.unparse(negated_test_ast).strip() if negated_test_ast else f"not ({condition_text})"

        true_branch_entry_placeholder = self.new_node(node_type="statement_block")
        self._link_predecessor_to_successor(if_condition_node, true_branch_entry_placeholder, link_type="branch")
        true_branch_loose_ends = self._process_statement_list_in_block(ast_node.body, [true_branch_entry_placeholder])

        false_branch_loose_ends = []
        if ast_node.orelse:
            false_branch_entry_placeholder = self.new_node(node_type="statement_block")
            self._link_predecessor_to_successor(if_condition_node, false_branch_entry_placeholder, link_type="else")
            false_branch_loose_ends = self._process_statement_list_in_block(ast_node.orelse, [false_branch_entry_placeholder])
        else:
            false_branch_loose_ends.append(if_condition_node)

        all_loose_ends = true_branch_loose_ends + false_branch_loose_ends
        return list(dict.fromkeys(all_loose_ends)) if all_loose_ends else []

    def _visit_loop_generic(self, ast_node: Union[ast.For, ast.While], source_node: CFGNode, loop_type: str) -> List[CFGNode]:
        if isinstance(ast_node, ast.For):
            target_text = ast.unparse(ast_node.target).strip()
            iter_text = ast.unparse(ast_node.iter).strip()
            condition_text = f"for {target_text} in {iter_text}"
        else:
            condition_text = f"while {ast.unparse(ast_node.test).strip()}"

        loop_condition_node = self.new_node(statements=[condition_text], node_type="condition")
        self._link_predecessor_to_successor(source_node, loop_condition_node)

        loop_body_entry_placeholder = self.new_node(node_type="statement_block")
        self._link_predecessor_to_successor(loop_condition_node, loop_body_entry_placeholder, link_type="branch")

        loop_exit_node_for_breaks = self.new_node(statements=[f"exit_point_after_{loop_type}_{loop_condition_node.id}"], node_type="statement_block")
        self._loop_exit_stack.append(loop_exit_node_for_breaks)
        self._loop_start_stack.append(loop_condition_node)

        body_loose_ends = self._process_statement_list_in_block(ast_node.body, [loop_body_entry_placeholder])

        for end_node in body_loose_ends:
            if end_node.node_type not in ("break_statement", "continue_statement", "return_statement"):
                self._link_predecessor_to_successor(end_node, loop_condition_node)

        self._loop_exit_stack.pop()
        self._loop_start_stack.pop()

        self._link_predecessor_to_successor(loop_condition_node, loop_exit_node_for_breaks, link_type="else")

        if ast_node.orelse:
            orelse_loose_ends = self._process_statement_list_in_block(ast_node.orelse, [loop_exit_node_for_breaks])
            return orelse_loose_ends
        else:
            return [loop_exit_node_for_breaks]

    def visit_For(self, ast_node: ast.For, source_node: CFGNode) -> List[CFGNode]:
        return self._visit_loop_generic(ast_node, source_node, "for")

    def visit_While(self, ast_node: ast.While, source_node: CFGNode) -> List[CFGNode]:
        return self._visit_loop_generic(ast_node, source_node, "while")

    def visit_Break(self, ast_node: ast.Break, source_node: CFGNode) -> List[CFGNode]:
        break_node = self.new_node(statements=["break"], node_type="break_statement")
        self._link_predecessor_to_successor(source_node, break_node)
        if self._loop_exit_stack:
            self._link_predecessor_to_successor(break_node, self._loop_exit_stack[-1])
        else:
            print("Warning: Break statement outside of a loop.")
        return [break_node]

    def visit_Continue(self, ast_node: ast.Continue, source_node: CFGNode) -> List[CFGNode]:
        continue_node = self.new_node(statements=["continue"], node_type="continue_statement")
        self._link_predecessor_to_successor(source_node, continue_node)
        if self._loop_start_stack:
            self._link_predecessor_to_successor(continue_node, self._loop_start_stack[-1])
        else:
            print("Warning: Continue statement outside of a loop.")
        return [continue_node]

    def visit_Try(self, ast_node: ast.Try, source_node: CFGNode) -> List[CFGNode]:
        try_entry_node = self.new_node(statements=["try"], node_type="try_block_start")
        self._link_predecessor_to_successor(source_node, try_entry_node)

        body_loose_ends = self._process_statement_list_in_block(ast_node.body, [try_entry_node])
        post_try_merge_node = self.new_node(statements=[], node_type="statement_block")

        finally_entry_node = None
        if ast_node.finalbody:
            finally_entry_node = self.new_node(statements=["finally"], node_type="finally_block_start")
            for end_node in body_loose_ends:
                if end_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                     self._link_predecessor_to_successor(end_node, finally_entry_node)

            current_finally_loose_ends = self._process_statement_list_in_block(ast_node.finalbody, [finally_entry_node])
            for fend_node in current_finally_loose_ends:
                 self._link_predecessor_to_successor(fend_node, post_try_merge_node)
            body_loose_ends = current_finally_loose_ends
        else:
            for end_node in body_loose_ends:
                if end_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                    self._link_predecessor_to_successor(end_node, post_try_merge_node)

        handler_overall_loose_ends = []
        for handler in ast_node.handlers:
            handler_text = "except"
            if handler.type:
                handler_text += f" {ast.unparse(handler.type).strip()}"
            if handler.name:
                handler_text += f" as {handler.name}"

            handler_entry = self.new_node(statements=[handler_text], node_type="exception_handler_start")
            self._link_predecessor_to_successor(try_entry_node, handler_entry, link_type="else")

            current_handler_loose_ends = self._process_statement_list_in_block(handler.body, [handler_entry])

            if ast_node.finalbody and finally_entry_node:
                for hend_node in current_handler_loose_ends:
                    if hend_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                        self._link_predecessor_to_successor(hend_node, finally_entry_node)
            else:
                for hend_node in current_handler_loose_ends:
                     if hend_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                        self._link_predecessor_to_successor(hend_node, post_try_merge_node)
            handler_overall_loose_ends.extend(current_handler_loose_ends)

        if ast_node.orelse:
            orelse_entry_node = self.new_node(statements=["orelse"], node_type="else_block_start")
            self._link_predecessor_to_successor(try_entry_node, orelse_entry_node, link_type="else")

            current_orelse_loose_ends = self._process_statement_list_in_block(ast_node.orelse, [orelse_entry_node])

            if ast_node.finalbody and finally_entry_node:
                for oend_node in current_orelse_loose_ends:
                     if oend_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                        self._link_predecessor_to_successor(oend_node, finally_entry_node)
            else:
                for oend_node in current_orelse_loose_ends:
                    if oend_node.node_type not in ("return_statement", "break_statement", "continue_statement"):
                        self._link_predecessor_to_successor(oend_node, post_try_merge_node)
            handler_overall_loose_ends.extend(current_orelse_loose_ends)

        final_loose_ends = [n for n in body_loose_ends + handler_overall_loose_ends if n.node_type in ("return_statement", "break_statement", "continue_statement")]

        is_post_try_merge_used = False
        for node in self.nodes.values():
            if node.next_node == post_try_merge_node or \
               node.branch_node == post_try_merge_node or \
               node.else_node == post_try_merge_node:
                is_post_try_merge_used = True
                break
            if hasattr(node, 'case_branches'):
                for _, target_n in node.case_branches:
                    if target_n == post_try_merge_node:
                        is_post_try_merge_used = True; break
                if is_post_try_merge_used: break

        if is_post_try_merge_used and post_try_merge_node not in final_loose_ends:
            final_loose_ends.append(post_try_merge_node)
        elif not is_post_try_merge_used and not final_loose_ends and not ast_node.finalbody :
             pass
        return list(dict.fromkeys(final_loose_ends))

    def visit_Raise(self, ast_node: ast.Raise, source_node: CFGNode) -> List[CFGNode]:
        raise_text = ast.unparse(ast_node).strip()
        raise_node = self.new_node(statements=[raise_text], node_type="raise_statement")
        self._link_predecessor_to_successor(source_node, raise_node)
        return [raise_node]

    def visit_Match(self, ast_node: ast.Match, source_node: CFGNode) -> Union[List[CFGNode], None]:
        match_subject_text = ast.unparse(ast_node.subject).strip()
        match_dispatcher_node = self.new_node(statements=[f"match {match_subject_text}"], node_type="match_dispatcher")
        self._link_predecessor_to_successor(source_node, match_dispatcher_node)

        if not hasattr(match_dispatcher_node, 'case_branches'):
            match_dispatcher_node.case_branches = []

        collected_loose_ends_from_all_cases: List[CFGNode] = []
        wildcard_case_exists = False

        for case_block in ast_node.cases:
            pattern_str = ast.unparse(case_block.pattern).strip()
            case_label_text = f"case: {pattern_str}"
            if case_block.guard:
                guard_str = ast.unparse(case_block.guard).strip()
                case_label_text += f" if {guard_str}"

            if isinstance(case_block.pattern, ast.MatchAs) and \
               case_block.pattern.pattern is None and \
               (case_block.pattern.name is None or case_block.pattern.name == "_") and \
               case_block.guard is None:
                wildcard_case_exists = True

            is_empty_or_pass_case = not case_block.body or \
                                   (len(case_block.body) == 1 and isinstance(case_block.body[0], ast.Pass))

            if is_empty_or_pass_case:
                node_stmts = ["pass"] if (case_block.body and isinstance(case_block.body[0], ast.Pass)) else []
                node_type = "pass_statement" if node_stmts else "statement_block"
                case_body_target_node = self.new_node(statements=node_stmts, node_type=node_type)
                match_dispatcher_node.case_branches.append((case_label_text, case_body_target_node))
                collected_loose_ends_from_all_cases.append(case_body_target_node)
            else:
                first_stmt_ast = case_block.body[0]
                remaining_stmts_ast = case_block.body[1:]

                first_stmt_text = ast.unparse(first_stmt_ast).strip()
                first_stmt_node_type = self._determine_node_type_from_ast(first_stmt_ast)
                actual_first_stmt_node = self.new_node(statements=[first_stmt_text], node_type=first_stmt_node_type)

                match_dispatcher_node.case_branches.append((case_label_text, actual_first_stmt_node))

                if remaining_stmts_ast:
                    case_body_loose_ends = self._process_statement_list_in_block(remaining_stmts_ast, [actual_first_stmt_node])
                    collected_loose_ends_from_all_cases.extend(case_body_loose_ends)
                else:
                    if actual_first_stmt_node.node_type not in ("return_statement", "break_statement", "continue_statement", "raise_statement"):
                        collected_loose_ends_from_all_cases.append(actual_first_stmt_node)
                    elif actual_first_stmt_node.node_type == "return_statement":
                        collected_loose_ends_from_all_cases.append(actual_first_stmt_node)
                    else:
                        collected_loose_ends_from_all_cases.append(actual_first_stmt_node)

        if not ast_node.cases:
            collected_loose_ends_from_all_cases.append(match_dispatcher_node)

        return list(dict.fromkeys(node for node in collected_loose_ends_from_all_cases if node is not None))

    def _renumber_nodes(self):
        if not self.nodes:
            return

        # 1. Collect all current node objects
        all_existing_nodes = list(self.nodes.values())

        # 2. Sort these nodes based on their existing `id` attribute.
        # This preserves the logical top-to-bottom order.
        # It's important if the entry node (id=1) was optimized out and
        # then re-added, or for any other case where original IDs matter for order.
        # However, given typical CFG construction, simple sorting by original ID is robust.
        all_existing_nodes.sort(key=lambda node: node.id)

        # 3. Create a new empty dictionary for the re-numbered nodes
        new_nodes_map = {}

        # 4. Initialize a counter for new IDs
        current_new_id = 1

        # 5. Iterate through the sorted list of nodes
        for node_obj in all_existing_nodes:
            # Update the node's id attribute
            node_obj.id = current_new_id

            # Add the node_obj to new_nodes_map with current_new_id as the key
            new_nodes_map[current_new_id] = node_obj

            # Increment current_new_id for the next node
            current_new_id += 1

        # 6. Replace the self.nodes dictionary with new_nodes_map
        self.nodes = new_nodes_map

        # 7. Update self.current_id to reflect the highest ID assigned.
        # This is important if any code were to try to add new nodes after this,
        # though typically re-numbering is one of the final steps.
        if not self.nodes: # If all nodes were removed (e.g. by optimization before this step)
             self.current_id = 0
        else:
             self.current_id = current_new_id - 1

    def _optimize_empty_blocks(self):
        if not self.entry_node:
            return

        while True:
            made_change_this_pass = False
            nodes_to_remove_map: Dict[int, CFGNode] = {}

            for node_id, current_node in list(self.nodes.items()):
                if node_id in nodes_to_remove_map:
                    continue

                is_optimizable = (
                    current_node.node_type == "statement_block" and
                    not current_node.statements and
                    current_node.id != self.entry_node.id and
                    (self.exit_node is None or current_node.id != self.exit_node.id) and
                    current_node.next_node is not None and
                    current_node.branch_node is None and
                    current_node.else_node is None and
                    not current_node.case_branches
                )

                if is_optimizable:
                    ultimate_successor = current_node.next_node
                    path_traversed = {current_node.id, ultimate_successor.id if ultimate_successor else -1}

                    temp_next_in_chain = ultimate_successor
                    while temp_next_in_chain and temp_next_in_chain.id in nodes_to_remove_map:
                        temp_next_in_chain = nodes_to_remove_map[temp_next_in_chain.id]
                        if temp_next_in_chain is None or temp_next_in_chain.id in path_traversed :
                            ultimate_successor = None
                            break
                        ultimate_successor = temp_next_in_chain
                        if ultimate_successor:
                             path_traversed.add(ultimate_successor.id)

                    if ultimate_successor:
                        nodes_to_remove_map[current_node.id] = ultimate_successor
                        made_change_this_pass = True

            if not made_change_this_pass:
                break

            for p_node in self.nodes.values():
                if p_node.id in nodes_to_remove_map:
                    continue

                if p_node.next_node and p_node.next_node.id in nodes_to_remove_map:
                    p_node.next_node = nodes_to_remove_map[p_node.next_node.id]

                if p_node.branch_node and p_node.branch_node.id in nodes_to_remove_map:
                    p_node.branch_node = nodes_to_remove_map[p_node.branch_node.id]

                if p_node.else_node and p_node.else_node.id in nodes_to_remove_map:
                    p_node.else_node = nodes_to_remove_map[p_node.else_node.id]

                if hasattr(p_node, 'case_branches') and p_node.case_branches:
                    updated_case_branches = []
                    branch_changed_in_p_node = False
                    for label, target_node in p_node.case_branches:
                        if target_node and target_node.id in nodes_to_remove_map:
                            updated_case_branches.append((label, nodes_to_remove_map[target_node.id]))
                            branch_changed_in_p_node = True
                        else:
                            updated_case_branches.append((label, target_node))
                    if branch_changed_in_p_node:
                        p_node.case_branches = updated_case_branches

            for node_id_to_remove in nodes_to_remove_map.keys():
                if node_id_to_remove in self.nodes:
                    del self.nodes[node_id_to_remove]

    def find_prime_paths(self) -> List[List[CFGNode]]:
        """
        Finds and returns the prime paths of the CFG.
        A prime path is a simple path that is not a sub-path of any other simple path.
        """
        if not self.entry_node:
            return []

        all_simple_paths = self._find_all_simple_paths()
        prime_paths = []

        for path in all_simple_paths:
            is_prime = True
            for other_path in all_simple_paths:
                if path == other_path:
                    continue
                # Check if path is a subpath of other_path
                if len(path) < len(other_path):
                    for i in range(len(other_path) - len(path) + 1):
                        if other_path[i:i+len(path)] == path:
                            is_prime = False
                            break
                if not is_prime:
                    break
            if is_prime:
                prime_paths.append(path)

        return prime_paths

    def _find_all_simple_paths(self) -> List[List[CFGNode]]:
        """
        Finds all simple paths in the CFG.
        A simple path is a path with no repeated vertices.
        This method explores paths from every node to every other node.
        """
        all_paths = []
        nodes = list(self.nodes.values())
        for start_node in nodes:
            for end_node in nodes:
                # Find paths from start_node to end_node
                # We can do this with a modified DFS.
                # To get all simple paths, we don't just start from the entry node.
                # A prime path can exist between any two nodes.
                paths = self._dfs_simple_paths(start_node, end_node)
                all_paths.extend(paths)

        # The paths found can be just single nodes, which are valid simple paths.
        # Filter out empty paths if any were added.
        all_paths = [p for p in all_paths if p]

        # Remove duplicate paths
        unique_paths_set = set(tuple(p) for p in all_paths)
        unique_paths = [list(p) for p in unique_paths_set]

        return unique_paths

    def _dfs_simple_paths(self, start_node: CFGNode, end_node: CFGNode) -> List[List[CFGNode]]:
        """
        Finds all simple paths from a start node to an end node using DFS.
        """

        stack = [(start_node, [start_node])]
        all_paths = []

        while stack:
            current_node, path = stack.pop()

            if current_node == end_node:
                all_paths.append(path)

            successors = self.get_successors(current_node)
            for successor in successors:
                if successor not in path:
                    new_path = path + [successor]
                    stack.append((successor, new_path))

        return all_paths

    def get_successors(self, node: CFGNode) -> List[CFGNode]:
        """
        Returns a list of successor nodes for a given node.
        """
        successors = []
        if node.next_node:
            successors.append(node.next_node)
        if node.branch_node:
            successors.append(node.branch_node)
        if node.else_node:
            successors.append(node.else_node)
        if hasattr(node, 'case_branches'):
            for _, target_node in node.case_branches:
                if target_node:
                    successors.append(target_node)
        return successors

    def _escape_label(self, text: str) -> str:
        """Escapes characters in a string for DOT label compatibility."""
        return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def to_dot(self, show_statement_text: bool = True) -> str:
        dot_lines = [
            "digraph CFG {",
            "    rankdir=TB;",
            "    ranksep=\"1.0\";",
            "    nodesep=\"0.5\";",
            "    node [shape=circle, fontname=Arial];",
            "    edge [fontname=Arial];"
        ]

        node_declarations = []
        edge_definitions = []

        processed_node_ids = set()

        nodes_to_render = list(self.nodes.values())

        for current_node in nodes_to_render:
            if not current_node or current_node.id in processed_node_ids:
                continue
            processed_node_ids.add(current_node.id)

            node_id_str = str(current_node.id)
            dot_label = f'"{node_id_str}"'

            xlabel_text = ""
            if current_node.node_type == "entry":
                xlabel_text = "START"
            elif current_node.node_type == "exit":
                xlabel_text = "EXIT"
            elif current_node.statements:
                xlabel_text = "\\n".join(s.replace('\\', '\\\\').replace('"', '\\"') for s in current_node.statements)
            elif current_node.node_type == "statement_block":
                xlabel_text = "Block (empty)"
            else:
                xlabel_text = current_node.node_type

            escaped_xlabel = xlabel_text.replace('\\', '\\\\').replace('"', '\\"')

            shape = "circle"
            if current_node.node_type == "entry":
                shape = "circle"
            elif current_node.node_type == "exit":
                shape = "doublecircle"
            elif current_node.node_type == "condition":
                shape = "circle"
            elif current_node.node_type == "match_dispatcher":
                shape = "circle"
            elif current_node.node_type == "merge_point":
                shape = "diamond"

            node_declarations.append(f'    {node_id_str} [label={dot_label}, xlabel="{escaped_xlabel}", shape={shape}];')

            if current_node.next_node:
                is_unconditional_sequential = (
                    current_node.branch_node is None and
                    current_node.else_node is None and
                    current_node.node_type != "match_dispatcher"
                )
                if is_unconditional_sequential:
                    edge_definitions.append(f"    {node_id_str} -> {current_node.next_node.id};")
                else:
                    edge_definitions.append(f"    {node_id_str} -> {current_node.next_node.id} [label=\"next\"];")

            if current_node.branch_node:
                label_text = "True"
                if hasattr(current_node, 'true_condition_label') and current_node.true_condition_label:
                    label_text = current_node.true_condition_label
                edge_definitions.append(f"    {node_id_str} -> {current_node.branch_node.id} [label=\"{self._escape_label(label_text)}\"];")

            if current_node.else_node:
                label_text = "False"
                if hasattr(current_node, 'false_condition_label') and current_node.false_condition_label:
                    label_text = current_node.false_condition_label
                edge_definitions.append(f"    {node_id_str} -> {current_node.else_node.id} [label=\"{self._escape_label(label_text)}\"];")

            if current_node.node_type == "match_dispatcher" and hasattr(current_node, 'case_branches') and current_node.case_branches:
                for i, (case_label, target_node) in enumerate(current_node.case_branches):
                    if target_node:
                        escaped_case_label = case_label.replace('\\', '\\\\').replace('"', '\\"')
                        edge_definitions.append(f"    {node_id_str} -> {target_node.id} [label=\"{escaped_case_label}\"];")

        for node_id_val, node_obj in self.nodes.items():
            if node_id_val not in processed_node_ids:
                node_id_str_orphan = str(node_obj.id)
                dot_label_orphan = f'"{node_id_str_orphan}"'
                xlabel_orphan = "Orphan: " + "\\n".join(s.replace('\\', '\\\\').replace('"', '\\"') for s in node_obj.statements) \
                                if node_obj.statements else f"Orphan: {node_obj.node_type}"
                escaped_xlabel_orphan = xlabel_orphan.replace('\\', '\\\\').replace('"', '\\"')
                shape_orphan = "box"
                node_declarations.append(f'    {node_id_str_orphan} [label={dot_label_orphan}, xlabel="{escaped_xlabel_orphan}", shape={shape_orphan}, style=filled, fillcolor=gray];')

        dot_lines.extend(sorted(list(set(node_declarations))))
        dot_lines.extend(sorted(list(set(edge_definitions))))
        dot_lines.append("}")
        return "\n".join(dot_lines)
