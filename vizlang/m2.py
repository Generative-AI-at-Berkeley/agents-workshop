"""Module 2: Directed Graph + Conditional Edges — Open in VizLang to visualize."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.m2.workflow import build_graph

graph = build_graph()
