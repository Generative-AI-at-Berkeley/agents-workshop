"""Latest module graph — Open in VizLang to visualize."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.registry import build_graph

graph = build_graph()
