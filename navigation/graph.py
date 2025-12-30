# Navigation Graph - Screen transition definitions
# Ported from ig-automation with MCP-friendly interfaces
#
# Defines:
# - ActionType: Types of UI actions (press_back, click_text, etc.)
# - NavigationAction: Single UI action with parameters
# - NavigationEdge: Transition between two screens
# - Graph definitions: LOGIN_FLOW_GRAPH, MAIN_APP_GRAPH

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Dict


class ActionType(str, Enum):
    """Types of navigation actions."""
    PRESS_BACK = "press_back"
    CLICK_ELEMENT = "click_element"  # XPath selector
    CLICK_TAB = "click_tab"  # Tab bar navigation
    CLICK_TEXT = "click_text"  # Find by text
    CLICK_CONTENT_DESC = "click_content_desc"  # Find by accessibility
    SWIPE_DOWN = "swipe_down"
    SWIPE_UP = "swipe_up"
    WAIT = "wait"
    LAUNCH_APP = "launch_app"


@dataclass
class NavigationAction:
    """A single action in a navigation sequence."""
    action_type: ActionType
    target: Optional[str] = None
    wait_after: float = 1.0
    description: str = ""


@dataclass
class NavigationEdge:
    """An edge in the navigation graph - transition between screens."""
    to_screen: str  # Screen ID (e.g., "explore_grid", "home_feed")
    actions: List[NavigationAction]
    cost: float = 1.0
    reliability: float = 0.95
    description: str = ""


# =============================================================================
# Helper functions for building graph
# =============================================================================

def press_back(wait_after: float = 0.8, desc: str = "Press back") -> NavigationAction:
    """Create a press back action."""
    return NavigationAction(
        action_type=ActionType.PRESS_BACK,
        wait_after=wait_after,
        description=desc,
    )


def click_text(text: str, wait_after: float = 1.0, desc: str = "") -> NavigationAction:
    """Create a click by text action."""
    return NavigationAction(
        action_type=ActionType.CLICK_TEXT,
        target=text,
        wait_after=wait_after,
        description=desc or f"Click text: {text}",
    )


def click_content_desc(desc_text: str, wait_after: float = 1.0, desc: str = "") -> NavigationAction:
    """Create a click by content description action."""
    return NavigationAction(
        action_type=ActionType.CLICK_CONTENT_DESC,
        target=desc_text,
        wait_after=wait_after,
        description=desc or f"Click desc: {desc_text}",
    )


def click_tab(tab_name: str, wait_after: float = 1.0) -> NavigationAction:
    """Create a tab click action (uses content description)."""
    return NavigationAction(
        action_type=ActionType.CLICK_TAB,
        target=tab_name,
        wait_after=wait_after,
        description=f"Click tab: {tab_name}",
    )


def click_element(xpath: str, wait_after: float = 1.0, desc: str = "") -> NavigationAction:
    """Create a click by XPath action."""
    return NavigationAction(
        action_type=ActionType.CLICK_ELEMENT,
        target=xpath,
        wait_after=wait_after,
        description=desc or f"Click: {xpath[:50]}",
    )


def wait(seconds: float, desc: str = "") -> NavigationAction:
    """Create a wait action."""
    return NavigationAction(
        action_type=ActionType.WAIT,
        wait_after=seconds,
        description=desc or f"Wait {seconds}s",
    )


def swipe_down(wait_after: float = 0.5) -> NavigationAction:
    """Create a swipe down action."""
    return NavigationAction(
        action_type=ActionType.SWIPE_DOWN,
        wait_after=wait_after,
        description="Swipe down",
    )


def swipe_up(wait_after: float = 0.5) -> NavigationAction:
    """Create a swipe up action."""
    return NavigationAction(
        action_type=ActionType.SWIPE_UP,
        wait_after=wait_after,
        description="Swipe up",
    )


def launch_app(package: str, wait_after: float = 3.0) -> NavigationAction:
    """Create a launch app action."""
    return NavigationAction(
        action_type=ActionType.LAUNCH_APP,
        target=package,
        wait_after=wait_after,
        description=f"Launch {package}",
    )


# =============================================================================
# Screen groupings
# =============================================================================

# Footer navigation screens (accessible from any footer-visible screen)
FOOTER_NAV_SCREENS: Set[str] = {
    "home_feed",
    "explore_grid",
    "reels_tab",
    "profile_page",
    "create_post_select",
}

# Safe states for warmup operations
WARMUP_SAFE_STATES: Set[str] = {
    "explore_grid",
    "search_results_reels",
    "reel_viewing",
    "home_feed",
}

# Safe states after login
LOGIN_SAFE_STATES: Set[str] = {
    "home_feed",
    "explore_grid",
    "profile_page",
}

