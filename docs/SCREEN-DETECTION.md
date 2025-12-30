# Screen Detection and Navigation System

## Table of Contents

1. [Overview](#overview)
2. [How Detection Works](#how-detection-works)
3. [Available Screens](#available-screens)
4. [Creating New Signatures](#creating-new-signatures)
5. [Navigation System](#navigation-system)
6. [API Reference](#api-reference)
7. [Performance](#performance)

---

## Overview

### What is Screen Detection?

The Screen Detection system is UIAgent's answer to a fundamental challenge in UI automation: **How does the automation system know where it is in the app?**

Unlike traditional automation that relies on fragile "find element by ID" approaches that break with every app update, UIAgent uses **signature-based fingerprinting** to identify screens. Each screen has a unique "fingerprint" of UI elements that should (or shouldn't) be present. The detector analyzes the current UI once, extracts all identifiers, and matches them against 40+ known screen signatures in parallel.

### Why This Matters

**Traditional Approach:**
```python
# Fragile - breaks when IDs change between app versions
if element_exists("com.instagram.android:id/explore_button"):
    return "explore"
```

**Signature-Based Approach:**
```python
# Robust - matches patterns, not exact IDs
# Looks for constellation of elements that define a screen
if has_elements([:id/action_bar_search_edit_text, :id/explore_action_bar])
   and not_has([:id/profile_header, text:Your story]):
    return "explore_grid" with 95% confidence
```

### Key Benefits

1. **Clone-Safe**: Works across Instagram clones (GB Instagram, Instagram Lite) by matching partial resource IDs
2. **Fast**: Single UI dump → parallel scoring → result in <500ms
3. **Accurate**: 95%+ detection accuracy with confidence scores
4. **Extensible**: Easy to add new screen signatures as the app evolves
5. **Self-Documenting**: Signatures serve as living documentation of app structure

### Architecture Components

The system consists of three main components:

1. **ScreenDetector** (`navigation/detector.py`) - Performs detection
2. **ScreenSignature** (`signatures/base.py`) - Defines screen fingerprints
3. **ScreenNavigator** (`navigation/navigator.py`) - Uses detection for pathfinding

---

## How Detection Works

### High-Level Algorithm

```
1. Get UI Hierarchy (500ms cache)
   ├─ Device dumps XML hierarchy
   └─ Parse into element tree

2. Extract Elements (normalization)
   ├─ resource-id:com.instagram.android:id/explore_action_bar
   ├─ id:explore_action_bar (clone-safe!)
   ├─ content-desc:Search and explore
   ├─ text:Your story
   ├─ text-lower:your story
   └─ class-short:FrameLayout

3. Score All Signatures (parallel)
   ├─ Check UNIQUE (instant 1.0 match)
   ├─ Check FORBIDDEN (instant disqualification)
   ├─ Score REQUIRED (base confidence)
   └─ Boost with OPTIONAL

4. Return Best Match
   └─ ScreenDetectionResult with confidence + candidates
```

### Element Extraction

The detector extracts UI elements into normalized identifiers for fast set-based matching:

```python
# From UI XML:
<node resource-id="com.instagram.android:id/explore_action_bar"
      content-desc="Search and explore"
      text=""
      class="android.widget.FrameLayout"
      clickable="true"/>

# Extracted identifiers:
resource-id:com.instagram.android:id/explore_action_bar  # Full ID
id:explore_action_bar                                     # Clone-safe
content-desc:Search and explore                           # Accessibility
content-desc-lower:search and explore                     # Case-insensitive
class:android.widget.FrameLayout                          # Full class
class-short:FrameLayout                                   # Short class
clickable:Search and explore                              # Clickable desc
```

**Why Normalization?**
- **Clone-safe matching**: Apps like GB Instagram use different package names but same `:id/` suffixes
- **Case-insensitive**: Text might vary in capitalization
- **Performance**: Set lookups are O(1)

### Scoring Algorithm

Signatures are scored in priority order to determine which screen is showing:

#### 1. UNIQUE Elements (Instant Win)

If **any** unique selector matches, confidence = 1.0 immediately:

```python
ScreenSignature(
    screen_id="explore_grid",
    unique=[":id/explore_action_bar"],  # Only on explore screen
    # ...
)
# If :id/explore_action_bar is present → confidence = 1.0
```

#### 2. FORBIDDEN Elements (Instant Disqualification)

If **any** forbidden selector matches, confidence = 0.0:

```python
ScreenSignature(
    screen_id="explore_grid",
    forbidden=[
        ":id/profile_header_container",  # Would indicate profile page
        "text:Your story",               # Would indicate home feed
    ],
    # ...
)
```

#### 3. REQUIRED Elements (Base Score)

Score = (matched required) / (total required)

```python
ScreenSignature(
    screen_id="reel_viewing",
    required=[
        ":id/clips_viewer_view_pager",  # Reel container
        ":id/like_button",              # Like button
        ":id/comment_button",           # Comment button
    ],
    # ...
)
# If 2 of 3 match → base_score = 0.67
```

#### 4. OPTIONAL Elements (Confidence Boost)

Optional elements add up to 0.1 confidence boost:

```python
optional_boost = 0.1 * (matched_optional / total_optional)
final_score = min(1.0, base_score + optional_boost)
```

### Selector Format Reference

UIAgent supports multiple selector formats for maximum flexibility:

| Format | Example | Description | Use Case |
|--------|---------|-------------|----------|
| `:id/xxx` | `:id/explore_action_bar` | Clone-safe resource ID | **Primary** - most stable |
| `id:xxx` | `id:search_bar` | Short ID format | Alternative syntax |
| `text:exact` | `text:Your story` | Exact text match | Visible labels |
| `text-lower:xxx` | `text-lower:your story` | Case-insensitive text | Flexible matching |
| `content-desc:label` | `content-desc:Like` | Accessibility label | Buttons, actions |
| `ClassName` | `VideoView` | Short class name | Element types |
| `contains:substring` | `contains:Reel by` | Partial text match | Dynamic content |
| `A OR B` | `text:Like OR text:Unlike` | Either matches | State variants |

**Selector Matching Logic:**

```python
# Clone-safe ID matching
":id/explore_action_bar" matches:
  - "resource-id:com.instagram.android:id/explore_action_bar"
  - "resource-id:com.gb.instagram:id/explore_action_bar"
  - "id:explore_action_bar"

# OR conditions
"text:Like OR text:Unlike" matches if either text is present

# Contains
"contains:Reel by" matches:
  - "content-desc:Reel by @username"
  - "text:Reel by someone"
```

### UI Hierarchy Cache

Detection uses a 500ms cache to avoid redundant UI dumps:

```python
# First call: dump UI (100-200ms)
result1 = detector.detect_screen()

# Second call within 500ms: use cache (instant)
result2 = detector.detect_screen()

# Force refresh (ignore cache)
result3 = detector.detect_screen(force_refresh=True)
```

**When to Force Refresh:**
- After performing UI actions (click, swipe)
- Before critical navigation decisions
- When detection result seems stale

---

## Available Screens

### Instagram App (40+ Screens)

#### Overlays (Priority 90-100)

Checked first since they appear on top of other screens.

| Screen ID | Description | Key Elements |
|-----------|-------------|--------------|
| `peek_view` | Long-press preview overlay | `:id/peek_container` |
| `comments_view` | Comments bottom sheet | `:id/layout_comment_thread_edittext` |
| `likes_page` | Views & likes overlay | `text:Likes` |

#### Login Flow (Priority 80-85)

| Screen ID | Description | Recovery Action |
|-----------|-------------|-----------------|
| `join_instagram` | Welcome screen | Click "I already have an account" |
| `login_meta_tos` | Meta Terms of Service | Click "Continue" |
| `login_page` | Username/password form | - |
| `login_approval_required` | Waiting for approval | Click "Try another way" |
| `login_2fa_method_select` | Choose 2FA method | Back |
| `login_2fa_code_entry` | Enter 6-digit code | Back |
| `login_save_info` | Save login info? | Click "Not now" |

#### Onboarding (Priority 83-84)

Safe states after login - all skippable.

| Screen ID | Description | Recovery |
|-----------|-------------|----------|
| `onboarding_facebook_suggestions` | Connect Facebook | Click "Skip" |
| `onboarding_contacts_sync` | Sync contacts | Click "Next" |
| `onboarding_profile_picture` | Add profile picture | Click "Skip" |
| `onboarding_follow_people` | Follow 5+ people | Click "Skip" |
| `onboarding_add_email` | Add email | Click "Skip" |
| `onboarding_preferences` | Content preferences | Click "Skip" |

#### Main Navigation (Priority 25-55)

Core screens for app navigation.

| Screen ID | Description | Safe State? |
|-----------|-------------|-------------|
| `home_feed` | Main feed with "Your story" | No (avoid for warmup) |
| `explore_grid` | Search/Explore landing page | **Yes** |
| `search_results_reels` | Search results (Reels tab) | **Yes** (ideal warmup) |
| `search_results_accounts` | Search results (Accounts tab) | No |
| `profile_page` | User profile (own or others) | No |
| `reels_tab` | Reels tab (footer nav) | No |
| `dm_inbox` | Direct messages inbox | No |
| `dm_thread` | Individual DM conversation | No |
| `notifications` | Activity/notifications screen | No |

#### Content Viewing (Priority 20-35)

| Screen ID | Description | Safe State? |
|-----------|-------------|-------------|
| `reel_viewing` | Full-screen reel player | **Yes** (main warmup) |
| `story_viewing` | Full-screen story viewer | No |

#### Content Creation (Priority 45-56)

| Screen ID | Description |
|-----------|-------------|
| `create_post_gallery` | Gallery picker for new post |
| `create_post_editor` | Post editing (filters, crop) |
| `create_post_share` | Final share screen for posts |
| `create_story_camera` | Camera for story creation |
| `create_reel_camera` | Camera/gallery for reel creation |
| `create_reel_editor` | Reel editing (audio, stickers) |
| `create_reel_music` | Music selection bottom sheet |
| `create_reel_text` | Text overlay composer |
| `create_reel_share` | Final share screen for reels |

#### Critical Screens (Priority 95)

| Screen ID | Description | Recovery |
|-----------|-------------|----------|
| `account_suspended` | Account suspended/disabled | Handle account suspended |

### Android System (10+ Screens)

Priority 100 - highest priority to catch system overlays.

| Screen ID | Description | Recovery |
|-----------|-------------|----------|
| `permission_dialog` | Android permission request | Click "Deny" |
| `permission_dialog_v2` | Android 13+ permissions | Click "Deny" |
| `app_crash_dialog` | App has stopped | Click "Close app" |
| `app_not_responding` | ANR dialog | Click "Wait" |
| `battery_optimization` | Battery optimization dialog | Click "Deny" |
| `system_alert_window` | Display over other apps | Click "Deny" |
| `accessibility_service` | Accessibility confirmation | Click "Allow" |
| `no_internet_dialog` | No internet connection | Click "OK" |
| `wifi_connection_prompt` | WiFi connection prompt | Click "Cancel" |
| `low_storage_warning` | Low storage space | Click "OK" |
| `app_update_available` | App update available | Click "Not now" |
| `google_play_services_update` | Play Services update | Click "Cancel" |

### Safe States

**Warmup Safe States:**
Screens ideal for warmup operations (viewing content without triggering engagement metrics):
- `explore_grid`
- `search_results_reels`
- `reel_viewing`
- `home_feed`

**Login Safe States:**
Screens that indicate successful login:
- `home_feed`
- `explore_grid`
- `profile_page`
- All `onboarding_*` screens

---

## Creating New Signatures

When `detect_screen()` returns `unknown`, you need to create a new signature. Here's the systematic process:

### Step 1: Dump Current UI

Use `dump_for_signature()` to extract all identifiable elements:

```python
dump = detector.dump_for_signature()

# Returns:
{
    "timestamp": "2025-12-30T10:30:00",
    "resource_ids": [
        "action_bar_search_edit_text",
        "explore_action_bar",
        "search_row_container",
        # ...
    ],
    "content_descs": [
        "Search and explore",
        "Reel by @username",
        # ...
    ],
    "texts": [
        "Explore",
        "Your story",
        # ...
    ],
    "classes": [
        "FrameLayout",
        "ImageView",
        # ...
    ],
    "clickables": [
        "Search and explore",
        # ...
    ],
    "total_elements": 142,
    "hint": "Use resource_ids for stable signatures (clone-safe with :id/xxx format)"
}
```

### Step 2: Identify Unique Elements

Look for elements that **only appear on this screen**:

```python
# Good unique identifiers:
unique = [
    ":id/explore_action_bar",         # Only on explore screen
    ":id/clips_viewer_view_pager",    # Only when viewing reels
    "text:Save your login info?",     # Only after login
]

# Bad unique identifiers:
unique = [
    ":id/action_bar",                 # Too generic, appears everywhere
    "text:Instagram",                 # Could be on multiple screens
]
```

### Step 3: Define Required Elements

Elements that **must all be present** for this screen:

```python
required = [
    ":id/action_bar_search_edit_text",  # Search bar
    ":id/search_row_container",         # Search container
]
# Screen matches if ALL required elements are present
```

### Step 4: Define Forbidden Elements

Elements that **must not be present** (distinguishes from similar screens):

```python
# On explore_grid, we should NOT see:
forbidden = [
    ":id/profile_header_container",  # Would indicate profile page
    "text:Your story",               # Would indicate home feed
    ":id/clips_viewer_view_pager",   # Would indicate reel viewing
]
```

### Step 5: Add Optional Boosters

Elements that increase confidence if present (but aren't required):

```python
optional = [
    ":id/explore_action_bar_container",
    "content-desc:Search and explore",
    "contains:Reel by",  # Search results might show reels
]
```

### Step 6: Create Signature

```python
from signatures.base import ScreenSignature

new_signature = ScreenSignature(
    app_id="instagram",
    screen_id="my_new_screen",
    description="Clear description of what this screen shows",

    # Priority (higher = checked first)
    # 100: System overlays
    # 90-95: Critical app overlays
    # 80-85: Login/onboarding
    # 40-60: Main navigation
    # 20-35: Content viewing
    priority=50,

    # Element selectors
    unique=[":id/unique_element"],           # ANY = instant match
    required=[":id/must_have_1", ":id/must_have_2"],  # ALL required
    forbidden=[":id/cant_have"],             # NONE can be present
    optional=[":id/nice_to_have"],           # Boost confidence

    # Recovery
    recovery_action="back",  # or "click_skip", "click_not_now", etc.
    is_safe_state=True,      # Safe for operations?
)
```

### Step 7: Test Signature

Add to `signatures/instagram.py`:

```python
INSTAGRAM_SIGNATURES.append(new_signature)
```

Test detection:

```python
result = detector.detect_screen(force_refresh=True)
print(f"Detected: {result.screen_id}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Matched: {result.matched_elements}")
```

### Signature Quality Checklist

**Good Signature:**
- ✅ Uses `:id/` format for resource IDs (clone-safe)
- ✅ Has at least one unique element OR 3+ required elements
- ✅ Forbidden elements distinguish from similar screens
- ✅ Description explains when/why this screen appears
- ✅ Priority reflects overlay hierarchy
- ✅ Optional elements boost confidence without causing false positives

**Bad Signature:**
- ❌ Uses full package resource IDs (`com.instagram.android:id/foo`)
- ❌ Only one required element with no unique
- ❌ No forbidden elements (too permissive)
- ❌ Generic description ("some screen")
- ❌ Wrong priority (content screen at priority 100)
- ❌ Too many optional elements that appear on other screens

### Example: Complete Signature

```python
ScreenSignature(
    app_id="instagram",
    screen_id="explore_grid",
    description="Search/Explore landing page with grid of suggested content",
    priority=40,

    # Unique identifier - instant 100% match
    unique=[":id/explore_action_bar"],

    # Must have search functionality
    required=[
        ":id/action_bar_search_edit_text",  # Search bar
    ],

    # Can't be other screens
    forbidden=[
        ":id/profile_header_container",      # Not profile
        "text:Your story",                   # Not home feed
        ":id/action_bar_button_back",        # Not search results
        ":id/scrollable_tab_layout",         # Not search results
        ":id/layout_comment_thread_edittext", # Not comments
        ":id/peek_container",                 # Not peek view
    ],

    # Boost confidence
    optional=[
        ":id/explore_action_bar_container",
        "content-desc:Search and explore",
        "contains:Reel by",  # Grid might show reels
    ],

    recovery_action=None,  # This is a safe state, no recovery needed
    is_safe_state=True,
)
```

---

## Navigation System

The navigation system uses **BFS pathfinding** on a directed graph of screen transitions to find and execute the shortest path between screens.

### Navigation Graph

Defined in `navigation/graph.py`, the graph consists of:

1. **Nodes**: Screen IDs (e.g., `explore_grid`, `home_feed`)
2. **Edges**: Transitions between screens
3. **Actions**: UI actions to execute (click, back, swipe)

```python
MAIN_APP_GRAPH = {
    "home_feed": [
        NavigationEdge(
            to_screen="explore_grid",
            actions=[click_tab("Search and explore")],
            cost=1.0,
            reliability=0.98,
            description="Go to Explore from Home",
        ),
        # ... more edges
    ],
    "explore_grid": [
        NavigationEdge(
            to_screen="home_feed",
            actions=[click_tab("Home")],
            cost=1.0,
            reliability=0.98,
            description="Go to Home from Explore",
        ),
        # ... more edges
    ],
}
```

### Action Types

| Action Type | Description | Parameters |
|-------------|-------------|------------|
| `PRESS_BACK` | Press back button | - |
| `CLICK_TAB` | Click bottom tab | `target`: content-desc |
| `CLICK_TEXT` | Click by text | `target`: text to find |
| `CLICK_CONTENT_DESC` | Click by accessibility label | `target`: content-desc |
| `CLICK_ELEMENT` | Click by XPath | `target`: XPath selector |
| `SWIPE_DOWN` | Swipe down | - |
| `SWIPE_UP` | Swipe up | - |
| `WAIT` | Wait for duration | `wait_after`: seconds |
| `LAUNCH_APP` | Launch app | `target`: package name |

### BFS Pathfinding

The navigator uses Breadth-First Search to find the shortest path:

```
Algorithm:
1. Detect current screen
2. If current == target → return ALREADY_THERE
3. BFS from current screen:
   ├─ Explore all edges (transitions)
   ├─ Track visited screens
   └─ Return first path that reaches target
4. Execute path step-by-step
5. Verify each step (optional)
6. Re-pathfind if deviation detected
```

**Why BFS?**
- Guarantees shortest path (minimum steps)
- Explores level-by-level (nearby screens first)
- Efficient for sparse graphs (most screens have 2-5 edges)

### Navigation Example

```python
from navigation.navigator import ScreenNavigator
from navigation.detector import ScreenDetector

detector = ScreenDetector(device)
navigator = ScreenNavigator(device, detector, app_id="instagram")

# Navigate from current screen to explore_grid
result = navigator.navigate_to(
    target="explore_grid",
    max_attempts=3,
    verify_each_step=True,
)

if result.success:
    print(f"Navigation succeeded in {result.total_time_seconds:.1f}s")
    print(f"Path: {result.path_summary}")
else:
    print(f"Navigation failed: {result.error_message}")
```

### Verification and Recovery

The navigator verifies each step and can recover from deviations:

```python
# Step 1: home_feed → explore_grid
#   Action: click_tab("Search and explore")
#   Verify: detect_screen() == "explore_grid"
#   ✅ Success

# Step 2: explore_grid → search_results_reels
#   Action: click search bar, type keyword
#   Verify: detect_screen() == "search_results_reels"
#   ❌ Actually at "search_results_accounts"
#   Recovery: Re-pathfind from "search_results_accounts"
```

**Verification Modes:**
- `verify_each_step=True`: Detect after every action (safer, slower)
- `verify_each_step=False`: Only detect at end (faster, riskier)

### Safe State Recovery

When automation gets stuck or encounters an unknown screen, use safe state recovery:

```python
# Recover to safe state for warmup
result = navigator.recover_to_safe_state(context="warmup")
# Targets: explore_grid, search_results_reels, reel_viewing, home_feed

# Recover after login
result = navigator.recover_to_safe_state(context="login")
# Targets: home_feed, explore_grid, profile_page
```

**Recovery Algorithm:**
1. Check if already in a safe state → return ALREADY_THERE
2. Try preferred target (e.g., `explore_grid` for warmup)
3. If preferred fails, find shortest path to **any** safe state
4. Execute navigation with retries

### Search Functionality

The `search_for_keyword()` function handles dynamic search flow:

```python
from navigation.search import search_for_keyword

result = search_for_keyword(
    d=device,
    detector=detector,
    navigator=navigator,
    keyword="dance",
    ensure_reels=True,  # Auto-switch to Reels tab if showing accounts
    timeout=15.0,
)

if result.success:
    print(f"Search completed: {result.result_type}")
    print(f"Final screen: {result.final_screen}")
    print(f"Steps: {result.steps_taken}")
```

**Search Flow:**
1. Navigate to `explore_grid` (if not already there)
2. Click search bar
3. Type keyword character-by-character (human-like delays: 30-100ms)
4. Press Enter
5. Wait for results (1-1.5s)
6. Detect result type (Reels vs Accounts)
7. Switch to Reels tab if needed

**Human-Like Delays:**
```python
# Typing delays (per character)
30-100ms between characters

# Action delays
200-400ms after clicking search bar
100-200ms after clearing text
1000-1500ms after pressing Enter
800-1200ms after clicking tab
```

### Navigation Statistics

Track navigation performance:

```python
stats = navigator.get_stats()
# {
#     "total_navigations": 42,
#     "successful_navigations": 40,
#     "success_rate": 0.952,
#     "total_steps_executed": 87,
#     "average_navigation_time_seconds": 2.3,
#     "graph_screens": 35
# }
```

---

## API Reference

### ScreenDetector

```python
from navigation.detector import ScreenDetector

detector = ScreenDetector(device)
```

#### detect_screen()

Detect the current screen using signature matching.

```python
result = detector.detect_screen(
    app_id="instagram",        # Which app's signatures to use
    force_refresh=False,       # Bypass 500ms cache
    include_system=True,       # Include android_system signatures
)
```

**Returns:** `ScreenDetectionResult`

```python
@dataclass
class ScreenDetectionResult:
    app_id: str                          # "instagram"
    screen_id: str                       # "explore_grid" or "unknown"
    confidence: float                    # 0.0 to 1.0
    detection_time_ms: float             # How long detection took
    matched_elements: List[str]          # Which selectors matched
    candidates: List[tuple]              # [(screen_id, score), ...]
    description: str                     # Human-readable description
    is_safe_state: bool                  # Safe for operations?
    recovery_action: Optional[str]       # Suggested recovery
    error: Optional[str]                 # Error if detection failed

    # Properties
    is_confident: bool                   # confidence >= 0.8
    is_unknown: bool                     # screen_id == "unknown"
    full_id: str                         # "app_id/screen_id"
```

**Example:**

```python
result = detector.detect_screen(force_refresh=True)

if result.is_unknown:
    print(f"Unknown screen, candidates: {result.candidates}")
elif result.is_confident:
    print(f"Detected: {result.screen_id} ({result.confidence:.0%})")
else:
    print(f"Low confidence: {result.screen_id} ({result.confidence:.0%})")
```

#### dump_for_signature()

Dump current UI for signature creation.

```python
dump = detector.dump_for_signature()
```

**Returns:** `Dict[str, Any]`

```python
{
    "timestamp": "2025-12-30T10:30:00",
    "resource_ids": ["id1", "id2", ...],
    "content_descs": ["desc1", "desc2", ...],
    "texts": ["text1", "text2", ...],
    "classes": ["FrameLayout", "ImageView", ...],
    "clickables": ["clickable_desc1", ...],
    "total_elements": 142,
    "hint": "Use resource_ids for stable signatures..."
}
```

#### get_stats()

Get detection performance statistics.

```python
stats = detector.get_stats()
# {
#     "detection_count": 150,
#     "average_time_ms": 245.32,
#     "unknown_count": 3,
#     "unknown_rate": 0.020
# }
```

#### invalidate_cache()

Force cache invalidation.

```python
detector.invalidate_cache()
```

### ScreenNavigator

```python
from navigation.navigator import ScreenNavigator

navigator = ScreenNavigator(
    device=device,
    detector=detector,
    app_id="instagram",
)
```

#### navigate_to()

Navigate to target screen with automatic re-pathfinding.

```python
result = navigator.navigate_to(
    target="explore_grid",      # Destination screen ID
    max_attempts=3,             # Maximum navigation attempts
    verify_each_step=True,      # Verify screen after each step
)
```

**Returns:** `NavigationResult`

```python
@dataclass
class NavigationResult:
    status: NavigationStatus              # SUCCESS, FAILED, NO_PATH, ALREADY_THERE
    start_screen: str                     # Where navigation started
    target_screen: str                    # Where we wanted to go
    final_screen: str                     # Where we ended up
    path_taken: List[NavigationStep]      # Steps executed
    steps_completed: int                  # Number of steps
    total_time_seconds: float             # Total time
    error_message: Optional[str]          # Error if failed
    recovery_attempts: int                # Number of retries

    # Properties
    success: bool                         # status in (SUCCESS, ALREADY_THERE)
```

**Example:**

```python
result = navigator.navigate_to("reel_viewing", max_attempts=2)

if result.success:
    print(f"✅ Navigated in {result.total_time_seconds:.1f}s")
    for step in result.path_taken:
        print(f"  {step.from_screen} → {step.to_screen}")
else:
    print(f"❌ Failed: {result.error_message}")
```

#### recover_to_safe_state()

Navigate to a safe state based on context.

```python
result = navigator.recover_to_safe_state(
    context="warmup"  # "warmup", "login", or "browse"
)
```

**Safe State Targets:**

| Context | Preferred Target | All Targets |
|---------|------------------|-------------|
| `warmup` | `explore_grid` | `explore_grid`, `search_results_reels`, `reel_viewing`, `home_feed` |
| `login` | `home_feed` | `home_feed`, `explore_grid`, `profile_page` |
| `browse` | `explore_grid` | `explore_grid`, `search_results_reels` |

#### find_path()

Find shortest path between two screens (without executing).

```python
path = navigator.find_path(
    from_screen="home_feed",
    to_screen="explore_grid",
)

if path:
    print(f"Path length: {len(path)} steps")
    print(f"Estimated reliability: {path.estimated_reliability:.1%}")
    for step in path.steps:
        print(f"  {step.from_screen} → {step.to_screen}")
else:
    print("No path found")
```

#### get_stats()

Get navigation statistics.

```python
stats = navigator.get_stats()
# {
#     "total_navigations": 42,
#     "successful_navigations": 40,
#     "success_rate": 0.952,
#     "total_steps_executed": 87,
#     "average_navigation_time_seconds": 2.3,
#     "graph_screens": 35
# }
```

### Search Functions

```python
from navigation.search import search_for_keyword
```

#### search_for_keyword()

Search for a keyword and navigate to search results.

```python
result = search_for_keyword(
    d=device,
    detector=detector,
    navigator=navigator,
    keyword="dance",
    ensure_reels=True,    # Auto-switch to Reels tab
    timeout=15.0,         # Maximum time for entire operation
)
```

**Returns:** `SearchResult`

```python
@dataclass
class SearchResult:
    success: bool                    # True if search completed
    keyword: str                     # Search keyword
    result_type: SearchResultType    # REELS, ACCOUNTS, UNKNOWN, FAILED
    final_screen: str                # Current screen after search
    steps_taken: List[str]           # Steps performed
    total_time_seconds: float        # Total time
    error_message: Optional[str]     # Error if failed
```

### Signature Registry

```python
from signatures.base import get_registry, get_signatures_for_app

registry = get_registry()
```

#### get_signatures_for_app()

Get signatures for an app.

```python
sigs = get_signatures_for_app(
    app_id="instagram",
    include_system=True,  # Include android_system signatures
)
```

#### get_signature()

Get specific signature.

```python
sig = registry.get_signature(
    app_id="instagram",
    screen_id="explore_grid",
)
```

#### get_all_screen_ids()

Get all registered screen IDs for an app.

```python
screen_ids = registry.get_all_screen_ids("instagram")
# ["home_feed", "explore_grid", "reel_viewing", ...]
```

#### get_safe_states()

Get screen IDs marked as safe states.

```python
safe = registry.get_safe_states("instagram")
# ["explore_grid", "search_results_reels", "reel_viewing", ...]
```

---

## Performance

### Benchmarks

**Detection Performance:**
- **Target**: <500ms detection
- **Typical**: 100-300ms
- **95th percentile**: <500ms
- **Accuracy**: 95%+ with confidence ≥ 0.8

**Cache Performance:**
- **First call**: 100-200ms (UI dump)
- **Cached call**: ~5ms (instant)
- **Cache TTL**: 500ms

**Navigation Performance:**
- **Single step**: 1-2s (action + verification)
- **Average navigation**: 2-3s (2-3 steps)
- **Max navigation**: 5-8s (4-6 steps with retries)

### Optimization Tips

#### 1. Use Cache Wisely

```python
# ✅ Good: Use cache for quick checks
current = detector.detect_screen()  # Uses cache if fresh

# ❌ Bad: Force refresh when not needed
current = detector.detect_screen(force_refresh=True)  # Slow
```

#### 2. Batch Operations

```python
# ✅ Good: Detect once, then act
screen = detector.detect_screen()
if screen.screen_id == "home_feed":
    # Perform multiple actions
    device.click(...)
    device.swipe(...)
    # Then detect again
    new_screen = detector.detect_screen(force_refresh=True)

# ❌ Bad: Detect after every tiny action
detector.detect_screen()
device.click(...)
detector.detect_screen()  # Unnecessary
device.swipe(...)
detector.detect_screen()  # Unnecessary
```

#### 3. Skip Verification When Safe

```python
# ✅ Good: Skip verification for reliable actions
result = navigator.navigate_to(
    "explore_grid",
    verify_each_step=False,  # Faster
)

# Use verification only when:
# - Actions are unreliable (reliability < 0.9)
# - Critical navigation (login flow)
# - Debugging navigation issues
```

#### 4. Monitor Unknown Rate

```python
stats = detector.get_stats()
if stats["unknown_rate"] > 0.05:  # More than 5% unknown
    print("⚠️  High unknown rate - may need new signatures")
    print(f"Unknown: {stats['unknown_count']}/{stats['detection_count']}")
```

#### 5. Prefer Unique Selectors

```python
# ✅ Fast: Unique selector (instant match)
ScreenSignature(
    unique=[":id/explore_action_bar"],
    required=[],
    # ...
)

# ❌ Slower: Many required, no unique
ScreenSignature(
    unique=[],
    required=[":id/a", ":id/b", ":id/c", ":id/d", ":id/e"],
    # ...
)
```

### Performance Monitoring

Track detection stats to identify issues:

```python
stats = detector.get_stats()

# Health metrics
assert stats["average_time_ms"] < 500, "Detection too slow"
assert stats["unknown_rate"] < 0.05, "Too many unknown screens"

# Print summary
print(f"Detection: {stats['detection_count']} calls")
print(f"Avg time: {stats['average_time_ms']:.0f}ms")
print(f"Unknown: {stats['unknown_rate']:.1%}")
```

### Troubleshooting

#### "Detection is slow (>500ms)"

1. Check device connection: `adb devices`
2. Check UI complexity: `device.dump_hierarchy()` size
3. Reduce signatures: Remove unused apps from registry
4. Profile: Add timing logs around `_extract_elements()`

#### "High unknown rate (>5%)"

1. Dump unknown screens: `detector.dump_for_signature()`
2. Create new signatures for common unknowns
3. Check signature quality: Are selectors too specific?
4. Verify clone-safe format: Use `:id/xxx`, not full package IDs

#### "Navigation fails frequently"

1. Check graph completeness: Is path defined?
2. Verify actions: Do selectors exist on target screen?
3. Add retries: Increase `max_attempts`
4. Enable verification: `verify_each_step=True`
5. Check action timing: Increase `wait_after` for slow UI

#### "False positive detections"

1. Signature too permissive: Add forbidden elements
2. Missing required elements: Need more specific selectors
3. Priority wrong: Higher priority screens match first
4. Test with real UI: `dump_for_signature()` and compare

---

## Advanced Topics

### Priority System

Signatures are checked in priority order (highest first):

```
Priority 100: Android system overlays (permissions, crashes)
Priority 90-95: App overlays (comments, peek view)
Priority 80-85: Login/onboarding flow
Priority 40-60: Main navigation screens
Priority 20-35: Content viewing screens
```

**Why Priority Matters:**

```python
# Scenario: User viewing a reel with comments open

# Without priority:
# Might match "reel_viewing" (background screen)

# With priority:
# Priority 95: "comments_view" ✅ Matches first
# Priority 30: "reel_viewing" (never checked)
```

### Clone-Safe Matching

Instagram has multiple clones (GB Instagram, Instagram Lite) with different package names but identical UI structure. Clone-safe matching handles this:

```python
# Official Instagram
resource-id="com.instagram.android:id/explore_action_bar"

# GB Instagram
resource-id="com.gb.instagram:id/explore_action_bar"

# Signature uses clone-safe format
unique=[":id/explore_action_bar"]  # Matches both!

# Matching logic:
if ":id/" in selector:
    id_part = selector.split(":id/")[-1]  # "explore_action_bar"
    for elem in elements:
        if f":id/{id_part}" in elem:  # Matches any package prefix
            return True
```

### Multi-App Support

UIAgent supports multiple apps through the registry:

```python
from signatures.base import register_signatures, ScreenSignature

# Define TikTok signatures
tiktok_sigs = [
    ScreenSignature(
        app_id="tiktok",
        screen_id="for_you_feed",
        # ...
    ),
]

# Register
register_signatures("tiktok", tiktok_sigs)

# Use
detector.detect_screen(app_id="tiktok")
```

### Confidence Interpretation

| Confidence | Interpretation | Action |
|------------|----------------|--------|
| 1.0 | Perfect match (unique element) | Proceed confidently |
| 0.8-0.99 | High confidence | Safe to proceed |
| 0.6-0.79 | Moderate confidence | Verify with secondary check |
| 0.4-0.59 | Low confidence | Manual inspection needed |
| <0.4 | Very low confidence | Treat as unknown |

Access via `result.is_confident` (>= 0.8).

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `navigation/detector.py` | 462 | Core screen detection logic |
| `navigation/navigator.py` | 541 | BFS pathfinding and navigation |
| `navigation/graph.py` | 607 | Navigation graph definitions |
| `navigation/search.py` | 287 | Keyword search functionality |
| `signatures/base.py` | 242 | Signature data structures |
| `signatures/instagram.py` | 997 | Instagram screen signatures |
| `signatures/android_system.py` | 271 | Android system signatures |

---

## See Also

- [UIAgent MCP Server Documentation](../README.md)
- [Navigation Graph Visualization](./NAVIGATION-GRAPH.md) (if exists)
- [Signature Registry Reference](./SIGNATURES.md) (if exists)
