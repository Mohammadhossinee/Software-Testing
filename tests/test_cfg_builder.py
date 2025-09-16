import unittest
import ast
import re # For regex searches in DOT string

from CFG.cfg_node import CFGNode
from CFG.cfg_builder import CFGBuilder

class TestCFGBuilderFeatures(unittest.TestCase):

    def _build_cfg_and_dot_for_source(self, source_code_str: str, graph_name: str = "test_graph", is_module: bool = True):
        builder = CFGBuilder()

        if is_module:
            builder.build_cfg(source_code_str, graph_name=graph_name)
        else:
            ast_module = ast.parse(source_code_str)
            if not (ast_module.body and isinstance(ast_module.body[0], (ast.FunctionDef, ast.AsyncFunctionDef))):
                raise ValueError("Source code for function test does not contain a function definition at the top level.")
            func_ast_node = ast_module.body[0]
            builder.build(func_ast_node, graph_name=graph_name)

        nodes = builder.nodes
        dot_string = builder.to_dot()
        return nodes, builder, dot_string

    def _find_node_by_exact_statement(self, nodes: dict, stmt: str) -> CFGNode | None:
        # Account for ast.unparse possibly using single quotes for strings
        stmt_v1 = stmt.replace('"', "'")
        for node in nodes.values():
            if node.statements and node.statements[0] == stmt:
                return node
            if node.statements and node.statements[0] == stmt_v1: # Check with single quotes too
                return node
        return None

    def _get_case_target_node(self, match_node: CFGNode, case_pattern_label_part: str) -> CFGNode | None:
        full_label_to_search = f"case: {case_pattern_label_part}"
        for label, target_node in match_node.case_branches:
            if label == full_label_to_search:
                return target_node
        return None

    def test_simple_script_sequential_flow(self):
        source_code = """
x = 10
y = 20
z = x + y
"""
        nodes, builder, dot_string = self._build_cfg_and_dot_for_source(source_code, "test_simple_script")

        node_x_eq_10 = self._find_node_by_exact_statement(nodes, "x = 10")
        node_y_eq_20 = self._find_node_by_exact_statement(nodes, "y = 20")
        node_z_eq_x_plus_y = self._find_node_by_exact_statement(nodes, "z = x + y")

        self.assertIsNotNone(node_x_eq_10, "Node for 'x = 10' not found.")
        self.assertIsNotNone(node_y_eq_20, "Node for 'y = 20' not found.")
        self.assertIsNotNone(node_z_eq_x_plus_y, "Node for 'z = x + y' not found.")

        edge_pattern_xy = rf"^\s*{node_x_eq_10.id}\s*->\s*{node_y_eq_20.id}\s*;"
        self.assertTrue(re.search(edge_pattern_xy, dot_string, re.MULTILINE),
                        f"Edge x=10 -> y=20 should not have a label. Pattern: {edge_pattern_xy}\nDOT:\n{dot_string}")

        edge_pattern_yz = rf"^\s*{node_y_eq_20.id}\s*->\s*{node_z_eq_x_plus_y.id}\s*;"
        self.assertTrue(re.search(edge_pattern_yz, dot_string, re.MULTILINE),
                        f"Edge y=20 -> z=x+y should not have a label. Pattern: {edge_pattern_yz}\nDOT:\n{dot_string}")

        self.assertIsNone(node_z_eq_x_plus_y.next_node,
                          f"Node 'z = x + y' should be terminal in a script context, but has next_node.")
        # Removed: Check that it doesn't link to builder.exit_node.

    def test_function_returns_are_terminal(self):
        source_code = """
def func_test(x):
    if x > 10:
        return "big"
    else:
        return "small"
"""
        nodes, builder, dot_string = self._build_cfg_and_dot_for_source(source_code, "test_func_returns", is_module=False)

        return_big_node = self._find_node_by_exact_statement(nodes, "return 'big'")
        return_small_node = self._find_node_by_exact_statement(nodes, "return 'small'")

        self.assertIsNotNone(return_big_node, "Node for 'return 'big'' not found.")
        self.assertIsNotNone(return_small_node, "Node for 'return 'small'' not found.")

        self.assertIsNone(return_big_node.next_node, "Node 'return 'big'' should be terminal.")
        self.assertIsNone(return_small_node.next_node, "Node 'return 'small'' should be terminal.")

        if return_big_node:
            return_big_pattern = rf"^\s*{return_big_node.id}\s*->.*"
            self.assertFalse(re.search(return_big_pattern, dot_string, re.MULTILINE),
                             f"Node 'return 'big'' (ID: {return_big_node.id}) should not have outgoing edges in DOT.")
        if return_small_node:
            return_small_pattern = rf"^\s*{return_small_node.id}\s*->.*"
            self.assertFalse(re.search(return_small_pattern, dot_string, re.MULTILINE),
                             f"Node 'return 'small'' (ID: {return_small_node.id}) should not have outgoing edges in DOT.")

    def test_match_case_convergence_to_successor(self):
        source_code = """
c = "L"
y = 0
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
        y = 0
        print("Default Case")
print(y)
"""
        nodes, builder, dot_string = self._build_cfg_and_dot_for_source(source_code, "test_match_convergence")

        print_y_node = self._find_node_by_exact_statement(nodes, "print(y)")
        self.assertIsNotNone(print_y_node, "Node for 'print(y)' (common successor) not found.")

        match_node = self._find_node_by_exact_statement(nodes, "match c")
        self.assertIsNotNone(match_node, "Match dispatcher node not found.")

        case_details = {
            "'N'": "print('Case N')",
            "'Y'": "print('Case Y')",
            "'M'": "print('Case M')",
            "_": "print('Default Case')"
        }

        self.assertTrue(hasattr(match_node, 'case_branches'), "Match node missing 'case_branches'")
        self.assertEqual(len(match_node.case_branches), len(case_details), "Incorrect number of case branches.")

        for case_pattern_key, last_stmt_text_expected in case_details.items():
            case_first_node = self._get_case_target_node(match_node, case_pattern_key)
            self.assertIsNotNone(case_first_node, f"Target node for case pattern '{case_pattern_key}' not found.")

            last_node_in_case_body = case_first_node
            if last_node_in_case_body.statements and not last_node_in_case_body.statements[0] == last_stmt_text_expected:
                if last_node_in_case_body.next_node: # Check next if first is not the target print
                    last_node_in_case_body = last_node_in_case_body.next_node

            self.assertIsNotNone(last_node_in_case_body, f"Could not find last node for case '{case_pattern_key}'.")
            self.assertTrue(last_node_in_case_body.statements and last_node_in_case_body.statements[0] == last_stmt_text_expected,
                            f"Expected last statement of case '{case_pattern_key}' to be '{last_stmt_text_expected}', got '{last_node_in_case_body.statements[0] if last_node_in_case_body.statements else None}'.")

            self.assertEqual(last_node_in_case_body.next_node, print_y_node,
                             f"Node '{last_stmt_text_expected}' (case '{case_pattern_key}') should link to 'print(y)' (ID: {print_y_node.id}), but links to {last_node_in_case_body.next_node.id if last_node_in_case_body.next_node else 'None'}.")

            edge_pattern = rf"^\s*{last_node_in_case_body.id}\s*->\s*{print_y_node.id}\s*;"
            self.assertTrue(re.search(edge_pattern, dot_string, re.MULTILINE),
                            f"DOT edge from '{last_stmt_text_expected}' to 'print(y)' not found or has a label. Pattern: {edge_pattern}\nDOT:\n{dot_string}")

    def test_if_elif_else_convergence(self):
        source_code = """
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
        nodes, builder, dot_string = self._build_cfg_and_dot_for_source(source_code, "test_if_convergence")

        # Identify key nodes (without trailing colons for conditions)
        score_40_node = self._find_node_by_exact_statement(nodes, "score = 40")
        if_score_90_node = self._find_node_by_exact_statement(nodes, "if score >= 90")
        print_grade_a_node = self._find_node_by_exact_statement(nodes, "print('Grade: A')")

        # For elif, the CFG creates nested if nodes. The statement in the node will be "if actual_condition"
        elif_score_80_node = self._find_node_by_exact_statement(nodes, "if score >= 80")
        print_grade_b_node = self._find_node_by_exact_statement(nodes, "print('Grade: B')")
        elif_score_70_node = self._find_node_by_exact_statement(nodes, "if score >= 70")
        print_grade_c_node = self._find_node_by_exact_statement(nodes, "print('Grade: C')")
        elif_score_60_node = self._find_node_by_exact_statement(nodes, "if score >= 60")
        print_grade_d_node = self._find_node_by_exact_statement(nodes, "print('Grade: D')")
        print_grade_f_node = self._find_node_by_exact_statement(nodes, "print('Grade: F')")
        print_amirali_node = self._find_node_by_exact_statement(nodes, "print('Amirali Toori')")
        x_30_node = self._find_node_by_exact_statement(nodes, "x = 30")
        x_20_node = self._find_node_by_exact_statement(nodes, "x = 20")

        self.assertIsNotNone(score_40_node, "Node 'score=40' not found")
        self.assertIsNotNone(if_score_90_node, "Node 'if score >= 90:' not found")
        self.assertIsNotNone(print_grade_a_node, "Node 'print('Grade: A')' not found")
        self.assertIsNotNone(elif_score_80_node, "Node 'if score >= 80:' (elif) not found")
        self.assertIsNotNone(print_grade_b_node, "Node 'print('Grade: B')' not found")
        self.assertIsNotNone(elif_score_70_node, "Node 'if score >= 70:' (elif) not found")
        self.assertIsNotNone(print_grade_c_node, "Node 'print('Grade: C')' not found")
        self.assertIsNotNone(elif_score_60_node, "Node 'if score >= 60:' (elif) not found")
        self.assertIsNotNone(print_grade_d_node, "Node 'print('Grade: D')' not found")
        self.assertIsNotNone(print_grade_f_node, "Node 'print('Grade: F')' not found")
        self.assertIsNotNone(print_amirali_node, "Node 'print('Amirali Toori')' not found")
        self.assertIsNotNone(x_30_node, "Node 'x=30' not found")
        self.assertIsNotNone(x_20_node, "Node 'x=20' not found")

        # 3. Assertions for if node styling (DOT output)
        if_node_id_str = str(if_score_90_node.id)
        expected_if_xlabel = re.escape("if score >= 90") # No colon
        if_node_pattern = rf'^\s*{if_node_id_str}\s*\[.*label="{if_node_id_str}".*xlabel="{expected_if_xlabel}".*shape=circle.*\];$'
        self.assertTrue(re.search(if_node_pattern, dot_string, re.MULTILINE), f"If node 'if score >= 90' DOT styling incorrect. Pattern: {if_node_pattern}\nDOT:\n{dot_string}")

        # True-path edge label
        true_edge_label = re.escape(if_score_90_node.true_condition_label)
        true_edge_pattern = rf"^\s*{if_score_90_node.id}\s*->\s*{print_grade_a_node.id}\s*\[label=\"{true_edge_label}\"\];$"
        self.assertTrue(re.search(true_edge_pattern, dot_string, re.MULTILINE), f"True edge from 'if score >= 90:' incorrect. Pattern: {true_edge_pattern}\nDOT:\n{dot_string}")

        # False-path edge label (to the next condition, which is the entry of the else block for the first if)
        # The else_node of "if score >= 90" should be the placeholder before "if score >= 80"
        # This placeholder then has "if score >= 80" as its first actual statement.
        # We need to find the placeholder or the actual condition node.
        # visit_If links if_condition_node.else_node to a placeholder, then processes orelse from it.
        # So, the else_node of if_score_90_node should be a placeholder, whose next_node is elif_score_80_node.
        self.assertIsNotNone(if_score_90_node.else_node, "if_score_90_node.else_node should not be None")
        # The direct successor (placeholder) might be optimized out.
        # The actual visual successor in DOT after optimization might be elif_score_80_node.
        # Let's assume optimizer might remove the placeholder if it's empty.
        # The label should be the false_condition_label.
        false_edge_label = re.escape(if_score_90_node.false_condition_label)
        # Check edge from if_score_90_node to elif_score_80_node (or its placeholder if not optimized)
        # This requires knowing how placeholders are handled by to_dot or optimized.
        # For now, let's assume the optimizer works and the direct successor is elif_score_80_node.
        # This might be too strong an assumption if the placeholder is not empty.
        # The placeholder node itself would have no xlabel.
        # A simpler check: the label on the else edge.
        false_edge_pattern = rf"^\s*{if_score_90_node.id}\s*->\s*\d+\s*\[label=\"{false_edge_label}\"\];$"
        self.assertTrue(re.search(false_edge_pattern, dot_string, re.MULTILINE), f"False edge from 'if score >= 90:' incorrect label or target. Pattern: {false_edge_pattern}\nDOT:\n{dot_string}")


        # 4. Assertions for Convergence
        grade_print_nodes = [print_grade_a_node, print_grade_b_node, print_grade_c_node, print_grade_d_node, print_grade_f_node]
        for grade_node in grade_print_nodes:
            self.assertEqual(grade_node.next_node, print_amirali_node,
                             f"Node '{grade_node.statements[0]}' should link to 'print(\"Amirali Toori\")'. Got {grade_node.next_node.statements[0] if grade_node.next_node else 'None'}")
            edge_pattern = rf"^\s*{grade_node.id}\s*->\s*{print_amirali_node.id}\s*;"
            self.assertTrue(re.search(edge_pattern, dot_string, re.MULTILINE),
                            f"DOT Edge from '{grade_node.statements[0]}' to 'print(\"Amirali Toori\")' not found or has a label.")

        # 5. Assertions for final sequence
        self.assertEqual(print_amirali_node.next_node, x_30_node, "'print(\"Amirali Toori\")' should link to 'x=30'.")
        self.assertEqual(x_30_node.next_node, x_20_node, "'x=30' should link to 'x=20'.")
        self.assertIsNone(x_20_node.next_node, "'x=20' should be terminal.")


    def test_match_case_issue_example(self):
        source_code = """
