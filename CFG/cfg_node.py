from typing import List, Optional, Tuple

class CFGNode:
    """
    Represents a node in the Control Flow Graph.
    This version uses direct links (next_node, branch_node, else_node)
    for simpler CFG structures.
    """
    def __init__(self, id: int, statements: Optional[List[str]] = None, node_type: str = "statement_block"):
        self.id: int = id
        self.statements: List[str] = statements if statements is not None else []
        self.node_type: str = node_type

        # Core CFG links
        self.next_node: Optional[CFGNode] = None      # For sequential flow
        self.branch_node: Optional[CFGNode] = None   # For 'true' branch of conditions (if, while, for)
                                                      # Or main execution path for try blocks
        self.else_node: Optional[CFGNode] = None     # For 'false' branch of conditions (if, while, for 'else' part of loop exit)
                                                      # Or 'else' block for try-except-else
                                                      # Or start of first exception handler for try-except

        # Specific for Match-Case statements
        # Stores tuples of (case_label_str, target_CFGNode_for_that_case_body)
        self.case_branches: List[Tuple[str, CFGNode]] = []

        # Note: Predecessors are not explicitly stored in this node version to keep it simple.
        # This affects some types of graph analysis but simplifies construction.

    def __repr__(self) -> str:
        next_id = self.next_node.id if self.next_node else None
        branch_id = self.branch_node.id if self.branch_node else None
        else_id = self.else_node.id if self.else_node else None
        return (f"CFGNode(id={self.id}, type='{self.node_type}', stmts='{' '.join(self.statements):.20s}...', "
                f"next={next_id}, branch={branch_id}, else={else_id}, cases={len(self.case_branches)})")

# It's possible that specific node types (Entry, Exit, IfCondition, LoopCondition, etc.)
# could inherit from CFGNode if they need to store more specialized information or behavior,
# but the provided CFGBuilder seems to use CFGNode directly and differentiate behavior
# based on 'node_type' string and by setting appropriate links.

# For consistency with the new CFGBuilder's direct use of CFGNode for various roles:
EntryNode = CFGNode
ExitNode = CFGNode
CallNode = CFGNode # Generic calls, or specific types like "function_call"
MatchNode = CFGNode # Will use case_branches
CaseNode = CFGNode # Represents the start of a case block statements
# ... and so on. The CFGBuilder assigns a 'node_type' string.

# If more specific classes were needed, they would look like:
# class EntryNode(CFGNode):
#     def __init__(self, id: int, name: str = "Entry"):
#         super().__init__(id, statements=[name], node_type="entry")

# class CallNode(CFGNode):
#     def __init__(self, id: int, call_name: str, node_type:str = "function_call"):
#         super().__init__(id, statements=[call_name], node_type=node_type)

# However, the provided CFGBuilder creates CFGNode instances directly,
# e.g. self.new_node(statements=[...], node_type="entry"),
# so distinct classes aren't strictly necessary for THIS version of CFGBuilder to function
# as long as the 'node_type' string is used for differentiation (e.g. in to_dot).
# The provided CFGBuilder's to_dot method does not use specific types for shapes,
# relying on node.node_type strings if show_node_type is True, but primarily on node.statements.
# The more recent to_dot used isinstance checks, which would require these aliases or actual classes.
# For now, this simple aliasing matches the builder's direct CFGNode usage.
# A more robust system would have these as distinct classes inheriting from a base CFGNode.
AbstractCFGNode = CFGNode # Alias for compatibility if any lingering refs
AbstractBranchNode = CFGNode # Alias
BreakNode = CFGNode
ContinueNode = CFGNode
ElseNode = CFGNode # This is a conceptual role, not a node type usually.
EndIfNode = CFGNode
EndLoopNode = CFGNode
LoopConditionNode = CFGNode
LoopNode = CFGNode
RaiseNode = CFGNode
ReturnNode = CFGNode
StartIfNode = CFGNode
StartLoopNode = CFGNode
TryNode = CFGNode
# These aliases ensure that if the CFGBuilder (or other code) still has type hints
# for these older class names, it won't immediately break on import, assuming the
# CFGNode structure is sufficient for how they are used by this specific builder.
# This is a transitional measure. Ideally, the builder would be updated to
# only use CFGNode or truly distinct subclasses of it if needed.