# Overlay screens (popups, dialogs, modals)
OVERLAY_SCREENS: Set[str] = {
    "comments_view",
    "likes_page",
    "share_sheet",
    "report_dialog",
    "peek_view",
    "story_viewing",
    "login_save_info",
    "login_2fa_code",
    "permission_dialog",
    "app_crash_dialog",
    "app_not_responding",
}


# =============================================================================
# Login Flow Graph
# =============================================================================

LOGIN_FLOW_GRAPH: Dict[str, List[NavigationEdge]] = {
    # Login page transitions
    "login_page": [
        NavigationEdge(
            to_screen="login_password",
            actions=[click_element("//*[@resource-id[contains(., 'login_username')]]")],
            cost=1.0,
            description="Enter username field",
        ),
    ],

    # Save login info prompt
    "login_save_info": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_text("Not now", wait_after=2.0)],
            cost=1.0,
            reliability=0.98,
            description="Skip save login info",
        ),
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_text("Not Now", wait_after=2.0)],
            cost=1.0,
            reliability=0.95,
            description="Skip save login info (alt)",
        ),
    ],

    # Notifications prompt
    "notifications_prompt": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_text("Not Now", wait_after=1.5)],
            cost=1.0,
            reliability=0.98,
            description="Skip notifications prompt",
        ),
    ],
}


# =============================================================================
# Main App Navigation Graph
# =============================================================================

