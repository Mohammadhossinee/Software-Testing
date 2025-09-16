import ast
import sys

# Helper to unparse if ast.unparse is not available (e.g. Python < 3.9)
def unparse_ast_node(node):
    if hasattr(ast, "unparse"):
        return ast.unparse(node)
    else:
        # For this exercise, we assume Python 3.9+ or astor is not required.
        # In a real scenario, you'd ensure astor or similar is used for older Pythons.
        raise NotImplementedError("ast.unparse is not available. Please use Python 3.9+ or install 'astor'.")

class ForToWhileTransformer(ast.NodeTransformer):
    """
    Transforms 'for' loops into equivalent 'while' loops.
    Handles 'for x in range(...)' and 'for x in iterable'.
    """
    def __init__(self):
        super().__init__()
        self._iterator_count = 0

    def _generate_iterator_name(self):
        name = f"_iterator_{self._iterator_count}"
        self._iterator_count += 1
        return name

    def visit_For(self, node):
        transformed_body = []
        for stmt in node.body:
            visited_stmt = self.visit(stmt)
            if isinstance(visited_stmt, list):
                transformed_body.extend(visited_stmt)
            elif isinstance(visited_stmt, ast.AST):
                transformed_body.append(visited_stmt)
            else:
                transformed_body.append(stmt)


        transformed_orelse = []
        if node.orelse:
            for stmt in node.orelse:
                visited_stmt = self.visit(stmt)
                if isinstance(visited_stmt, list):
                    transformed_orelse.extend(visited_stmt)
                elif isinstance(visited_stmt, ast.AST):
                    transformed_orelse.append(visited_stmt)
                else:
                     transformed_orelse.append(stmt)

        if isinstance(node.iter, ast.Call) and \
           isinstance(node.iter.func, ast.Name) and \
           node.iter.func.id == 'range' and \
           isinstance(node.target, ast.Name):

            loop_var = node.target.id
            range_args = node.iter.args

            start_node = ast.Constant(value=0)
            step_node = ast.Constant(value=1)

            if len(range_args) == 1:
                end_node = range_args[0]
            elif len(range_args) == 2:
                start_node = range_args[0]
                end_node = range_args[1]
            elif len(range_args) == 3:
                start_node = range_args[0]
                end_node = range_args[1]
                step_node = range_args[2]
            else:
                node.body = transformed_body
                node.orelse = transformed_orelse
                return self.generic_visit(node)

            all_arg_nodes_for_check = [start_node, end_node, step_node]
            for arg_node in all_arg_nodes_for_check:
                if isinstance(arg_node, ast.Name) and arg_node.id == loop_var:
                    node.body = transformed_body
                    node.orelse = transformed_orelse
                    return self.generic_visit(node)

            init_assign = ast.Assign(
                targets=[ast.Name(id=loop_var, ctx=ast.Store())],
                value=start_node
            )

            is_negative_step = False
            if isinstance(step_node, ast.Constant) and isinstance(step_node.value, (int, float)):
                if step_node.value < 0:
                    is_negative_step = True

            if is_negative_step:
                op = ast.Gt()
            else:
                op = ast.Lt()

            condition = ast.Compare(
                left=ast.Name(id=loop_var, ctx=ast.Load()),
                ops=[op],
                comparators=[end_node]
            )

            increment_assign = ast.AugAssign(
                target=ast.Name(id=loop_var, ctx=ast.Store()),
                op=ast.Add(),
                value=step_node
            )

            while_loop = ast.While(
                test=condition,
                body=transformed_body + [increment_assign],
                orelse=transformed_orelse
            )
            return [init_assign, while_loop]

        else:
            iterator_var_name = self._generate_iterator_name()

            iterator_init = ast.Assign(
                targets=[ast.Name(id=iterator_var_name, ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='iter', ctx=ast.Load()), args=[node.iter], keywords=[])
            )

            assign_next = ast.Assign(
                targets=[node.target],
                value=ast.Call(func=ast.Name(id='next', ctx=ast.Load()), args=[ast.Name(id=iterator_var_name, ctx=ast.Load())], keywords=[])
            )

            try_block = ast.Try(
                body=[assign_next],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id='StopIteration', ctx=ast.Load()),
                        name=None,
                        body=[ast.Break()]
                    )
                ],
                orelse=[],
                finalbody=[]
            )

            while_true_loop = ast.While(
                test=ast.Constant(value=True),
                body=[try_block] + transformed_body,
                orelse=transformed_orelse
            )

            return [iterator_init, while_true_loop]

