import unittest
import ast
from .cfg_builder import CFGBuilder # Assuming this will pick up the modified version
from .cfg_node import CFGNode

class TestCFGGeneration(unittest.TestCase):

    def setUp(self):
        self.builder = CFGBuilder()

    def _find_node_by_statement(self, start_node, statement_substr, visited=None):
        """Helper to find a node containing a specific statement substring."""
        if visited is None:
            visited = set()
        
        if start_node is None or start_node.id in visited:
            return None
        visited.add(start_node.id)

        if any(statement_substr in stmt for stmt in start_node.statements):
            return start_node
        
        # Traverse
        found = self._find_node_by_statement(start_node.next_node, statement_substr, visited)
        if found: return found
        found = self._find_node_by_statement(start_node.branch_node, statement_substr, visited)
        if found: return found
        found = self._find_node_by_statement(start_node.else_node, statement_substr, visited)
        if found: return found
        
        if hasattr(start_node, 'case_branches') and start_node.case_branches:
            for _, case_target_node in start_node.case_branches:
                found = self._find_node_by_statement(case_target_node, statement_substr, visited)
                if found: return found

        return None

    def _count_nodes(self, start_node):
        """Helper to count all unique nodes reachable from start_node."""
        count = 0
        queue = [start_node]
        visited_count = set()
        while queue:
            current = queue.pop(0)
            if current is None or current.id in visited_count:
                continue
            visited_count.add(current.id)
            count += 1
            if current.next_node:
                queue.append(current.next_node)
            if current.branch_node:
                queue.append(current.branch_node)
            if current.else_node:
                queue.append(current.else_node)
            if hasattr(current, 'case_branches') and current.case_branches:
                for _, case_target_node in current.case_branches:
                    if case_target_node: # Ensure not None before adding
                        queue.append(case_target_node)
        return count

    # --- Test Cases Start Here ---

    def test_annotated_assignments(self):
        # Case 1: Annotated assignment with a value
        code_with_value = "x: int = 10"
        cfg_with_value = self.builder.build_cfg(code_with_value)
        
        assign_node_wv = self._find_node_by_statement(cfg_with_value, "x: int = 10")
        self.assertIsNotNone(assign_node_wv, "Node 'x: int = 10' not found")
        self.assertEqual(assign_node_wv.node_type, "assignment")
        self.assertIsNotNone(assign_node_wv.next_node)
        self.assertEqual(assign_node_wv.next_node.node_type, "exit") # Should lead to exit

        # Case 2: Annotated assignment without a value
        code_without_value = "y: str"
        cfg_without_value = self.builder.build_cfg(code_without_value)

        assign_node_wov = self._find_node_by_statement(cfg_without_value, "y: str")
        self.assertIsNotNone(assign_node_wov, "Node 'y: str' not found")
        self.assertEqual(assign_node_wov.node_type, "assignment")
        self.assertIsNotNone(assign_node_wov.next_node)
        self.assertEqual(assign_node_wov.next_node.node_type, "exit")

    def test_calls(self):
        # Case 1: Simple method call
        code_method_call = "obj.method()"
        cfg_method_call = self.builder.build_cfg(code_method_call)
        
        call_node_method = self._find_node_by_statement(cfg_method_call, "obj.method()")
        self.assertIsNotNone(call_node_method, "Node 'obj.method()' not found")
        self.assertEqual(call_node_method.node_type, "function_call")
        self.assertIsNotNone(call_node_method.next_node)
        self.assertEqual(call_node_method.next_node.node_type, "exit")

        # Case 2: Simple function call
        code_function_call = "my_function()"
        cfg_function_call = self.builder.build_cfg(code_function_call)

        call_node_function = self._find_node_by_statement(cfg_function_call, "my_function()")
        self.assertIsNotNone(call_node_function, "Node 'my_function()' not found")
        self.assertEqual(call_node_function.node_type, "function_call")
        self.assertIsNotNone(call_node_function.next_node)
        self.assertEqual(call_node_function.next_node.node_type, "exit")

    def test_while_loops(self):
        # Case 1: Basic while loop
        code_basic_while = """
while x < 10:
    x = x + 1
"""
        cfg_basic_while = self.builder.build_cfg(code_basic_while)
        self.assertEqual(self._count_nodes(cfg_basic_while), 4, "Basic While: Node count mismatch")

        cond_node_bw = self._find_node_by_statement(cfg_basic_while, "x < 10")
        self.assertIsNotNone(cond_node_bw, "Basic While: Condition node not found")
        self.assertEqual(cond_node_bw.node_type, "condition")
        self.assertIs(cfg_basic_while.next_node, cond_node_bw, "Basic While: Start should link to condition node")
        
        body_node_bw = self._find_node_by_statement(cfg_basic_while, "x = x + 1")
        self.assertIsNotNone(body_node_bw, "Basic While: Body node not found")
        
        self.assertIs(cond_node_bw.branch_node, body_node_bw, "Basic While: Condition should branch to body")
        self.assertIs(body_node_bw.next_node, cond_node_bw, "Basic While: Body should loop back to condition")
        self.assertIsNotNone(cond_node_bw.else_node, "Basic While: Condition should have an else path to exit")
        self.assertEqual(cond_node_bw.else_node.node_type, "exit", "Basic While: Condition else path should lead to exit")

        # Case 2: While loop with an else block
        code_while_else = """
while y < 5:
    y = y + 1
else:
    y = 0
"""
        cfg_while_else = self.builder.build_cfg(code_while_else)
        self.assertEqual(self._count_nodes(cfg_while_else), 5, "While-Else: Node count mismatch")
        cond_node_we = self._find_node_by_statement(cfg_while_else, "y < 5")
        self.assertIsNotNone(cond_node_we, "While-Else: Condition node not found")
        self.assertIs(cfg_while_else.next_node, cond_node_we, "While-Else: Start should link to condition node")
        body_node_we = self._find_node_by_statement(cfg_while_else, "y = y + 1")
        self.assertIsNotNone(body_node_we, "While-Else: Body node not found")
        else_body_node_we = self._find_node_by_statement(cfg_while_else, "y = 0")
        self.assertIsNotNone(else_body_node_we, "While-Else: Else body node not found")

        self.assertIs(cond_node_we.branch_node, body_node_we)
        self.assertIs(body_node_we.next_node, cond_node_we)
        self.assertIs(cond_node_we.else_node, else_body_node_we)
        self.assertIsNotNone(else_body_node_we.next_node)
        self.assertEqual(else_body_node_we.next_node.node_type, "exit")

        # Case 3: While loop with an empty body
        code_empty_while = "while z > 0: pass"
        cfg_empty_while = self.builder.build_cfg(code_empty_while)
        
        cond_node_ew = self._find_node_by_statement(cfg_empty_while, "z > 0")
        self.assertIsNotNone(cond_node_ew, "Empty While: Condition node not found")
        self.assertIs(cfg_empty_while.next_node, cond_node_ew, "Empty While: Start should link to condition node")
        pass_node_ew = self._find_node_by_statement(cfg_empty_while, "pass")
        
        if pass_node_ew:
             self.assertEqual(self._count_nodes(cfg_empty_while), 4, "Empty While (with pass): Node count mismatch")
             self.assertIs(cond_node_ew.branch_node, pass_node_ew, "Empty While: Cond should branch to pass")
             self.assertIs(pass_node_ew.next_node, cond_node_ew, "Empty While: Pass should loop to cond")
        else:
             self.assertEqual(self._count_nodes(cfg_empty_while), 3, "Empty While (no pass node): Node count mismatch")
             self.assertIs(cond_node_ew.branch_node, cond_node_ew, "Empty While: Cond should branch to self if body empty")
        
        self.assertIsNotNone(cond_node_ew.else_node)
        self.assertEqual(cond_node_ew.else_node.node_type, "exit")

        code_false_cond_while = "while False: val = 1"
        cfg_fals_cond_while = self.builder.build_cfg(code_false_cond_while)
        self.assertEqual(self._count_nodes(cfg_fals_cond_while), 4, "False Cond While: Node count mismatch")
        cond_node_fcw = self._find_node_by_statement(cfg_fals_cond_while, "False")
        self.assertIsNotNone(cond_node_fcw, "False Cond While: Condition node 'False' not found")
        self.assertIs(cfg_fals_cond_while.next_node, cond_node_fcw, "False Cond While: Start should link to condition node")
        body_node_fcw = self._find_node_by_statement(cfg_fals_cond_while, "val = 1")
        self.assertIsNotNone(body_node_fcw, "False Cond While: Body node 'val = 1' not found")
        
        self.assertIs(cond_node_fcw.branch_node, body_node_fcw)
        self.assertIs(body_node_fcw.next_node, cond_node_fcw)
        self.assertIsNotNone(cond_node_fcw.else_node)
        self.assertEqual(cond_node_fcw.else_node.node_type, "exit")

    def _find_for_init_node(self, start_node, iter_source_str):
       # iter_source_str is like "iter(range(3))" or "iter(my_list)"
       q = [start_node]
       visited = set()
       while q:
           curr = q.pop(0)
           if not curr or curr.id in visited:
               continue
           visited.add(curr.id)
           if curr.node_type == "for_init" and curr.statements and iter_source_str in curr.statements[0]:
               return curr
           if curr.next_node: q.append(curr.next_node)
           if curr.branch_node: q.append(curr.branch_node)
           if curr.else_node: q.append(curr.else_node)
       return None

    def test_for_loops(self):
        # Basic For
        code_basic_for = "for i in range(3): print(i)"
        cfg_basic_for = self.builder.build_cfg(code_basic_for)
        self.assertEqual(self._count_nodes(cfg_basic_for), 6, "Basic For: Node count mismatch")

        init_node_bf = self._find_for_init_node(cfg_basic_for, "iter(range(3))")
        self.assertIsNotNone(init_node_bf, "Basic For: Init node 'iter(range(3))' not found")
        self.assertEqual(init_node_bf.node_type, "for_init")
        self.assertIs(cfg_basic_for.next_node, init_node_bf, "Basic For: Start should link to init node")

        iter_var_name_bf = init_node_bf.statements[0].split(" ")[0]

        header_node_bf = self._find_node_by_statement(cfg_basic_for, f"for i in {iter_var_name_bf}")
        self.assertIsNotNone(header_node_bf, f"Basic For: Header node 'for i in {iter_var_name_bf}' not found")
        self.assertEqual(header_node_bf.node_type, "condition")

        next_item_node_bf = self._find_node_by_statement(cfg_basic_for, f"i = next({iter_var_name_bf})")
        self.assertIsNotNone(next_item_node_bf, f"Basic For: Next item node 'i = next({iter_var_name_bf})' not found")
        self.assertEqual(next_item_node_bf.node_type, "assignment")
        
        body_node_bf = self._find_node_by_statement(cfg_basic_for, "print(i)")
        self.assertIsNotNone(body_node_bf, "Basic For: Body node 'print(i)' not found")

        self.assertIs(init_node_bf.next_node, header_node_bf, "Basic For: Link init to header")
        self.assertIs(header_node_bf.branch_node, next_item_node_bf, "Basic For: Link header to next_item")
        self.assertIs(next_item_node_bf.next_node, body_node_bf, "Basic For: Link next_item to body")
        self.assertIs(body_node_bf.next_node, header_node_bf, "Basic For: Link body back to header")
        self.assertIsNotNone(header_node_bf.else_node, "Basic For: Header should have an else path")
        self.assertEqual(header_node_bf.else_node.node_type, "exit", "Basic For: Header else path should lead to exit")

        # For-Else
        code_for_else = """
for x in my_list:
    process(x)
else:
    print('Done')
"""
        cfg_for_else = self.builder.build_cfg(code_for_else)
        self.assertEqual(self._count_nodes(cfg_for_else), 7, "For-Else: Node count mismatch")

        init_node_fe = self._find_for_init_node(cfg_for_else, "iter(my_list)")
        self.assertIsNotNone(init_node_fe, "For-Else: Init node 'iter(my_list)' not found")
        self.assertIs(cfg_for_else.next_node, init_node_fe, "For-Else: Start should link to init node")
        iter_var_name_fe = init_node_fe.statements[0].split(" ")[0]

        header_node_fe = self._find_node_by_statement(cfg_for_else, f"for x in {iter_var_name_fe}")
        self.assertIsNotNone(header_node_fe, f"For-Else: Header node 'for x in {iter_var_name_fe}' not found")

        next_item_node_fe = self._find_node_by_statement(cfg_for_else, f"x = next({iter_var_name_fe})")
        self.assertIsNotNone(next_item_node_fe, f"For-Else: Next item node 'x = next({iter_var_name_fe})' not found")

        else_body_node_fe = self._find_node_by_statement(cfg_for_else, "print('Done')")
        self.assertIsNotNone(else_body_node_fe, "For-Else: Else body node 'print('Done')' not found")
        self.assertIs(header_node_fe.else_node, else_body_node_fe, "For-Else: Header else should link to else body")
        self.assertIsNotNone(else_body_node_fe.next_node, "For-Else: Else body should have next node")
        self.assertEqual(else_body_node_fe.next_node.node_type, "exit", "For-Else: Else body next node should be exit")

        # For-Empty Sequence
        code_for_empty_seq = "for y in []: print(y)"
        cfg_for_empty_seq = self.builder.build_cfg(code_for_empty_seq)
        self.assertEqual(self._count_nodes(cfg_for_empty_seq), 6, "For-EmptySeq: Node count mismatch")

        init_node_fes = self._find_for_init_node(cfg_for_empty_seq, "iter([])")
        self.assertIsNotNone(init_node_fes, "For-EmptySeq: Init node 'iter([])' not found")
        self.assertIs(cfg_for_empty_seq.next_node, init_node_fes, "For-EmptySeq: Start should link to init node")
        iter_var_name_fes = init_node_fes.statements[0].split(" ")[0]

        header_node_fes = self._find_node_by_statement(cfg_for_empty_seq, f"for y in {iter_var_name_fes}")
        self.assertIsNotNone(header_node_fes, f"For-EmptySeq: Header node 'for y in {iter_var_name_fes}' not found")
        self.assertEqual(header_node_fes.else_node.node_type, "exit", "For-EmptySeq: Header else path should be exit")

        # For-Break
        code_for_break = """
for z in items:
    if z == 1:
        break
    print(z)
"""
        cfg_for_break = self.builder.build_cfg(code_for_break)
        # Count might vary based on how shared exit is handled for break vs loop end
        # Expected: Start, Init, Header, NextItem, If, Break, Print, Exit = 8
        self.assertEqual(self._count_nodes(cfg_for_break), 8, "For-Break: Node count mismatch")

        init_node_fb = self._find_for_init_node(cfg_for_break, "iter(items)")
        self.assertIsNotNone(init_node_fb, "For-Break: Init node 'iter(items)' not found")
        self.assertIs(cfg_for_break.next_node, init_node_fb, "For-Break: Start should link to init node")
        iter_var_name_fb = init_node_fb.statements[0].split(" ")[0]
        
        header_node_fb = self._find_node_by_statement(cfg_for_break, f"for z in {iter_var_name_fb}")
        self.assertIsNotNone(header_node_fb, f"For-Break: Header node 'for z in {iter_var_name_fb}' not found")

        next_item_node_fb = self._find_node_by_statement(cfg_for_break, f"z = next({iter_var_name_fb})")
        self.assertIsNotNone(next_item_node_fb, f"For-Break: Next item node 'z = next({iter_var_name_fb})' not found")
        
        if_node_fb = self._find_node_by_statement(cfg_for_break, "z == 1")
        self.assertIsNotNone(if_node_fb, "For-Break: If condition node 'z == 1' not found")
        self.assertEqual(if_node_fb.node_type, "condition")
        # Assuming next_item_node directly leads to if condition (or through an empty block)
        actual_next_from_next_item = self._get_actual_target_node(next_item_node_fb.next_node)
        self.assertIs(actual_next_from_next_item, if_node_fb, "For-Break: NextItem node should link to If condition")


        break_node_fb = self._find_node_by_statement(cfg_for_break, "break")
        self.assertIsNotNone(break_node_fb, "For-Break: Break node not found")

        if break_node_fb.next_node:
             self.assertNotEqual(break_node_fb.next_node, header_node_fb, "For-Break: Break should not loop back to header")
             self.assertEqual(break_node_fb.next_node.node_type, "exit", "For-Break: Break node should lead to exit")

        # For-Complex Target
        code_for_complex_target = "for x, y in items: process(x, y)"
        cfg_fct = self.builder.build_cfg(code_for_complex_target)
        self.assertEqual(self._count_nodes(cfg_fct), 6, "For-ComplexTarget: Node count mismatch")

        init_node_fct = self._find_for_init_node(cfg_fct, "iter(items)")
        self.assertIsNotNone(init_node_fct, "For-ComplexTarget: Init node 'iter(items)' not found")
        self.assertIs(cfg_fct.next_node, init_node_fct, "For-ComplexTarget: Start should link to init node")
        iter_var_name_fct = init_node_fct.statements[0].split(" ")[0]

        header_node_fct = self._find_node_by_statement(cfg_fct, f"for (x, y) in {iter_var_name_fct}")
        self.assertIsNotNone(header_node_fct, f"For-ComplexTarget: Header node 'for (x, y) in {iter_var_name_fct}' not found")

        next_item_node_fct = self._find_node_by_statement(cfg_fct, f"(x, y) = next({iter_var_name_fct})")
        self.assertIsNotNone(next_item_node_fct, f"For-ComplexTarget: Next item node '(x, y) = next({iter_var_name_fct})' not found")

        body_node_fct = self._find_node_by_statement(cfg_fct, "process(x, y)")
        self.assertIsNotNone(body_node_fct, "For-ComplexTarget: Body node 'process(x, y)' not found")
        
        self.assertIs(header_node_fct.branch_node, next_item_node_fct, "For-ComplexTarget: Link header to next_item")
        self.assertIs(next_item_node_fct.next_node, body_node_fct, "For-ComplexTarget: Link next_item to body")
        self.assertIs(body_node_fct.next_node, header_node_fct, "For-ComplexTarget: Link body to header")
        self.assertEqual(header_node_fct.else_node.node_type, "exit", "For-ComplexTarget: Header else path should be exit")

    def test_if_else_join_points(self):
        code_if_else_simple_join = """
a = 1 
if a > 0:
    x = 10
else:
    x = 20
y = x 
"""
        cfg = self.builder.build_cfg(code_if_else_simple_join)
        self.assertEqual(self._count_nodes(cfg), 7, "IESJ: Node count mismatch")

        assign_node_a = self._find_node_by_statement(cfg, "a = 1")
        self.assertIsNotNone(assign_node_a, "IESJ: Assign 'a = 1' not found")
        
        cond_node_a = self._find_node_by_statement(cfg, "a > 0")
        self.assertIsNotNone(cond_node_a, "IESJ: Condition 'a > 0' not found")
        self.assertIs(assign_node_a.next_node, cond_node_a, "IESJ: Assign 'a=1' should link to Cond 'a>0'")
        
        true_branch_end = self._find_node_by_statement(cfg, "x = 10")
        self.assertIsNotNone(true_branch_end, "IESJ: True branch 'x = 10' not found")
        
        false_branch_end = self._find_node_by_statement(cfg, "x = 20")
        self.assertIsNotNone(false_branch_end, "IESJ: False branch 'x = 20' not found")
        
        join_node_y = self._find_node_by_statement(cfg, "y = x")
        self.assertIsNotNone(join_node_y, "IESJ: Join node 'y = x' not found")

        self.assertIs(true_branch_end.next_node, join_node_y, "IESJ: True branch should link to join node")
        self.assertIs(false_branch_end.next_node, join_node_y, "IESJ: False branch should link to join node")

        code_if_no_else_simple_join = """
a = 1
if a > 0:
    x = 10
y = x 
"""
        cfg_no_else = self.builder.build_cfg(code_if_no_else_simple_join)
        self.assertEqual(self._count_nodes(cfg_no_else), 6, "INE_SJ: Node count mismatch")

        assign_node_a_ne = self._find_node_by_statement(cfg_no_else, "a = 1")
        self.assertIsNotNone(assign_node_a_ne, "INE_SJ: Assign 'a = 1' not found")

        cond_node_a_ne = self._find_node_by_statement(cfg_no_else, "a > 0")
        self.assertIsNotNone(cond_node_a_ne, "INE_SJ: Condition 'a > 0' not found")
        self.assertIs(assign_node_a_ne.next_node, cond_node_a_ne, "INE_SJ: Assign 'a=1' should link to Cond 'a>0'")
        
        true_branch_end_ne = self._find_node_by_statement(cfg_no_else, "x = 10")
        self.assertIsNotNone(true_branch_end_ne, "INE_SJ: True branch 'x = 10' not found")
        
        join_node_y_ne = self._find_node_by_statement(cfg_no_else, "y = x")
        self.assertIsNotNone(join_node_y_ne, "INE_SJ: Join node 'y = x' not found")

        self.assertIs(true_branch_end_ne.next_node, join_node_y_ne, "INE_SJ: True branch should link to join node")
        self.assertIs(cond_node_a_ne.else_node, join_node_y_ne, "INE_SJ: Condition's false path should link to join node")

        code_if_else_complex_join = """
a = 1
if a > 0:
    b = 1
else:
    b = 2
if b == 1:
    c = 3
else:
    c = 4
d = c
"""
        cfg_complex = self.builder.build_cfg(code_if_else_complex_join)
        self.assertEqual(self._count_nodes(cfg_complex), 11, "IECJ: Node count mismatch")

        assign_node_a_c = self._find_node_by_statement(cfg_complex, "a = 1")
        self.assertIsNotNone(assign_node_a_c, "IECJ: Assign 'a = 1' not found")
        cond_node_A = self._find_node_by_statement(cfg_complex, "a > 0")
        self.assertIsNotNone(cond_node_A, "IECJ: Condition 'a > 0' not found")
        self.assertIs(assign_node_a_c.next_node, cond_node_A, "IECJ: Assign 'a=1' should link to Cond 'a>0'")

        true_branch_A = self._find_node_by_statement(cfg_complex, "b = 1")
        self.assertIsNotNone(true_branch_A, "IECJ: Node 'b = 1' not found")
        false_branch_A = self._find_node_by_statement(cfg_complex, "b = 2")
        self.assertIsNotNone(false_branch_A, "IECJ: Node 'b = 2' not found")
        
        cond_node_B = self._find_node_by_statement(cfg_complex, "b == 1")
        self.assertIsNotNone(cond_node_B, "IECJ: Condition 'b == 1' not found")

        self.assertIsNotNone(true_branch_A.next_node, "IECJ: True branch A has no successor")
        self.assertIsNotNone(false_branch_A.next_node, "IECJ: False branch A has no successor")
        self.assertIs(true_branch_A.next_node, false_branch_A.next_node, "IECJ: Branches of A should lead to the same merge node")
        
        merge_node_1 = true_branch_A.next_node
        self.assertEqual(merge_node_1.node_type, "merge_point", "IECJ: Expected merge_point node after first if/else")
        self.assertEqual(len(merge_node_1.statements), 0, "IECJ: Merge_point node should have no statements")
        self.assertIs(merge_node_1.next_node, cond_node_B, "IECJ: Merge_point should lead to the second If condition")

        # Assertions for the second if/else block and its join point
        true_branch_B = self._find_node_by_statement(cfg_complex, "c = 3")
        self.assertIsNotNone(true_branch_B, "IECJ: Node 'c = 3' not found")
        false_branch_B = self._find_node_by_statement(cfg_complex, "c = 4")
        self.assertIsNotNone(false_branch_B, "IECJ: Node 'c = 4' not found")
        assign_node_d = self._find_node_by_statement(cfg_complex, "d = c")
        self.assertIsNotNone(assign_node_d, "IECJ: Node 'd = c' not found")

        self.assertIs(self._get_actual_target_node(cond_node_B.branch_node), true_branch_B, "IECJ: Cond B true branch should link to 'c=3'")
        self.assertIs(self._get_actual_target_node(cond_node_B.else_node), false_branch_B, "IECJ: Cond B false branch should link to 'c=4'")

        self.assertIs(true_branch_B.next_node, assign_node_d, "IECJ: Node 'c=3' should link to 'd=c'")
        self.assertIs(false_branch_B.next_node, assign_node_d, "IECJ: Node 'c=4' should link to 'd=c'")
        self.assertEqual(assign_node_d.next_node.node_type, "exit", "IECJ: Node 'd=c' should link to EXIT")


        code_if_no_else_complex_join = """
a = 1
if a > 0:
    b = 1
if b == 1: # Note: b might not be defined if a <= 0, this is for CFG structure test
    c = 3
else:
    c = 4
d = c
"""
        cfg_no_else_complex = self.builder.build_cfg(code_if_no_else_complex_join)
        self.assertEqual(self._count_nodes(cfg_no_else_complex), 10, "INE_CJ: Node count mismatch")

        assign_node_a_nec = self._find_node_by_statement(cfg_no_else_complex, "a = 1")
        self.assertIsNotNone(assign_node_a_nec, "INE_CJ: Assign 'a = 1' not found")
        cond_node_A_nec = self._find_node_by_statement(cfg_no_else_complex, "a > 0")
        self.assertIsNotNone(cond_node_A_nec, "INE_CJ: Condition 'a > 0' not found")
        self.assertIs(assign_node_a_nec.next_node, cond_node_A_nec, "INE_CJ: Assign 'a=1' should link to Cond 'a>0'")

        true_branch_A_nec = self._find_node_by_statement(cfg_no_else_complex, "b = 1")
        self.assertIsNotNone(true_branch_A_nec, "INE_CJ: Node 'b = 1' not found")
        
        cond_node_B_nec = self._find_node_by_statement(cfg_no_else_complex, "b == 1") # This will be after merge
        self.assertIsNotNone(cond_node_B_nec, "INE_CJ: Condition 'b == 1' not found")

        self.assertIsNotNone(true_branch_A_nec.next_node, "INE_CJ: True branch A has no successor (should go to merge)")
        self.assertIsNotNone(cond_node_A_nec.else_node, "INE_CJ: False path of cond A has no successor (should go to merge)")

        # Both paths from the first 'if' (true branch 'b=1' and the implicit false path)
        # should merge before the second 'if b == 1'.
        # Let's find this merge point.
        # If true_branch_A_nec.next_node is the merge point:
        merge_node_ine_cj = true_branch_A_nec.next_node
        self.assertIs(cond_node_A_nec.else_node, merge_node_ine_cj, "INE_CJ: Paths from first If should lead to same merge node")
        self.assertEqual(merge_node_ine_cj.node_type, "merge_point", "INE_CJ: Expected merge_point node")
        self.assertEqual(len(merge_node_ine_cj.statements), 0, "INE_CJ: Merge_point node should be empty")
        self.assertIs(merge_node_ine_cj.next_node, cond_node_B_nec, "INE_CJ: Merge_point should lead to second If condition")

        # Continue assertions for the second if/else block
        true_branch_B_nec = self._find_node_by_statement(cfg_no_else_complex, "c = 3")
        self.assertIsNotNone(true_branch_B_nec, "INE_CJ: Node 'c = 3' not found")
        false_branch_B_nec = self._find_node_by_statement(cfg_no_else_complex, "c = 4")
        self.assertIsNotNone(false_branch_B_nec, "INE_CJ: Node 'c = 4' not found")
        assign_node_d_nec = self._find_node_by_statement(cfg_no_else_complex, "d = c")
        self.assertIsNotNone(assign_node_d_nec, "INE_CJ: Node 'd = c' not found")

        self.assertIs(self._get_actual_target_node(cond_node_B_nec.branch_node), true_branch_B_nec)
        self.assertIs(self._get_actual_target_node(cond_node_B_nec.else_node), false_branch_B_nec)
        self.assertIs(true_branch_B_nec.next_node, assign_node_d_nec)
        self.assertIs(false_branch_B_nec.next_node, assign_node_d_nec)
        self.assertEqual(assign_node_d_nec.next_node.node_type, "exit")


    def test_leading_statement_before_if(self):
        code = """
x = 1
if x != 1:
    print("OK")
else:
    print("Not OK")
"""
        cfg_start_node = self.builder.build_cfg(code)

        self.assertIsNotNone(cfg_start_node, "CFG start node should exist")
        self.assertEqual(cfg_start_node.node_type, "start_point", "Start node type mismatch")

        assign_node = self._find_node_by_statement(cfg_start_node, "x = 1")
        self.assertIsNotNone(assign_node, "Node 'x = 1' not found")
        self.assertEqual(assign_node.node_type, "assignment", "Node 'x = 1' type mismatch")

        condition_node = self._find_node_by_statement(cfg_start_node, "x != 1")
        self.assertIsNotNone(condition_node, "Condition node 'x != 1' not found")
        self.assertEqual(condition_node.node_type, "condition", "Condition node 'x != 1' type mismatch")

        self.assertIs(assign_node.next_node, condition_node,
                      "Node 'x = 1' should directly lead to condition 'x != 1'")

        true_branch_node = self._find_node_by_statement(cfg_start_node, "print('OK')")
        self.assertIsNotNone(true_branch_node, "True branch node print('OK') not found")
        self.assertIn(true_branch_node.node_type, ["function_call", "expression_statement"], "True branch node type mismatch")

        self.assertIs(condition_node.branch_node, true_branch_node,
                      "Condition node 'x != 1' true branch should lead to 'print(\"OK\")'")

        false_branch_node = self._find_node_by_statement(cfg_start_node, "print('Not OK')")
        self.assertIsNotNone(false_branch_node, "False branch node print('Not OK') not found")
        self.assertIn(false_branch_node.node_type, ["function_call", "expression_statement"], "False branch node type mismatch")

        self.assertIs(condition_node.else_node, false_branch_node,
                      "Condition node 'x != 1' else branch should lead to 'print(\"Not OK\")'")

        exit_node = self._find_node_by_statement(cfg_start_node, "EXIT")
        self.assertIsNotNone(exit_node, "Exit node not found") # This test case should still have an EXIT node
        self.assertEqual(exit_node.node_type, "exit", "Exit node type mismatch")

        self.assertIs(true_branch_node.next_node, exit_node,
                      "True branch 'print(\"OK\")' should lead to EXIT")
        self.assertIs(false_branch_node.next_node, exit_node,
                      "False branch 'print(\"Not OK\")' should lead to EXIT")
        self.assertEqual(self._count_nodes(cfg_start_node), 6, "Node count mismatch for leading statement before if")

    def test_return_statements(self):
        code = """
if (x < y):
    return
print(x)
return
"""
        cfg_start_node = self.builder.build_cfg(code)
        self.assertIsNotNone(cfg_start_node, "CFG start node should exist")

        condition_node = self._find_node_by_statement(cfg_start_node, "x < y")
        self.assertIsNotNone(condition_node, "Condition node 'x < y' not found")
        self.assertEqual(condition_node.node_type, "condition", "Condition node 'x < y' type mismatch")

        self.assertIs(cfg_start_node.next_node, condition_node, "Start node should link to condition node 'x < y'")

        if_return_node = self._find_node_by_statement(cfg_start_node, "return")
        self.assertIsNotNone(if_return_node, "Return node inside if block not found")
        self.assertEqual(if_return_node.node_type, "return_statement", "Return node inside if block type mismatch")

        current_node_path = condition_node.branch_node
        while current_node_path and not current_node_path.statements and current_node_path.node_type == "statement_block":
            current_node_path = current_node_path.next_node
        self.assertIs(current_node_path, if_return_node, "Condition node 'x < y' true branch should lead to the first return node")

        self.assertIsNone(if_return_node.next_node, "if_return_node.next_node should be None")
        self.assertIsNone(if_return_node.branch_node, "if_return_node.branch_node should be None")
        self.assertIsNone(if_return_node.else_node, "if_return_node.else_node should be None")

        print_node = self._find_node_by_statement(cfg_start_node, "print(x)")
        self.assertIsNotNone(print_node, "Node 'print(x)' not found")
        self.assertIn(print_node.node_type, ["function_call", "expression_statement"], "print(x) node type mismatch")

        current_node_path_else = condition_node.else_node
        while current_node_path_else and not current_node_path_else.statements and current_node_path_else.node_type == "statement_block":
            current_node_path_else = current_node_path_else.next_node
        self.assertIs(current_node_path_else, print_node, "Condition node 'x < y' else branch should lead to 'print(x)'")

        main_return_node = None
        if print_node.next_node and print_node.next_node.node_type == "return_statement":
            main_return_node = print_node.next_node

        self.assertIsNotNone(main_return_node, "Main return node after 'print(x)' not found or not directly linked")
        if main_return_node:
             self.assertEqual(main_return_node.node_type, "return_statement", "Main return node type mismatch")
             self.assertNotEqual(if_return_node.id, main_return_node.id, "Should find two distinct return nodes")
             self.assertIsNone(main_return_node.next_node, "main_return_node.next_node should be None")
             self.assertIsNone(main_return_node.branch_node, "main_return_node.branch_node should be None")
             self.assertIsNone(main_return_node.else_node, "main_return_node.else_node should be None")

        # MODIFIED SECTION
        exit_node_main = self._find_node_by_statement(cfg_start_node, "EXIT")
        self.assertIsNone(exit_node_main, "A global EXIT node should NOT be found when all paths return")

        # Expected node count: Start, Cond, Ret1, Print, Ret2 = 5 nodes (no global EXIT)
        self.assertEqual(self._count_nodes(cfg_start_node), 5, "Node count should be 5 when no global EXIT node is present due to all paths returning")
        # END OF MODIFIED SECTION

    def _get_actual_target_node(self, node: CFGNode) -> CFGNode | None:
        # Helper to skip over an empty intermediate block if present
        if node and not node.statements and node.next_node and \
           node.node_type == "statement_block" and not node.branch_node and not node.else_node:
            return node.next_node
        return node

    def test_match_case_statements(self):
        # Test 1: Basic Match with Wildcard
        code1 = """
c = "L"
y = 0 # Initialize y
match c:
    case 'N':
        y = 25
    case 'Y':
        y = 50
    case _:
        y = 0  # Default case
print(y)
"""
        cfg1 = self.builder.build_cfg(code1)

        # Find initial nodes
        assign_c_node1 = self._find_node_by_statement(cfg1, 'c =')
        self.assertTrue(assign_c_node1 and any('L' in stmt for stmt in assign_c_node1.statements), "T1: Assign 'c' content check failed")

        assign_y_init_node1 = self._find_node_by_statement(assign_c_node1, 'y =')
        self.assertTrue(assign_y_init_node1 and any('0' in stmt for stmt in assign_y_init_node1.statements if "case _" not in stmt), "T1: Assign 'y=0' (init) content check failed") # Ensure not the wildcard y=0

        match_node1 = self._find_node_by_statement(assign_y_init_node1, 'match c')
        self.assertIsNotNone(match_node1, "T1: 'match c' (dispatcher) node not found")
        self.assertEqual(match_node1.node_type, "match_dispatcher", "T1: Match node type should be 'match_dispatcher'")

        # Verify case_branches
        self.assertEqual(len(match_node1.case_branches), 3, "T1: Should have 3 case branches")

        print_y_node1 = self._find_node_by_statement(cfg1, "print(y)")
        self.assertIsNotNone(print_y_node1, "T1: 'print(y)' node not found")

        # Case 'N'
        label_N, body_N_entry_node = match_node1.case_branches[0]
        self.assertEqual(label_N, "c == 'N'", "T1: Label for case 'N' incorrect") # MODIFIED
        self.assertIsNotNone(body_N_entry_node, "T1: Body entry for case 'N' is None")
        assign_y25_node1 = self._find_node_by_statement(self._get_actual_target_node(body_N_entry_node), "y =")
        self.assertTrue(assign_y25_node1 and any('25' in stmt for stmt in assign_y25_node1.statements), "T1: Assign 'y = 25' content check failed")
        self.assertIs(self._get_actual_target_node(body_N_entry_node), assign_y25_node1, "T1: Link body_N_entry -> y = 25")

        # Case 'Y'
        label_Y, body_Y_entry_node = match_node1.case_branches[1]
        self.assertEqual(label_Y, "c == 'Y'", "T1: Label for case 'Y' incorrect") # MODIFIED
        self.assertIsNotNone(body_Y_entry_node, "T1: Body entry for case 'Y' is None")
        assign_y50_node1 = self._find_node_by_statement(self._get_actual_target_node(body_Y_entry_node), "y =")
        self.assertTrue(assign_y50_node1 and any('50' in stmt for stmt in assign_y50_node1.statements), "T1: Assign 'y = 50' content check failed")
        self.assertIs(self._get_actual_target_node(body_Y_entry_node), assign_y50_node1, "T1: Link body_Y_entry -> y = 50")

        # Case '_'
        label_W, body_W_entry_node = match_node1.case_branches[2]
        self.assertEqual(label_W, "'default'", "T1: Label for case '_' incorrect") # MODIFIED
        self.assertIsNotNone(body_W_entry_node, "T1: Body entry for case '_' is None")
        assign_y0_node1 = self._find_node_by_statement(self._get_actual_target_node(body_W_entry_node), "y =")
        self.assertTrue(assign_y0_node1 and any('0' in stmt for stmt in assign_y0_node1.statements), "T1: Assign 'y = 0' (wildcard) content check failed")
        self.assertIs(self._get_actual_target_node(body_W_entry_node), assign_y0_node1, "T1: Link body_W_entry -> y = 0")

        # All case bodies should now link directly to print_y_node1
        self.assertIs(assign_c_node1.next_node, assign_y_init_node1, "T1: Link c -> y_init")
        self.assertIs(assign_y_init_node1.next_node, match_node1, "T1: Link y_init -> match c")

        self.assertIs(assign_y25_node1.next_node, print_y_node1, "T1: Link y25 -> print(y)")
        self.assertIs(assign_y50_node1.next_node, print_y_node1, "T1: Link y50 -> print(y)")
        self.assertIs(assign_y0_node1.next_node, print_y_node1, "T1: Link y0 (wildcard) -> print(y)")

        # If a wildcard exists, match_node itself is not considered a direct exit path to print_y_node1
        # unless all case branches terminate (e.g. return), which is not the case here.
        # The existing logic for visit_Match when wildcard_case_exists = True does not add match_node to final_exit_nodes.
        # So, its next_node might not be set by build_cfg if it's not a loose end.
        # However, if it *were* a loose end (e.g. if the wildcard case also returned), this might be different.
        # For this test, the wildcard case y=0 flows to print(y).
        # Let's confirm match_node.next_node is NOT print_y_node1 directly, it's up to case branches.
        self.assertIsNot(match_node1.next_node, print_y_node1, "T1: match_node.next_node should not directly lead to print(y) when wildcard path exists and flows.")

        self.assertEqual(self._count_nodes(cfg1), 12, "T1: Node count mismatch (expected 1 less due to no end_match_node)")


        # Test 2: Match with No Wildcard (Fallthrough)
        code2 = """
val = 3
match val:
    case 1:
        x = 10
    case 2:
        x = 20
print(val)
"""
        cfg2 = self.builder.build_cfg(code2)
        assign_val_node2 = self._find_node_by_statement(cfg2, 'val =')
        self.assertTrue(assign_val_node2 and any('3' in stmt for stmt in assign_val_node2.statements))
        match_node2 = self._find_node_by_statement(assign_val_node2, 'match val')
        self.assertIsNotNone(match_node2)
        self.assertEqual(match_node2.node_type, "match_dispatcher")

        self.assertEqual(len(match_node2.case_branches), 2)
        print_val_node2 = self._find_node_by_statement(cfg2, "print(val)")
        self.assertIsNotNone(print_val_node2)

        # Case 1
        label1, body1_entry = match_node2.case_branches[0]
        self.assertEqual(label1, "val == 1") # MODIFIED
        self.assertIsNotNone(body1_entry)
        assign_x10_node2 = self._find_node_by_statement(self._get_actual_target_node(body1_entry), "x =")
        self.assertTrue(assign_x10_node2 and any('10' in stmt for stmt in assign_x10_node2.statements))
        self.assertIs(self._get_actual_target_node(body1_entry), assign_x10_node2)

        # Case 2
        label2, body2_entry = match_node2.case_branches[1]
        self.assertEqual(label2, "val == 2") # MODIFIED
        self.assertIsNotNone(body2_entry)
        assign_x20_node2 = self._find_node_by_statement(self._get_actual_target_node(body2_entry), "x =")
        self.assertTrue(assign_x20_node2 and any('20' in stmt for stmt in assign_x20_node2.statements))
        self.assertIs(self._get_actual_target_node(body2_entry), assign_x20_node2)

        # Case bodies link to print_val_node2
        # Fallthrough from match_node (no wildcard) also links to print_val_node2
        self.assertIs(assign_val_node2.next_node, match_node2, "T2: Link val -> match val")
        self.assertIs(assign_x10_node2.next_node, print_val_node2, "T2: Link x10 -> print(val)")
        self.assertIs(assign_x20_node2.next_node, print_val_node2, "T2: Link x20 -> print(val)")

        # match_node itself is a loose end returned by visit_Match, build_cfg links it.
        self.assertIs(match_node2.next_node, print_val_node2, "T2: Fallthrough from match_node to print(val)")

        self.assertEqual(self._count_nodes(cfg2), 9, "T2: Node count mismatch (expected 1 less due to no end_match_node)")


        # Test 3: Match with Guard
        code3 = """
num = 10
match num:
    case x if x > 0:
        result = "positive"
    case 0:
        result = "zero"
    case _:
        result = "negative"
print(result)
"""
        cfg3 = self.builder.build_cfg(code3)
        assign_num_node3 = self._find_node_by_statement(cfg3, 'num =')
        self.assertTrue(assign_num_node3 and any('10' in stmt for stmt in assign_num_node3.statements))
        match_node3 = self._find_node_by_statement(assign_num_node3, 'match num')
        self.assertIsNotNone(match_node3)
        self.assertEqual(match_node3.node_type, "match_dispatcher")

        self.assertEqual(len(match_node3.case_branches), 3)
        print_result_node3 = self._find_node_by_statement(cfg3, "print(result)")
        self.assertIsNotNone(print_result_node3)

        # Case x if x > 0
        label_g, body_g_entry = match_node3.case_branches[0]
        self.assertEqual(label_g, "(num matches x) if x > 0") # MODIFIED
        self.assertIsNotNone(body_g_entry)
        assign_pos_node3 = self._find_node_by_statement(self._get_actual_target_node(body_g_entry), "result =")
        self.assertTrue(assign_pos_node3 and any('positive' in stmt for stmt in assign_pos_node3.statements))
        self.assertIs(self._get_actual_target_node(body_g_entry), assign_pos_node3)

        # Case 0
        label_0, body_0_entry = match_node3.case_branches[1]
        self.assertEqual(label_0, "num == 0") # MODIFIED
        self.assertIsNotNone(body_0_entry)
        assign_zero_node3 = self._find_node_by_statement(self._get_actual_target_node(body_0_entry), "result =")
        self.assertTrue(assign_zero_node3 and any('zero' in stmt for stmt in assign_zero_node3.statements))
        self.assertIs(self._get_actual_target_node(body_0_entry), assign_zero_node3)

        # Case _
        label_w, body_w_entry = match_node3.case_branches[2]
        self.assertEqual(label_w, "'default'") # MODIFIED
        self.assertIsNotNone(body_w_entry)
        assign_neg_node3 = self._find_node_by_statement(self._get_actual_target_node(body_w_entry), "result =")
        self.assertTrue(assign_neg_node3 and any('negative' in stmt for stmt in assign_neg_node3.statements))
        self.assertIs(self._get_actual_target_node(body_w_entry), assign_neg_node3)

        # All case bodies should now link directly to print_result_node3
        self.assertIs(assign_num_node3.next_node, match_node3, "T3: Link num -> match num")
        self.assertIs(assign_pos_node3.next_node, print_result_node3, "T3: Link positive -> print(result)")
        self.assertIs(assign_zero_node3.next_node, print_result_node3, "T3: Link zero -> print(result)")
        self.assertIs(assign_neg_node3.next_node, print_result_node3, "T3: Link negative (wildcard) -> print(result)")

        # Similar to Test 1, match_node.next_node behavior with wildcard.
        self.assertIsNot(match_node3.next_node, print_result_node3, "T3: match_node.next_node should not directly lead to print(result) when wildcard path exists and flows.")

        self.assertEqual(self._count_nodes(cfg3), 11, "T3: Node count mismatch (expected 1 less due to no end_match_node)")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
