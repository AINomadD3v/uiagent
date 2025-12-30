# UIAgent Screen Detection & Navigation System
## Implementation Plan - December 30, 2025

### Goal
Port ig-automation's battle-tested screen signature system to UIAgent MCP server, enabling Claude to:
1. Know "where am I?" in any app
2. Navigate to specific screens automatically
3. Write scripts that reference screen IDs instead of raw xpaths

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        UIAgent MCP Server                        │
├─────────────────────────────────────────────────────────────────┤
│  NEW TOOLS                                                       │
│  ├── detect_screen(serial, app?) → ScreenID + confidence        │
│  ├── navigate_to(serial, target_screen) → success/path taken    │
│  ├── get_screen_signatures(app) → available screens             │
│  └── dump_for_signature(serial) → elements for new signature    │
├─────────────────────────────────────────────────────────────────┤
│  CORE MODULES (ported from ig-automation)                        │
│  ├── screen_detector.py    - Signature matching engine          │
│  ├── screen_navigator.py   - BFS pathfinding + execution        │
│  └── signatures/           - App-specific signature files       │
│      ├── instagram.py      - Instagram signatures (from ig-auto)│
│      └── generic.py        - Android system dialogs             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Infrastructure (Day 1)

### 1.1 Create signatures module structure
```
uiagent/
├── mcp_server.py           # Existing - add new tools
├── signatures/
│   ├── __init__.py         # Signature registry
│   ├── base.py             # ScreenSignature, ScreenID base classes
│   ├── instagram.py        # Copy from ig-automation (40+ screens)
│   └── android_system.py   # Permission dialogs, system popups
└── navigation/
    ├── __init__.py
    ├── detector.py         # Port ScreenDetector class
    ├── navigator.py        # Port pathfinding + execution
    └── graph.py            # Navigation graph definitions
```

### 1.2 Port base classes from ig-automation

**From `screen_signatures.py`:**
- `ScreenSignature` dataclass (required/forbidden/unique/optional/priority)
- `ScreenDetectionResult` dataclass
- `ScreenID` enum (make it app-specific, not hardcoded)

**Key adaptation:** Make ScreenID dynamic per-app instead of single enum:
```python
# Instead of hardcoded ScreenID enum, use string IDs per app
@dataclass
class ScreenSignature:
    app_id: str              # "instagram", "tiktok", etc.
    screen_id: str           # "explore_grid", "reel_viewing"
    required: List[str]
    forbidden: List[str]
    unique: List[str]
    optional: List[str]
    priority: int = 50
    recovery_action: Optional[str] = None
```

### 1.3 Port detector algorithm

**From `screen_detector.py` (505 lines) - KEY LOGIC:**
```python
def detect_screen(self, force_refresh=False) -> ScreenDetectionResult:
    # 1. Get UI hierarchy (cached 500ms)
    hierarchy = self._get_ui_hierarchy(force_refresh)

    # 2. Extract all element identifiers into a Set
    elements = self._extract_elements(hierarchy)
    # Creates: {"resource-id:com.instagram.android:id/search_bar",
    #           "content-desc:Like", "text:Your story", ...}

    # 3. Score ALL signatures (sorted by priority)
    for sig in get_signatures_by_priority():
        score, matched = self._score_signature(sig, elements)

    # 4. Return highest scoring match with confidence
```

**Scoring algorithm:**
- `unique` match → instant 1.0 (but still check forbidden)
- `forbidden` match → instant 0.0 (disqualified)
- `required` → base_score = matches / total_required
- `optional` → up to +0.1 boost

**Clone-safe matching:** Uses `:id/xxx` format - matches just the ID part regardless of package prefix (handles com.instagram.android vs com.instagram.androie clones).

---

## Phase 2: MCP Tool Integration (Day 1-2)

### 2.1 New MCP Tools