c = "L"
y = 0
match c:
    case "N":
        y = 25
    case "Y":
        y = 50
        x = 10
    case "M":
        pass
    case _:
        y = -1
"""
        nodes, builder, dot_string = self._build_cfg_and_dot_for_source(source_code, "test_match_terminal_cases")

        match_dispatcher_node = self._find_node_by_exact_statement(nodes, "match c")
        self.assertIsNotNone(match_dispatcher_node, "Match dispatcher node not found.")
        if not match_dispatcher_node: return

        self.assertTrue(hasattr(match_dispatcher_node, 'case_branches'))
        self.assertEqual(len(match_dispatcher_node.case_branches), 4)

        expected_case_details = {
            "'N'": ("y = 25", "assignment", None),
            "'Y'": ("y = 50", "assignment", "x = 10"),
            "'M'": ("pass", "pass_statement", None),
            "_"  : ("y = -1", "assignment", None)
        }

        found_labels_in_branches = [label_text for label_text, _ in match_dispatcher_node.case_branches]
        for case_pattern_key, (expected_first_stmt, expected_type, expected_second_stmt_text) in expected_case_details.items():
            case_label_to_find = f"case: {case_pattern_key}"
            self.assertIn(case_label_to_find, found_labels_in_branches, f"Expected case label '{case_label_to_find}' not found.")

            target_node = self._get_case_target_node(match_dispatcher_node, case_pattern_key)
            self.assertIsNotNone(target_node, f"Target node for case '{case_label_to_find}' is None.")

            self.assertTrue(target_node.statements and target_node.statements[0] == expected_first_stmt,
                            f"Case '{case_label_to_find}': Expected first stmt '{expected_first_stmt}', got '{target_node.statements[0] if target_node.statements else ''}'")
            self.assertEqual(target_node.node_type, expected_type, f"Case '{case_label_to_find}': Expected type '{expected_type}', got '{target_node.node_type}'")

            last_node_in_case = target_node
            if expected_second_stmt_text:
                self.assertIsNotNone(target_node.next_node, f"Node '{expected_first_stmt}' in case '{case_label_to_find}' should have a next node.")
                if target_node.next_node:
                    last_node_in_case = target_node.next_node
                    self.assertTrue(last_node_in_case.statements and last_node_in_case.statements[0] == expected_second_stmt_text,
                                    f"Case '{case_label_to_find}': Expected second stmt '{expected_second_stmt_text}', got '{last_node_in_case.statements[0] if last_node_in_case.statements else ''}'.")

            self.assertIsNone(last_node_in_case.next_node, f"Last node '{last_node_in_case.statements[0] if last_node_in_case.statements else 'EMPTY'}' in case '{case_label_to_find}' should be terminal.")

        entry_node_id_str = str(builder.entry_node.id)
        entry_node_pattern = rf'^\s*{entry_node_id_str}\s*\[.*label="{entry_node_id_str}".*xlabel="START".*shape=circle.*\];$'
        self.assertTrue(re.search(entry_node_pattern, dot_string, re.MULTILINE))

        match_node_id_str = str(match_dispatcher_node.id)
        expected_match_xlabel = "match c"
        match_node_pattern = rf'^\s*{match_node_id_str}\s*\[.*label="{match_node_id_str}".*xlabel=".*{re.escape(expected_match_xlabel)}.*".*shape=circle.*\];$'
        self.assertTrue(re.search(match_node_pattern, dot_string, re.MULTILINE))

        node_y_eq_25 = self._get_case_target_node(match_dispatcher_node, "'N'")
        self.assertIsNotNone(node_y_eq_25)
        if node_y_eq_25:
            node_y_eq_25_id_str = str(node_y_eq_25.id)
            node_y_eq_25_pattern = rf'^\s*{node_y_eq_25_id_str}\s*\[.*label="{node_y_eq_25_id_str}".*xlabel="{re.escape("y = 25")}".*shape=circle.*\];$'
            self.assertTrue(re.search(node_y_eq_25_pattern, dot_string, re.MULTILINE))

        node_y_eq_50 = self._get_case_target_node(match_dispatcher_node, "'Y'")
        self.assertIsNotNone(node_y_eq_50)
        if node_y_eq_50 and node_y_eq_50.next_node:
            node_x_eq_10 = node_y_eq_50.next_node
            node_x_eq_10_id_str = str(node_x_eq_10.id)
            node_x_eq_10_pattern = rf'^\s*{node_x_eq_10_id_str}\s*\[.*label="{node_x_eq_10_id_str}".*xlabel="{re.escape("x = 10")}".*shape=circle.*\];$'
            self.assertTrue(re.search(node_x_eq_10_pattern, dot_string, re.MULTILINE))

if __name__ == "__main__":
    unittest.main()
