from dataclasses import dataclass, field
from dataclasses_json import DataClassJsonMixin

from typing import List
from .nodes import Node


@dataclass
class Journal(DataClassJsonMixin):
    """A collection of nodes representing the solution tree."""

    nodes: List[Node] = field(default_factory=list)

    def __getitem__(self, idx: int) -> Node:
        return self.nodes[idx]

    def __len__(self) -> int:
        return len(self.nodes)

    def append(self, node: Node) -> None:
        """Append a new node to the journal."""
        node.step = len(self.nodes)
        self.nodes.append(node)

    @property
    def draft_nodes(self) -> List[Node]:
        """Return a list of nodes representing initial coding drafts."""
        return [node for node in self.nodes if not node.parent]

    @property
    def buggy_nodes(self) -> List[Node]:
        """Return a list of nodes that are considered buggy by the agent."""
        return [node for node in self.nodes if node.is_buggy]

    @property
    def good_nodes(self) -> List[Node]:
        """Return a list of nodes that are considered good by the agent."""
        return [node for node in self.nodes if not node.is_buggy]

    @property
    def metric_history(self) -> List[float]:
        """Return a list all metric values in the journal."""
        return [node.metric for node in self.nodes]

    def get_best_node(self, only_good: bool = True) -> Node:
        """Return the best solution found so far (node with the highest validation metric)."""
        if only_good:
            need_nodes = self.good_nodes
            if not need_nodes:
                return None
        else:
            need_nodes = self.nodes

        # Now the validation metric is loss(MSE), so the less, the better.
        return min(need_nodes, key=lambda n: n.metric)

    def generate_summary(self, include_code: bool = False):
        """Generate a summary of the good nodes in the journal for the agent."""
        summary = []
        for node in self.good_nodes:
            strbuff = []
            strbuff.append(f"Design: {node.plan}")
            if include_code:
                strbuff.append(f"Code: {node.code}")
            strbuff.append(f"Result: {node.analysis}")
            strbuff.append(f"Validation Metric (Mean Squared Error): {node.metric}")

            summary.append("\n".join(strbuff))

        return "\n----------------------------------\n".join(summary)