```python
@mcp.tool()
async def detect_screen(
    serial: str,
    app_id: str = "instagram"  # Which signature set to use
) -> dict:
    """
    Detect current screen using signature matching.

    Returns:
        screen_id: Detected screen identifier
        confidence: 0.0-1.0 match confidence
        matched_elements: Which elements matched
        candidates: Top 3 alternative matches
        detection_time_ms: Performance metric
    """

@mcp.tool()
async def navigate_to(
    serial: str,
    target_screen: str,        # e.g., "explore_grid"
    app_id: str = "instagram",
    max_attempts: int = 3
) -> dict:
    """
    Navigate from current screen to target screen.

    Uses BFS pathfinding through navigation graph.
    Executes actions (press_back, click, etc.) and verifies each step.
    Re-paths if deviation detected.

    Returns:
        success: bool
        path_taken: List of screens traversed
        actions_executed: List of actions performed
        final_screen: Where we ended up
        error: Error message if failed
    """

@mcp.tool()
async def get_screen_info(
    app_id: str = "instagram"
) -> dict:
    """
    Get available screens and navigation graph for an app.

    Returns:
        screens: List of {screen_id, description, safe_state}
        navigation_edges: Graph of possible transitions
        safe_states: Screens where operations can proceed
    """

@mcp.tool()
async def dump_for_signature(
    serial: str
) -> dict:
    """
    Dump current UI elements for creating new signatures.

    Use when detect_screen returns UNKNOWN.
    Returns structured data for signature creation.
    """
```

### 2.2 Integration with existing tools

**Enhance `get_elements`:** Add optional `detect_screen=True` parameter:
```python
@mcp.tool()
async def get_elements(
    serial: str,
    filter: str = "interactive",
    detect_screen: bool = False  # NEW
) -> dict:
    # ... existing logic ...

    if detect_screen:
        result["current_screen"] = await detect_screen(serial)
```

**Enhance `run_script`:** Inject screen detection helpers:
```python
# Available in run_script context:
# current_screen = detect_screen()  # Returns ScreenID
# navigate_to("explore_grid")       # Auto-navigates
# is_on_screen("reel_viewing")      # Quick check
```

---

## Phase 3: Port Instagram Signatures (Day 2)

### 3.1 Copy signatures from ig-automation

**Direct copy with minor adaptations:**
- `shared/config/screen_signatures.py` → `uiagent/signatures/instagram.py`
- `shared/config/navigation_graph.py` → `uiagent/navigation/instagram_graph.py`

**Screens to port (40+):**
```
OVERLAYS (priority 90-100):
- peek_view, comments_view, likes_page

CRITICAL (priority 80-89):
- human_verification, mobile_verification, account_suspended

LOGIN FLOW (priority 80-85):
- join_instagram, login_meta_tos, login_page
- login_approval_required, login_2fa_*, login_save_info

ONBOARDING (priority 83-84):
- onboarding_facebook_suggestions, onboarding_contacts_sync
- onboarding_profile_picture, onboarding_follow_people
- onboarding_add_email, onboarding_preferences

NAVIGATION (priority 40-60):
- explore_grid, search_results_reels, search_results_accounts
- profile_page, home_feed, notifications, dm_inbox, dm_thread

CONTENT VIEWING (priority 20-35):
- reel_viewing, story_viewing, post_viewing

CONTENT CREATION (priority 45-55):
- create_post_gallery, create_post_editor, create_post_share
- create_reel_camera, create_reel_editor, create_reel_music
- create_reel_text, create_reel_share
```

### 3.2 Add Android system signatures

**New file: `uiagent/signatures/android_system.py`**
```python
ANDROID_SYSTEM_SIGNATURES = [
    ScreenSignature(
        app_id="android_system",
        screen_id="permission_dialog",
        required=["text:Allow", "text:Deny"],
        unique=[":id/permission_message"],
        priority=100,  # Always check first
    ),
    ScreenSignature(
        app_id="android_system",
        screen_id="app_crash_dialog",
        required=["contains:has stopped", "text:Close app"],
        priority=100,
    ),
    # ... device logs access, battery optimization, etc.
]
```

---

## Phase 4: Navigation Engine (Day 2-3)

### 4.1 Port BFS pathfinder

**From `screen_navigator.py`:**
```python
def find_path(from_screen: str, to_screen: str) -> Optional[NavigationPath]:
    """
    BFS pathfinding through navigation graph.

    Returns path with:
    - List of screens to traverse
    - Actions for each transition
    - Total cost estimate
    - Combined reliability score
    """
    queue = [(from_screen, [], 0.0, 1.0)]  # (screen, path, cost, reliability)
    visited = set()

    while queue:
        current, path, cost, reliability = queue.pop(0)

        if current == to_screen:
            return NavigationPath(path, cost, reliability)

        for edge in get_outgoing_edges(current):
            if edge.to_screen not in visited:
                new_path = path + [edge]
                new_cost = cost + edge.cost
                new_reliability = reliability * edge.reliability
                queue.append((edge.to_screen, new_path, new_cost, new_reliability))
                visited.add(edge.to_screen)

    return None  # No path found
```