# This is the new helper function
def convert_for_to_while_code(code_string: str) -> str:
    """
    Parses Python code, transforms for-loops to while-loops, and returns the modified code string.
    """
    # ast and ForToWhileTransformer are already imported at the module level.
    # No need to re-import them here if this function is part of the same file.
    try:
        parsed_ast = ast.parse(code_string)
        transformer = ForToWhileTransformer()
        transformed_ast = transformer.visit(parsed_ast)
        ast.fix_missing_locations(transformed_ast)
        # Use the module-level unparse_ast_node for consistency
        return unparse_ast_node(transformed_ast)
    except SyntaxError as e:
        return f"SyntaxError in input code: {e}"
    except NotImplementedError as e: # From unparse_ast_node
        print(f"Error: {e}", file=sys.stderr)
        # Decide how to handle this: re-raise, return original, or error message
        return code_string # Or perhaps f"NotImplementedError: {e}"
    except Exception as e:
        # Log other potential errors during transformation
        return f"An error occurred during conversion: {e}"


# Old convert_for_to_while function, now effectively replaced by convert_for_to_while_code
# For simplicity, I'll comment it out or remove it. Let's remove it to avoid confusion.
# def convert_for_to_while(code_string):
#     try:
#         if sys.version_info < (3, 8):
#             pass
#
#         tree = ast.parse(code_string)
#         transformer = ForToWhileTransformer()
#         new_tree = transformer.visit(tree)
#         ast.fix_missing_locations(new_tree)
#         return unparse_ast_node(new_tree)
#     except SyntaxError as e:
#         return f"SyntaxError in input code: {e}"
#     except NotImplementedError as e:
#         print(f"Error: {e}", file=sys.stderr)
#         return code_string
#     except Exception as e:
#         return f"An error occurred during conversion: {e}"

if __name__ == '__main__':
    # sample_code_for is used by the first major test print
    sample_code_for = """
print("Simple range:")
for i in range(5):
    print(i)

print("\\nRange with start and end:")
for j in range(2, 8):
    if j == 5:
        break
    print(j)
else:
    print("Loop finished without break")

print("\\nRange with start, end, and step:")
for k in range(1, 10, 2):
    print(k)

print("\\nRange with negative step:")
for l_var in range(5, 0, -1):
    print(l_var)
else:
    print("Negative step loop finished")

print("\\nNested loops (range):")
for outer in range(2):
    print(f"Outer: {outer}")
    for inner in range(3):
        print(f"  Inner: {inner}")
        if inner == 1:
            continue
    if outer == 0:
        print("Outer loop 0 specific line")

print("\\nLoop with variable in range:")
n_val = 5
m_val = 2
p_val = 8
q_val = 2
for i_var in range(n_val):
    print(i_var)
for j_var in range(m_val, p_val):
    print(j_var)
for k_var in range(m_val, p_val, q_val):
    print(k_var)

print("\\nLoop over a list:")
my_list = [10, 20, 30]
for x_item in my_list:
    print(x_item)
else:
    print("List iteration finished.")

print("\\nLoop over a string:")
for char_val in "abc":
    if char_val == 'b':
        continue
    print(char_val)

print("\\nNested loops (mixed):")
for i_outer in range(2):
    print(f"Outer i: {i_outer}")
    for char_inner in "xy":
        print(f"  Inner char: {char_inner}")
        if i_outer == 0 and char_inner == 'x':
            break
    else: # else for inner loop
        print("  Inner loop finished normally.")
else: # else for outer loop
    print("Outer loop finished normally.")
"""
    print("Original code (sample_code_for):")
    print(sample_code_for)

    # Use the new helper function
    converted_sample_code = convert_for_to_while_code(sample_code_for)
    print("\nConverted code (sample_code_for):")
    print(converted_sample_code)

    print("\n--- Testing specific cases ---")

    test_cases = {
        "for_else": """
for i in range(3):
    print(i)
else:
    print("Done.")
""",
        "for_break_else": """
for i in range(5):
    if i == 2:
        break
    print(i)
else:
    print("Loop done (no break)")
""",
        "for_continue": """
for i in range(4):
    if i == 1:
        continue
    print(i)
""",
        "for_list_comprehension_iterator": """
for x in [y*y for y in range(3)]: # Iterable is a list comprehension
    print(x)
""",
        "for_tuple_unpack_list": """
data = [(1, 'a'), (2, 'b')]
for num, char_code in data: # Tuple unpacking
    print(f"Num: {num}, Char: {char_code}")
""",
        "for_string_literal_iterator": """
for char_code in "hello":
    print(char_code)
""",
        "empty_for_loop_pass": """
for _ in range(3):
    pass
""",
        "empty_for_loop_iterable_pass": """
my_iterable = [1,2]
for _ in my_iterable:
    pass
""",
        "for_loop_var_in_range_skipped": """
i = 0
for i in range(i, 5): # Should be skipped by range logic, potentially handled by generic if logic changes
    print(i)
"""
    }

    for name, code in test_cases.items():
        print(f"\n--- Test: {name} ---")
        print("Original:")
        print(code)
        # Use the new helper function for each test case
        converted = convert_for_to_while_code(code)
        print("Converted:")
        print(converted)

    print("\nFinished all tests.")
