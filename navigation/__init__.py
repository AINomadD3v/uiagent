# Navigation System for UIAgent
# Ported from ig-automation's BFS pathfinding system
#
# This module provides:
# - ScreenDetector: Detects current screen from UI hierarchy
# - ScreenNavigator: Finds and executes paths between screens
# - Navigation graph structures: ActionType, NavigationAction, NavigationEdge

from .detector import ScreenDetector
from .navigator import (
    ScreenNavigator,
    NavigationStatus,
    NavigationStep,
    NavigationPath,
    NavigationResult,
)
from .graph import (
    ActionType,
    NavigationAction,
    NavigationEdge,
    get_full_graph,
    get_outgoing_edges,
    has_path,
    WARMUP_SAFE_STATES,
    LOGIN_SAFE_STATES,
    FOOTER_NAV_SCREENS,
    OVERLAY_SCREENS,
)
from .search import (
    search_for_keyword,
    SearchResult,
    SearchResultType,
)

__all__ = [
    # Detector
    "ScreenDetector",
    # Navigator
    "ScreenNavigator",
    "NavigationStatus",
    "NavigationStep",
    "NavigationPath",
    "NavigationResult",
    # Graph types
    "ActionType",
    "NavigationAction",
    "NavigationEdge",
    # Graph functions
    "get_full_graph",
    "get_outgoing_edges",
    "has_path",
    # Screen sets
    "WARMUP_SAFE_STATES",
    "LOGIN_SAFE_STATES",
    "FOOTER_NAV_SCREENS",
    "OVERLAY_SCREENS",
    # Search
    "search_for_keyword",
    "SearchResult",
    "SearchResultType",
]
