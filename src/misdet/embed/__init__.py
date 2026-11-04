"""Graph embedding backends for policy nodes."""

from .gds_node2vec import embed_policy_nodes_with_gds
from .py_node2vec import embed_policy_nodes, load_node2vec_config

__all__ = [
    "embed_policy_nodes",
    "embed_policy_nodes_with_gds",
    "load_node2vec_config",
]