### 4.2 Port navigation executor

**Key features to port:**
1. Execute actions (press_back, click_text, click_content_desc, etc.)
2. Verify destination after each step
3. Re-path on deviation (if actual != expected, find new path from actual)
4. Retry mechanism (max_attempts)
5. Stop mechanism (graceful interrupt)

---

## Phase 5: Claude Integration (Day 3)

### 5.1 Skill documentation

**Update `android-automation` skill:**
```markdown
## Screen Detection

Before writing scripts, detect current screen:
detect_screen(serial) → Returns screen_id + confidence

## Navigation

Navigate to known screens:
navigate_to(serial, "explore_grid")  # Auto-finds path and executes

## Available Screens (Instagram)

| Screen ID | Description | Safe State |
|-----------|-------------|------------|
| explore_grid | Search landing page | ✅ |
| search_results_reels | Search results with reels | ✅ |
| reel_viewing | Full-screen reel player | ✅ |
| home_feed | Main feed | ❌ (navigate away) |
| ... | ... | ... |
```

### 5.2 Script patterns with screen awareness

```python
# Claude can now write:

# 1. Check where we are
screen = detect_screen()
if screen.screen_id != "explore_grid":
    navigate_to("explore_grid")

# 2. Perform action
d.xpath("//*[@text='Search']").click()
d.send_keys("travel")

# 3. Verify we're in right place
assert detect_screen().screen_id == "search_results_reels"

# 4. Watch reels
d.xpath("//reel_thumbnail").click()
wait_for_screen("reel_viewing", timeout=5)
```

---

## File Changes Summary

### New Files
```
uiagent/
├── signatures/
│   ├── __init__.py           # Signature registry + loader
│   ├── base.py               # ScreenSignature, NavigationEdge classes
│   ├── instagram.py          # Port from ig-automation (~1300 lines)
│   └── android_system.py     # System dialogs (~100 lines)
├── navigation/
│   ├── __init__.py
│   ├── detector.py           # Port ScreenDetector (~400 lines)
│   ├── navigator.py          # Port pathfinder + executor (~500 lines)
│   └── instagram_graph.py    # Port navigation graph (~900 lines)
```

### Modified Files
```
uiagent/
├── mcp_server.py             # Add 4 new tools
```

### Dependencies
- No new dependencies (uses existing uiautomator2 + xml.etree)

---

## Testing Plan

### Unit Tests
1. Signature matching (required/forbidden/unique/optional scoring)
2. Clone-safe ID matching (`:id/xxx` works for any package)
3. BFS pathfinding (finds optimal path)
4. Action execution (press_back, click_text, etc.)

### Integration Tests
1. Detect known Instagram screens (40+ screens)
2. Navigate between screens (home → explore → search → reel)
3. Handle overlays (comments, likes, peek_view)
4. Recover from unknown screens

### Live Tests
1. Full warmup flow: launch → navigate → search → watch reels
2. Login flow handling
3. Popup dismissal during navigation

---

## Timeline

| Day | Phase | Deliverable |
|-----|-------|-------------|
| 1 | Phase 1-2 | Core infrastructure + MCP tools |
| 2 | Phase 3-4 | Instagram signatures + navigation engine |
| 3 | Phase 5 | Claude integration + testing |

---

## Success Criteria

1. `detect_screen()` returns correct screen 95%+ of the time
2. `navigate_to()` reaches target screen 90%+ of the time
3. Claude can write scripts using screen IDs instead of raw xpaths
4. Detection time <500ms average
5. Works with Instagram clones (different package names)

---

## Future Enhancements

1. **TikTok signatures** - Similar screen structure
2. **Auto-signature learning** - Detect new screens and suggest signatures
3. **Visual verification** - Screenshot + ML for ambiguous cases
4. **Navigation recording** - Record manual navigation to build graphs
