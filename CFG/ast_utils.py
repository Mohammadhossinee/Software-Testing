import ast

# Ensure this is compatible with Python versions,
# using Union for older versions if needed.
# Given CFG.py uses ast.AST | None, we assume Python 3.10+
# so no special Union import is needed for this specific type hint.

def parse_code_to_ast(code_string: str) -> ast.AST | None:
  """
  Parses a string of Python code and returns its AST representation.

  Args:
    code_string: A string containing Python code.

  Returns:
    An ast.AST object representing the root of the parsed code,
    or None if a SyntaxError occurs during parsing.
  """
  try:
    tree = ast.parse(code_string)
    return tree
  except SyntaxError as e:
    print(f"Syntax error in input code: {e}")
    return None

def negate_condition_ast(condition_node: ast.expr) -> ast.expr:
    """
    Negates an AST expression node representing a condition.
    (Implementation details as per previous versions)
    """
    if isinstance(condition_node, ast.Compare):
        if len(condition_node.ops) == 1 and len(condition_node.comparators) == 1:
            op = condition_node.ops[0]
            negated_op_type = None
            if isinstance(op, ast.Eq): negated_op_type = ast.NotEq
            elif isinstance(op, ast.NotEq): negated_op_type = ast.Eq
            elif isinstance(op, ast.Lt): negated_op_type = ast.GtE
            elif isinstance(op, ast.LtE): negated_op_type = ast.Gt
            elif isinstance(op, ast.Gt): negated_op_type = ast.LtE
            elif isinstance(op, ast.GtE): negated_op_type = ast.Lt
            elif isinstance(op, ast.Is): negated_op_type = ast.IsNot
            elif isinstance(op, ast.IsNot): negated_op_type = ast.Is
            elif isinstance(op, ast.In): negated_op_type = ast.NotIn
            elif isinstance(op, ast.NotIn): negated_op_type = ast.In
            if negated_op_type:
                return ast.Compare(left=condition_node.left, ops=[negated_op_type()], comparators=condition_node.comparators)
    elif isinstance(condition_node, ast.UnaryOp) and isinstance(condition_node.op, ast.Not):
        return condition_node.operand
    elif isinstance(condition_node, ast.BoolOp):
        negated_values = [negate_condition_ast(val) for val in condition_node.values]
        if isinstance(condition_node.op, ast.And):
            return ast.BoolOp(op=ast.Or(), values=negated_values)
        elif isinstance(condition_node.op, ast.Or):
            return ast.BoolOp(op=ast.And(), values=negated_values)
    elif isinstance(condition_node, ast.Constant):
        if condition_node.value is True: return ast.Constant(value=False)
        elif condition_node.value is False: return ast.Constant(value=True)
    return ast.UnaryOp(op=ast.Not(), operand=condition_node)