MAIN_APP_GRAPH: Dict[str, List[NavigationEdge]] = {
    # -------------------------------------------------------------------------
    # Home Feed
    # -------------------------------------------------------------------------
    "home_feed": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[click_tab("Search and explore")],
            cost=1.0,
            reliability=0.98,
            description="Go to Explore from Home",
        ),
        NavigationEdge(
            to_screen="reels_tab",
            actions=[click_tab("Reels")],
            cost=1.0,
            reliability=0.98,
            description="Go to Reels tab",
        ),
        NavigationEdge(
            to_screen="profile_page",
            actions=[click_tab("Profile")],
            cost=1.0,
            reliability=0.98,
            description="Go to Profile",
        ),
        NavigationEdge(
            to_screen="dm_inbox",
            actions=[click_content_desc("Direct message button, Double tap for direct messages")],
            cost=1.0,
            reliability=0.95,
            description="Go to DM inbox",
        ),
        NavigationEdge(
            to_screen="create_post_select",
            actions=[click_tab("Create")],
            cost=1.0,
            reliability=0.95,
            description="Open create menu",
        ),
    ],

    # -------------------------------------------------------------------------
    # Explore Grid
    # -------------------------------------------------------------------------
    "explore_grid": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_tab("Home")],
            cost=1.0,
            reliability=0.98,
            description="Go to Home from Explore",
        ),
        NavigationEdge(
            to_screen="search_input",
            actions=[click_element("//*[contains(@resource-id, 'action_bar_search_edit_text')]")],
            cost=1.0,
            reliability=0.98,
            description="Focus search input",
        ),
        NavigationEdge(
            to_screen="reels_tab",
            actions=[click_tab("Reels")],
            cost=1.0,
            reliability=0.98,
            description="Go to Reels tab from Explore",
        ),
        NavigationEdge(
            to_screen="profile_page",
            actions=[click_tab("Profile")],
            cost=1.0,
            reliability=0.98,
            description="Go to Profile from Explore",
        ),
    ],

    # -------------------------------------------------------------------------
    # Search Results
    # -------------------------------------------------------------------------
    "search_results_reels": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back(wait_after=1.0)],
            cost=1.0,
            reliability=0.95,
            description="Back to Explore from search results",
        ),
        NavigationEdge(
            to_screen="reel_viewing",
            actions=[click_element("//*[contains(@resource-id, 'image_button')]", wait_after=1.5)],
            cost=1.0,
            reliability=0.9,
            description="Open first reel from search",
        ),
    ],

    "search_results_accounts": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back()],
            cost=1.0,
            reliability=0.95,
            description="Back to Explore",
        ),
    ],

    "search_results_tags": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back()],
            cost=1.0,
            reliability=0.95,
            description="Back to Explore",
        ),
    ],

    "search_input": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Cancel search",
        ),
    ],

    # -------------------------------------------------------------------------
    # Reel Viewing
    # -------------------------------------------------------------------------
    "reel_viewing": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back(wait_after=1.0)],
            cost=1.0,
            reliability=0.9,
            description="Exit reel to Explore",
        ),
        NavigationEdge(
            to_screen="comments_view",
            actions=[click_content_desc("Comment")],
            cost=1.0,
            reliability=0.95,
            description="Open comments",
        ),
        NavigationEdge(
            to_screen="likes_page",
            actions=[click_element("//*[contains(@resource-id, 'like_count')]")],
            cost=1.0,
            reliability=0.85,
            description="Open likes page",
        ),
        NavigationEdge(
            to_screen="profile_page",
            actions=[click_element("//*[contains(@resource-id, 'clips_author_profile_pic') or contains(@resource-id, 'row_feed_photo_profile_imageview')]")],
            cost=1.0,
            reliability=0.9,
            description="Go to reel author profile",
        ),
    ],

    # -------------------------------------------------------------------------
    # Reels Tab
    # -------------------------------------------------------------------------
    "reels_tab": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_tab("Home")],
            cost=1.0,
            reliability=0.98,
            description="Go to Home from Reels",
        ),
        NavigationEdge(
            to_screen="explore_grid",
            actions=[click_tab("Search and explore")],
            cost=1.0,
            reliability=0.98,
            description="Go to Explore from Reels",
        ),
        NavigationEdge(
            to_screen="comments_view",
            actions=[click_content_desc("Comment")],
            cost=1.0,
            reliability=0.95,
            description="Open comments on reel",
        ),
    ],

    # -------------------------------------------------------------------------
    # Profile Page
    # -------------------------------------------------------------------------
    "profile_page": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_tab("Home")],
            cost=1.0,
            reliability=0.98,
            description="Go to Home from Profile",
        ),
        NavigationEdge(
            to_screen="explore_grid",
            actions=[click_tab("Search and explore")],
            cost=1.0,
            reliability=0.98,
            description="Go to Explore from Profile",
        ),
        NavigationEdge(
            to_screen="profile_followers",
            actions=[click_element("//*[contains(@resource-id, 'row_profile_header_followers_container')]")],
            cost=1.0,
            reliability=0.9,
            description="Open followers list",
        ),
        NavigationEdge(
            to_screen="profile_following",
            actions=[click_element("//*[contains(@resource-id, 'row_profile_header_following_container')]")],
            cost=1.0,
            reliability=0.9,
            description="Open following list",
        ),
    ],

    # -------------------------------------------------------------------------
    # Overlay screens (dismissable)
    # -------------------------------------------------------------------------
    "comments_view": [
        NavigationEdge(
            to_screen="reel_viewing",
            actions=[press_back(wait_after=0.5)],
            cost=1.0,
            reliability=0.98,
            description="Close comments",
        ),
    ],

    "likes_page": [
        NavigationEdge(
            to_screen="reel_viewing",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Close likes page",
        ),
    ],

    "share_sheet": [
        NavigationEdge(
            to_screen="reel_viewing",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Close share sheet",
        ),
    ],

    "peek_view": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Close peek view",
        ),
    ],

    "profile_followers": [
        NavigationEdge(
            to_screen="profile_page",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Close followers list",
        ),
    ],

    "profile_following": [
        NavigationEdge(
            to_screen="profile_page",
            actions=[press_back()],
            cost=1.0,
            reliability=0.98,
            description="Close following list",
        ),
    ],

    # -------------------------------------------------------------------------
    # DM Inbox
    # -------------------------------------------------------------------------
    "dm_inbox": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[press_back()],
            cost=1.0,
            reliability=0.95,
            description="Back to Home from DMs",
        ),
    ],

    # -------------------------------------------------------------------------
    # Story Viewing
    # -------------------------------------------------------------------------
    "story_viewing": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[press_back()],
            cost=1.0,
            reliability=0.9,
            description="Exit story to Home",
        ),
    ],

    # -------------------------------------------------------------------------
    # Create Flow
    # -------------------------------------------------------------------------
    "create_post_select": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[press_back()],
            cost=1.0,
            reliability=0.95,
            description="Cancel create",
        ),
    ],

    "create_post_edit": [
        NavigationEdge(
            to_screen="create_post_select",
            actions=[press_back()],
            cost=1.0,
            reliability=0.9,
            description="Back to selection",
        ),
    ],
}


def get_full_graph() -> Dict[str, List[NavigationEdge]]:
    """Get the complete merged navigation graph."""
    graph: Dict[str, List[NavigationEdge]] = {}

    for screen_id, edges in LOGIN_FLOW_GRAPH.items():
        graph[screen_id] = edges.copy()

    for screen_id, edges in MAIN_APP_GRAPH.items():
        if screen_id in graph:
            graph[screen_id].extend(edges)
        else:
            graph[screen_id] = edges.copy()

    return graph


def get_outgoing_edges(screen_id: str) -> List[NavigationEdge]:
    """Get all outgoing edges from a screen."""
    graph = get_full_graph()
    return graph.get(screen_id, [])


def has_path(from_screen: str, to_screen: str) -> bool:
    """Quick check if a path exists between two screens."""
    if from_screen == to_screen:
        return True

    graph = get_full_graph()
    visited: Set[str] = {from_screen}
    queue = [from_screen]

    while queue:
        current = queue.pop(0)
        for edge in graph.get(current, []):
            if edge.to_screen == to_screen:
                return True
            if edge.to_screen not in visited:
                visited.add(edge.to_screen)
                queue.append(edge.to_screen)

    return False
