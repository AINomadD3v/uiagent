# UIAgent MCP Server Documentation

## Overview

The UIAgent MCP (Model Context Protocol) server provides Claude Code with direct access to Android devices through uiautomator2. This server exposes 31 tools organized into four tiers, enabling everything from basic device control to sophisticated screen detection and navigation.

**Key Differentiator**: The `run_script` tool allows Claude to execute complete Python automation scripts in a single call (vs individual tap/swipe commands), making it dramatically more efficient for complex automation tasks.

**Architecture**:
- Built with FastMCP framework
- Integrates with existing UIAgent components (AndroidDriver, AndroidProvider)
- Background thread system for popup management
- Signature-based screen detection (40+ known Instagram screens)
- BFS pathfinding for automated navigation

## Quick Start

### Installation

Add the UIAgent MCP server to Claude Code CLI:

```bash
# Method 1: Using .mcp.json in project directory
cat > .mcp.json <<EOF
{
  "mcpServers": {
    "uiagent": {
      "command": "nix",
      "args": ["develop", "--command", "python", "mcp_server.py"],
      "cwd": "/home/aidev/phone-farm-tools/uiagent",
      "env": {
        "SUPPRESS_SHELL_HOOK": "1"
      }
    }
  }
}
EOF

# Method 2: Global installation (user scope)
claude mcp add uiagent --scope user --transport stdio \
  -- nix develop /home/aidev/phone-farm-tools/uiagent --command python mcp_server.py
```

### First Commands

```python
# 1. List available devices
devices = list_devices()
serial = devices[0]["serial"]

# 2. Take a screenshot to see current state
image = screenshot(serial)

# 3. Run a simple automation script
result = run_script(serial, '''
    # Click a button
    d(text="Login").click()

    # Wait for home screen
    d(resourceId="com.app:id/home").wait(timeout=10)

    print("Navigation complete!")
''')
```

## Tool Reference

### TIER 1: Basic Device Control

#### 1. list_devices()

List all connected Android devices.

**Signature**:
```python
def list_devices() -> List[Dict[str, Any]]
```

**Parameters**: None

**Returns**:
```python
[
    {
        "serial": str,      # Device serial number (required for other tools)
        "model": str,       # Device model name
        "name": str,        # Device display name
        "status": str,      # Connection status
        "enabled": bool     # Whether device is available
    },
    ...
]
```

**Example**:
```python
devices = list_devices()
serial = devices[0]["serial"]  # Use this serial for other tools
```

---

#### 2. screenshot(serial)

Capture a screenshot from the Android device.

**Signature**:
```python
def screenshot(serial: str) -> MCPImage
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number from list_devices() |

**Returns**: JPEG image (FastMCP Image object) that Claude can analyze visually

**Notes**:
- Automatically resized to 1568px max dimension for optimal Claude analysis
- Returns multimodal image that Claude can see and analyze

**Example**:
```python
devices = list_devices()
serial = devices[0]["serial"]

# Capture screenshot
image = screenshot(serial)
# Claude can now analyze the image visually
```

---

#### 3. tap(serial, x, y)

Tap at specific screen coordinates.

**Signature**:
```python
def tap(serial: str, x: int, y: int) -> TapResult
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| x | int | Yes | X coordinate in pixels (0 = left edge) |
| y | int | Yes | Y coordinate in pixels (0 = top edge) |

**Returns**:
```python
{
    "success": bool,    # Whether tap was executed
    "x": int,          # X coordinate tapped
    "y": int           # Y coordinate tapped
}
```

**Example**:
```python
# Get screen size first if needed
info = device_info(serial)
center_x = info["screen_width"] // 2
center_y = info["screen_height"] // 2
tap(serial, center_x, center_y)
```

**Note**: For complex automation with element selection, prefer `run_script()`.

---

#### 4. shell(serial, command)

Execute a shell command on the Android device via ADB.

**Signature**:
```python
def shell(serial: str, command: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| command | str | Yes | Shell command string |

**Returns**:
```python
{
    "output": str,  # Command stdout
    "error": str    # Command stderr
}
```

**Examples**:
```python
# Get Android version
shell(serial, "getprop ro.build.version.release")

# List installed packages
shell(serial, "pm list packages | grep instagram")

# Check current activity
shell(serial, "dumpsys activity activities | grep mResumedActivity")
```

**Common Use Cases**:
- Get system properties: `getprop ro.build.version.release`
- List files: `ls /sdcard/`
- Check processes: `ps | grep com.app`
- Manage apps: `pm list packages`

---

#### 5. device_info(serial)

Get detailed information about a device in one call.

**Signature**:
```python
def device_info(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "serial": str,
    "model": str,
    "name": str,
    "screen_width": int,
    "screen_height": int,
    "current_app": {
        "package": str,   # Currently running package
        "activity": str,  # Current activity
        "pid": int        # Process ID
    } | None
}
```

**Example**:
```python
info = device_info(serial)
print(f"Screen: {info['screen_width']}x{info['screen_height']}")
print(f"Current app: {info['current_app']['package']}")
```

---

### TIER 2: Automation Scripting

#### 6. run_script(serial, code, timeout_seconds=60) 🌟

**CORE TOOL** - Execute Python automation code with full uiautomator2 access.

**Signature**:
```python
async def run_script(
    serial: str,
    code: str,
    timeout_seconds: int = 60
) -> ScriptResult
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| code | str | Yes | - | Python code to execute |
| timeout_seconds | int | No | 60 | Max execution time (max: 300s) |

**Available Globals in Execution Context**:
- `d`: uiautomator2.Device - The connected device instance
- `u2`: uiautomator2 module - For constants and utilities
- `time`: time module - For delays (use sparingly)
- `json`: json module - For data handling
- `os`, `sys`: Standard library modules

**Returns**:
```python
{
    "stdout": str,              # Captured stdout output
    "stderr": str,              # Captured stderr output
    "result": str | None,       # repr() of final expression result
    "error": str | None,        # Exception traceback if execution failed
    "debug_log": str | None     # Line-by-line execution trace
}
```

**Examples**:

```python
# Click login and wait for home
result = run_script(serial, '''
    d.xpath("//button[@resource-id='com.app:id/login']").click()
    d.xpath("//view[@resource-id='com.app:id/home']").wait(timeout=10)
    print("Login successful")
''')

# Scroll through feed
result = run_script(serial, '''
    for i in range(5):
        d.swipe(0.5, 0.8, 0.5, 0.3)
        time.sleep(1)
    print("Scrolled 5 times")
''')

# Conditional logic
result = run_script(serial, '''
    if d.xpath("//button[@text='Accept']").exists(timeout=2):
        d.xpath("//button[@text='Accept']").click()
        print("Dismissed popup")
    d.xpath("//button[@text='Login']").click()
''')
```

**Notes**:
- Timeout capped at 300 seconds (5 minutes)
- Use this for complex automation - much more efficient than individual tap/swipe commands
- Scripts run in isolated executor with asyncio timeout enforcement

---

#### 7. ui_hierarchy(serial)

Get the UI element hierarchy from the device screen.

**Signature**:
```python
def ui_hierarchy(serial: str) -> HierarchyResult
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "xml": str,              # Raw XML hierarchy dump
    "tree": Dict[str, Any],  # Parsed UI element tree
    "screen_width": int,
    "screen_height": int
}
```

**WARNING**: Returns LARGE data (10k+ lines for complex screens). Use sparingly - prefer `screenshot()` for initial analysis.

**Use this when you need to**:
- Find element resource-ids or content-desc values
- Build xpath selectors for automation
- Locate clickable elements programmatically

**Key Element Properties**:
- `resource-id`: Most stable selector (e.g., 'com.app:id/login_btn')
- `content-desc`: Accessibility label
- `text`: Visible text (least stable)
- `clickable`: Whether element accepts clicks
- `bounds`: Element position [x1,y1][x2,y2]

---

#### 8. get_elements(serial, filter="interactive", max_elements=50)

Get filtered UI elements in a Claude-consumable format.

**Signature**:
```python
def get_elements(
    serial: str,
    filter: str = "interactive",
    max_elements: int = 50
) -> List[Dict[str, Any]]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| filter | str | No | "interactive" | Element filter mode |
| max_elements | int | No | 50 | Maximum elements to return |

**Filter Options**:
- `"interactive"`: Clickable, checkable, or focusable elements (default)
- `"text"`: Elements with visible text or content description
- `"inputs"`: Editable text fields
- `"all"`: All elements (warning: can be large)
- Custom xpath: e.g., `"//*[@resource-id='com.app:id/btn']"`

**Returns**:
```python
[
    {
        "index": int,               # Position in results
        "selector": str,            # XPath selector to target this element
        "text": str | None,         # Visible text (if any)
        "desc": str | None,         # Content description (if any)
        "resource_id": str | None,  # Resource ID (if any)
        "type": str,                # Simplified element type (Button, TextView, etc.)
        "bounds": [int, int, int, int],  # [x1, y1, x2, y2]
        "clickable": bool,          # Whether element is clickable
        "center": [int, int]        # [x, y] center point for tapping
    },
    ...
]
```

**Example Workflow**:
```python
# 1. Screenshot to see the screen
screenshot(serial)

# 2. Get interactive elements
elements = get_elements(serial, filter="interactive")
# Returns: [{"index": 0, "selector": "...", "text": "Login", ...}, ...]

# 3. Use selector in run_script
run_script(serial, '''
    d.xpath("//android.widget.Button[@text='Login']").click()
''')

# Get all text inputs
inputs = get_elements(serial, filter="inputs")

# Custom xpath - find by partial resource-id
buttons = get_elements(serial, filter="//*[contains(@resource-id, 'btn')]")
```

**Notes**: MUCH more efficient than `ui_hierarchy` for navigation tasks. Returns only essential info needed to interact with elements.

---

#### 9. wait_for(serial, text=None, text_gone=None, xpath=None, timeout=10.0)

Wait for a condition on the device screen.

**Signature**:
```python
def wait_for(
    serial: str,
    text: Optional[str] = None,
    text_gone: Optional[str] = None,
    xpath: Optional[str] = None,
    timeout: float = 10.0
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| text | str | No | None | Wait for this text to appear on screen |
| text_gone | str | No | None | Wait for this text to disappear |
| xpath | str | No | None | Wait for element matching this xpath |
| timeout | float | No | 10.0 | Max wait time in seconds |

**Returns**:
```python
{
    "found": bool,      # Whether condition was met
    "elapsed": float,   # Time waited in seconds
    "message": str      # Description of result
}
```

**Examples**:
```python
# Wait for loading to finish
wait_for(serial, text_gone="Loading...")

# Wait for login button to appear
wait_for(serial, text="Login", timeout=15)

# Wait for specific element
wait_for(serial, xpath="//*[@resource-id='com.app:id/home_feed']")
```

**Notes**: Essential for async UI operations - wait for elements to appear/disappear before proceeding with automation.

---

#### 10. swipe(serial, direction=None, start_x=None, start_y=None, end_x=None, end_y=None, duration=0.3)

Perform a swipe gesture on the device.

**Signature**:
```python
def swipe(
    serial: str,
    direction: Optional[str] = None,
    start_x: Optional[float] = None,
    start_y: Optional[float] = None,
    end_x: Optional[float] = None,
    end_y: Optional[float] = None,
    duration: float = 0.3
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| direction | str | No | None | Named direction: "up", "down", "left", "right" |
| start_x | float | No | None | Starting X (pixels or 0.0-1.0 relative) |
| start_y | float | No | None | Starting Y (pixels or 0.0-1.0 relative) |
| end_x | float | No | None | Ending X (pixels or 0.0-1.0 relative) |
| end_y | float | No | None | Ending Y (pixels or 0.0-1.0 relative) |
| duration | float | No | 0.3 | Swipe duration in seconds |

**Returns**:
```python
# For direction-based swipes:
{
    "success": bool,
    "direction": str,
    "duration": float
}

# For coordinate-based swipes:
{
    "success": bool,
    "start": [float, float],
    "end": [float, float],
    "duration": float
}
```

**Examples**:
```python
# Scroll down (swipe up)
swipe(serial, direction="up")

# Scroll up (swipe down)
swipe(serial, direction="down")

# Swipe left to go to next item
swipe(serial, direction="left")

# Custom swipe with relative coords (center to top)
swipe(serial, start_x=0.5, start_y=0.7, end_x=0.5, end_y=0.3)
```

**Notes**: Provide either `direction` OR all of (start_x, start_y, end_x, end_y). Coordinates can be absolute pixels or relative (0.0-1.0).

---

#### 11. app_launch(serial, package, activity=None, wait=True)

Launch an app by package name.

**Signature**:
```python
def app_launch(
    serial: str,
    package: str,
    activity: Optional[str] = None,
    wait: bool = True
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| package | str | Yes | - | App package name |
| activity | str | No | None | Specific activity to launch |
| wait | bool | No | True | Wait for app to launch |

**Returns**:
```python
{
    "success": bool,
    "package": str,
    "current_package": str,    # Actual current package
    "current_activity": str,   # Actual current activity
    "error": str | None        # Error message if failed
}
```

**Examples**:
```python
# Launch Instagram
app_launch(serial, package="com.instagram.android")

# Launch Chrome
app_launch(serial, package="com.android.chrome")

# Launch with specific activity
app_launch(serial, package="com.app", activity=".MainActivity")
```

---

#### 12. app_terminate(serial, package)

Stop/kill an app by package name.

**Signature**:
```python
def app_terminate(serial: str, package: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| package | str | Yes | App package name to terminate |

**Returns**:
```python
{
    "success": bool,
    "package": str,
    "message": str,
    "error": str | None
}
```

**Example**:
```python
# Stop Instagram
app_terminate(serial, package="com.instagram.android")
```

---

#### 13. app_list(serial, filter="third_party")

List installed apps on the device.

**Signature**:
```python
def app_list(
    serial: str,
    filter: str = "third_party"
) -> List[Dict[str, Any]]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| filter | str | No | "third_party" | Which apps to list |

**Filter Options**:
- `"third_party"`: User-installed apps only (default)
- `"system"`: System apps only
- `"all"`: All apps

**Returns**:
```python
[
    {"package": str},
    ...
]
```

**Examples**:
```python
# Get user-installed apps
apps = app_list(serial)

# Get all apps including system
apps = app_list(serial, filter="all")
```

---

#### 14. file_push(serial, local_path, remote_path)

Push a file from local machine to the Android device.

**Signature**:
```python
def file_push(
    serial: str,
    local_path: str,
    remote_path: str
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| local_path | str | Yes | Path to local file |
| remote_path | str | Yes | Destination path on device |

**Returns**:
```python
{
    "success": bool,
    "local": str,
    "remote": str,
    "message": str,
    "error": str | None
}
```

**Example**:
```python
file_push(serial, "/tmp/config.json", "/sdcard/Download/config.json")
```

---

#### 15. file_pull(serial, remote_path, local_path)

Pull a file from the Android device to local machine.

**Signature**:
```python
def file_pull(
    serial: str,
    remote_path: str,
    local_path: str
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| remote_path | str | Yes | Path to file on device |
| local_path | str | Yes | Destination path on local machine |

**Returns**:
```python
{
    "success": bool,
    "remote": str,
    "local": str,
    "message": str,
    "error": str | None
}
```

**Example**:
```python
file_pull(serial, "/sdcard/screenshot.png", "/tmp/screenshot.png")
```

---

#### 16. get_orientation(serial)

Get the current screen orientation.

**Signature**:
```python
def get_orientation(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "orientation": str,  # "portrait", "landscape", "portrait-reverse", "landscape-reverse"
    "rotation": int,     # 0, 90, 180, or 270 degrees
    "raw": int,          # Raw rotation value (0-3)
    "error": str | None
}
```

---

#### 17. set_orientation(serial, orientation)

Set the screen orientation.

**Signature**:
```python
def set_orientation(
    serial: str,
    orientation: str
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |
| orientation | str | Yes | Target orientation |

**Orientation Options**:
- `"natural"` or `"portrait"`: Default portrait
- `"left"` or `"landscape"`: Rotate left (landscape)
- `"right"`: Rotate right (landscape)
- `"upsidedown"`: Upside down portrait

**Returns**:
```python
{
    "success": bool,
    "orientation": str,
    "message": str,
    "error": str | None
}
```

**Examples**:
```python
# Force landscape
set_orientation(serial, "landscape")

# Back to portrait
set_orientation(serial, "portrait")
```

---

### TIER 3: Popup Management (Background Thread System)

The popup management system runs a background thread that continuously monitors for configured popup patterns and dismisses them automatically. All dismissals are recorded to history for later review.

#### 18. popup_configure(serial, patterns, append=True)

Configure popup patterns for automatic dismissal.

**Signature**:
```python
def popup_configure(
    serial: str,
    patterns: List[Dict[str, str]],
    append: bool = True
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| patterns | List[Dict] | Yes | - | Pattern definitions |
| append | bool | No | True | If True, add to existing patterns. If False, replace all. |

**Pattern Structure**:
```python
{
    "name": str,           # Human-readable identifier (e.g., "save_login_info")
    "detect_xpath": str,   # XPath to detect popup presence
    "dismiss_xpath": str,  # XPath for element to click to dismiss
    "type": str            # Optional: "popup" (default) or "toast"
}
```

**Returns**:
```python
{
    "success": bool,
    "patterns_added": int,
    "total_patterns": int,
    "message": str
}
```

**Example**:
```python
popup_configure(serial, [
    {
        "name": "save_login_info",
        "detect_xpath": "//*[@content-desc='Save your login info?']",
        "dismiss_xpath": "//*[@text='Not now' or @text='Not Now']"
    },
    {
        "name": "notifications_prompt",
        "detect_xpath": "//*[contains(@text, 'Turn on notifications')]",
        "dismiss_xpath": "//*[@text='Not Now']"
    }
])
```

**Notes**: Patterns are automatically loaded from `popup_patterns.json` on first device access. Use this to add additional patterns or replace defaults.

---

#### 19. popup_enable(serial)

Start automatic popup dismissal in background.

**Signature**:
```python
def popup_enable(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "success": bool,
    "status": str,           # "started", "already_running", "no_patterns"
    "pattern_count": int,
    "message": str
}
```

**Example**:
```python
# First configure patterns (optional if defaults exist)
popup_configure(serial, [...])

# Then enable auto-dismiss
popup_enable(serial)

# Now popups will be auto-dismissed in background
# Check what was dismissed:
popup_history(serial)
```

**Notes**:
- Launches a background thread that continuously monitors for configured popup patterns
- All dismissals are recorded to history for later review
- Auto-enabled on first device access if default patterns exist

---

#### 20. popup_disable(serial)

Stop automatic popup dismissal.

**Signature**:
```python
def popup_disable(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "success": bool,
    "status": str,  # "stopped", "not_running"
    "message": str
}
```

**Notes**: Stops the background watcher thread. Patterns are preserved and can be re-enabled with `popup_enable()`. History is also preserved.

---

#### 21. popup_history(serial, clear=False, limit=20)

Get history of auto-dismissed popups.

**Signature**:
```python
def popup_history(
    serial: str,
    clear: bool = False,
    limit: int = 20
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| clear | bool | No | False | Clear history after returning |
| limit | int | No | 20 | Max records to return (newest first) |

**Returns**:
```python
{
    "entries": [
        {
            "name": str,
            "type": str,              # "popup" or "toast"
            "timestamp": str,         # ISO 8601 timestamp
            "detect_xpath": str,
            "dismiss_xpath": str,
            "dismissed": bool,        # For popups: whether dismiss succeeded
            "verified": bool,         # For popups: whether popup disappeared
            "captured_text": str,     # For toasts: captured text content
            "message": str
        },
        ...
    ],
    "total": int,              # Total records in history
    "returned": int,           # Number of records returned
    "watcher_active": bool,    # Whether watcher is currently running
    "pattern_count": int       # Number of configured patterns
}
```

**Example**:
```python
# After running some automation...
history = popup_history(serial)

# Shows: [
#   {"name": "save_login_info", "timestamp": "...", "dismissed": True},
#   {"name": "notifications", "timestamp": "...", "dismissed": True}
# ]
```

**Notes**: Essential for understanding automation flow and debugging. History is a ring buffer (max 100 entries per device).

---

#### 22. popup_check(serial, patterns=None)

One-shot check for popups on screen right now.

**Signature**:
```python
def popup_check(
    serial: str,
    patterns: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| patterns | List[Dict] | No | None | Optional patterns to check. If None, uses configured patterns. |

**Returns**:
```python
{
    "found": [
        {
            "name": str,
            "detect_xpath": str,
            "dismiss_xpath": str,
            "visible": bool
        },
        ...
    ],
    "checked": int,         # Number of patterns checked
    "any_visible": bool,    # True if any popups found
    "message": str
}
```

**Examples**:
```python
# Check configured patterns
result = popup_check(serial)
# Returns: {"found": [{"name": "save_login", ...}], "checked": 5}

# Check custom patterns (discovery mode)
popup_check(serial, patterns=[
    {"name": "test", "detect_xpath": "//*[contains(@text, 'Error')]"}
])
```

**Notes**:
- Unlike the background watcher, this is a single check that returns immediately
- Useful for discovery (finding new popup patterns), debugging, and manual handling

---

### TIER 4: Screen Detection & Navigation (NEW - December 2025)

The screen detection and navigation system uses signature-based fingerprinting to identify screens and BFS pathfinding to navigate between them. Supports 40+ known Instagram screens and system overlays.

#### 23. detect_screen(serial, app_id="instagram", force_refresh=False)

Detect the current screen using signature-based fingerprinting.

**Signature**:
```python
def detect_screen(
    serial: str,
    app_id: str = "instagram",
    force_refresh: bool = False
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| app_id | str | No | "instagram" | App to detect screens for |
| force_refresh | bool | No | False | If True, bypasses 500ms UI cache |

**Returns**:
```python
{
    "app_id": str,                   # App the screen belongs to
    "screen_id": str,                # Detected screen identifier
    "full_id": str,                  # Combined "app_id/screen_id" format
    "confidence": float,             # 0.0 to 1.0 confidence score
    "is_confident": bool,            # True if confidence >= 0.8
    "is_unknown": bool,              # True if screen couldn't be identified
    "detection_time_ms": float,      # How long detection took
    "matched_elements": List[str],   # Which signature selectors matched
    "candidates": List[Tuple[str, float]],  # Alternative matches [(screen_id, score), ...]
    "description": str,              # Human-readable screen description
    "is_safe_state": bool,           # Whether this is a safe state for operations
    "recovery_action": str           # Suggested recovery action if stuck
}
```

**Detection System**:
1. Dumps UI hierarchy once
2. Extracts element identifiers (resource-ids, text, content-desc)
3. Matches against 40+ known screen signatures
4. Returns confidence score and matched elements

**Known Screens (Instagram)**:
- `home_feed`, `explore_grid`, `profile_page`, `dm_inbox`, `reels_tab`
- `reel_viewing`, `story_viewing`, `comments_view`, `likes_page`
- `login_page`, `login_2fa_code`, `login_save_info`
- `create_post_select`, `create_post_edit`, `create_reel_camera`
- `search_results_reels`, `profile_grid`, `profile_followers`
- ...and 30+ more

**System Overlays** (detected automatically):
- `permission_dialog`, `app_crash_dialog`, `app_not_responding`
- `battery_optimization`, `no_internet_dialog`

**Example Workflow**:
```python
# 1. Detect where we are
screen = detect_screen(serial, app_id="instagram")
print(f"Current screen: {screen['screen_id']}")

# 2. Take action based on screen
if screen['screen_id'] == 'home_feed':
    # Already on home, good to go
    pass
elif screen['screen_id'] == 'permission_dialog':
    # Need to dismiss permission dialog first
    run_script(serial, "d(text='Deny').click()")
```

**Performance Targets**:
- Detection time: <500ms (typically 100-300ms)
- Unknown rate: <5%

---

#### 24. dump_for_signature(serial)

Dump current UI for creating new screen signatures.

**Signature**:
```python
def dump_for_signature(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "timestamp": str,           # When dump was taken
    "resource_ids": List[str],  # Element IDs (use ":id/xxx" format in signatures)
    "content_descs": List[str], # Content descriptions
    "texts": List[str],         # Visible text values
    "classes": List[str],       # Element class types
    "clickables": List[str],    # Clickable element descriptions
    "total_elements": int,      # Total extracted elements
    "hint": str                 # Usage guidance for creating signatures
}
```

**Creating a New Signature from Dump**:
1. Call `dump_for_signature` when on unknown screen
2. Identify unique elements in `resource_ids`
3. Create ScreenSignature with:
   - `unique`: Elements that ONLY appear on this screen
   - `required`: Elements that MUST be present
   - `forbidden`: Elements that MUST NOT be present
   - `optional`: Elements that boost confidence if present

**Example**:
```python
# On unknown screen
dump = dump_for_signature(serial)
print(dump['resource_ids'])
# ['action_bar_search_edit_text', 'search_row_container', ...]

# Create signature using these IDs:
# ScreenSignature(
#     app_id="instagram",
#     screen_id="new_screen",
#     unique=[":id/action_bar_search_edit_text"],
#     required=[":id/search_row_container"],
#     ...
# )
```

---

#### 25. get_screen_info(app_id="instagram", screen_id=None)

Get information about available screens and signatures.

**Signature**:
```python
def get_screen_info(
    app_id: str = "instagram",
    screen_id: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| app_id | str | No | "instagram" | App to get screen info for |
| screen_id | str | No | None | Optional specific screen to get details for |

**Returns (List Mode - screen_id=None)**:
```python
{
    "app_id": str,
    "screens": List[str],           # List of all screen_ids
    "safe_states": List[str],       # Screen IDs marked as safe for operations
    "total_count": int,             # Total number of signatures
    "apps_available": List[str]     # All registered app IDs
}
```

**Returns (Detail Mode - screen_id provided)**:
```python
{
    "app_id": str,
    "screen_id": str,
    "full_id": str,
    "description": str,              # Human-readable description
    "required": List[str],           # Required element selectors
    "forbidden": List[str],          # Forbidden element selectors
    "unique": List[str],             # Unique identifier selectors
    "optional": List[str],           # Optional boost selectors
    "priority": int,                 # Detection priority (higher = checked first)
    "recovery_action": str,          # Suggested recovery if stuck
    "is_safe_state": bool            # Whether safe for operations
}
```

**Examples**:
```python
# List all screens
info = get_screen_info(app_id="instagram")
print(f"Known screens: {info['screens']}")
print(f"Safe states: {info['safe_states']}")

# Get specific screen details
info = get_screen_info(app_id="instagram", screen_id="home_feed")
print(f"Description: {info['description']}")
print(f"Unique elements: {info['unique']}")
```

---

#### 26. get_detection_stats(serial)

Get screen detection performance statistics.

**Signature**:
```python
def get_detection_stats(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "detection_count": int,      # Total detections performed
    "average_time_ms": float,    # Average detection time
    "unknown_count": int,        # Times detection returned "unknown"
    "unknown_rate": float        # Ratio of unknown detections (0.0-1.0)
}
```

**Performance Targets**:
- `average_time_ms`: <500ms (typically 100-300ms)
- `unknown_rate`: <0.05 (5% unknown is concerning)

**Example**:
```python
stats = get_detection_stats(serial)
if stats['unknown_rate'] > 0.1:
    print("High unknown rate - may need new signatures")
if stats['average_time_ms'] > 500:
    print("Detection running slow - check device connection")
```

---

#### 27. navigate_to(serial, target_screen, app_id="instagram", max_attempts=3, verify_steps=True)

Navigate to a target screen using BFS pathfinding.

**Signature**:
```python
def navigate_to(
    serial: str,
    target_screen: str,
    app_id: str = "instagram",
    max_attempts: int = 3,
    verify_steps: bool = True
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| target_screen | str | Yes | - | Screen ID to navigate to |
| app_id | str | No | "instagram" | App to navigate in |
| max_attempts | int | No | 3 | Maximum retry attempts |
| verify_steps | bool | No | True | Verify screen after each step |

**Automatic Navigation**:
1. Detects current screen
2. Finds shortest path to target
3. Executes navigation actions (clicks, back presses)
4. Verifies each step
5. Re-pathfinds if navigation goes off-track

**Returns**:
```python
{
    "status": str,                    # "success", "already_there", "failed", "no_path"
    "success": bool,                  # True if navigation completed
    "start_screen": str,              # Where navigation started
    "target_screen": str,             # Where we wanted to go
    "final_screen": str,              # Where we ended up
    "steps_completed": int,           # Number of steps taken
    "total_time_seconds": float,      # How long navigation took
    "path_summary": List[str],        # List of "from → to" transitions
    "error_message": str | None       # Error details if failed
}
```

**Known Screens (Instagram)**:
- `home_feed`, `explore_grid`, `reels_tab`, `profile_page`
- `reel_viewing`, `comments_view`, `likes_page`
- `search_results_reels`, `search_results_accounts`
- `dm_inbox`, `story_viewing`, `create_post_select`
- `profile_followers`, `profile_following`

**Examples**:
```python
# Navigate from anywhere to explore
result = navigate_to(serial, "explore_grid")
if result['success']:
    print(f"Arrived in {result['total_time_seconds']:.1f}s")

# Navigate to home feed
navigate_to(serial, "home_feed")

# Navigate to reels viewing
navigate_to(serial, "reel_viewing")
```

---

#### 28. recover_to_safe_state(serial, context="warmup", app_id="instagram")

Navigate to a known safe state for recovery.

**Signature**:
```python
def recover_to_safe_state(
    serial: str,
    context: str = "warmup",
    app_id: str = "instagram"
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| context | str | No | "warmup" | Recovery context |
| app_id | str | No | "instagram" | App to recover in |

**Context Options**:
- `"warmup"`: For warmup operations (targets: explore_grid, search_results_reels)
- `"login"`: After login (targets: home_feed, explore_grid)
- `"browse"`: General browsing (targets: explore_grid)

**Safe States by Context**:
- **warmup**: explore_grid, search_results_reels, reel_viewing, home_feed
- **login**: home_feed, explore_grid, profile_page
- **browse**: explore_grid, search_results_reels

**Returns**: Same as `navigate_to()`

**Example**:
```python
# Recover after getting stuck
result = recover_to_safe_state(serial, context="warmup")
if result['success']:
    print(f"Recovered to {result['final_screen']}")
```

**Notes**: Use this when automation gets stuck or is in an unknown state. Will navigate to a predictable screen based on context.

---

#### 29. get_navigation_graph(from_screen=None)

Get information about the navigation graph.

**Signature**:
```python
def get_navigation_graph(
    from_screen: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| from_screen | str | No | None | If provided, get only edges from this screen. If None, returns summary. |

**Returns (Summary Mode - from_screen=None)**:
```python
{
    "total_screens": int,        # Number of screens with outgoing edges
    "all_screens": List[str],    # List of all screen IDs in graph
    "safe_states": List[str]     # Screens marked as safe for recovery
}
```

**Returns (Detail Mode - from_screen provided)**:
```python
{
    "screen_id": str,
    "edges": [
        {
            "to_screen": str,
            "cost": int,           # Navigation cost
            "reliability": float,  # Success probability (0.0-1.0)
            "description": str,    # Human-readable description
            "actions_count": int   # Number of actions in this edge
        },
        ...
    ],
    "edge_count": int
}
```

**Examples**:
```python
# Get graph overview
info = get_navigation_graph()
print(f"Total screens: {info['total_screens']}")

# Get edges from explore_grid
edges = get_navigation_graph(from_screen="explore_grid")
for e in edges['edges']:
    print(f"  → {e['to_screen']} ({e['description']})")
```

---

#### 30. get_navigation_stats(serial)

Get navigation performance statistics.

**Signature**:
```python
def get_navigation_stats(serial: str) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Description |
|------|------|----------|-------------|
| serial | str | Yes | Device serial number |

**Returns**:
```python
{
    "total_navigations": int,                  # Total navigation attempts
    "successful_navigations": int,             # Successful navigations
    "success_rate": float,                     # Success ratio (0.0-1.0)
    "total_steps_executed": int,               # Total steps taken
    "average_navigation_time_seconds": float,  # Average time per navigation
    "graph_screens": int                       # Number of screens in navigation graph
}
```

**Example**:
```python
stats = get_navigation_stats(serial)
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Avg time: {stats['average_navigation_time_seconds']:.1f}s")
```

---

#### 31. search_for_keyword(serial, keyword, ensure_reels=True, timeout=15.0, app_id="instagram")

Search for a keyword and navigate to search results.

**Signature**:
```python
def search_for_keyword(
    serial: str,
    keyword: str,
    ensure_reels: bool = True,
    timeout: float = 15.0,
    app_id: str = "instagram"
) -> Dict[str, Any]
```

**Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| serial | str | Yes | - | Device serial number |
| keyword | str | Yes | - | Search keyword to enter |
| ensure_reels | bool | No | True | If True, switch to Reels tab if showing accounts |
| timeout | float | No | 15.0 | Maximum time for entire operation (seconds) |
| app_id | str | No | "instagram" | App to search in |

**Automatic Search Flow**:
1. Navigate to explore_grid if not already there
2. Click search bar
3. Type the keyword with human-like delays
4. Press Enter to search
5. Wait for results
6. Optionally switch to Reels tab if showing accounts

**Returns**:
```python
{
    "success": bool,                # True if search completed
    "keyword": str,                 # The keyword that was searched
    "result_type": str,             # "reels", "accounts", "unknown", or "failed"
    "final_screen": str,            # Current screen after search
    "steps_taken": List[str],       # List of steps performed
    "total_time_seconds": float,    # How long the operation took
    "error_message": str | None     # Error details if failed
}
```

**Examples**:
```python
# Search for dance reels
result = search_for_keyword(serial, keyword="dance")
if result['success'] and result['result_type'] == 'reels':
    print(f"Ready to browse reels!")

# Search without auto-switching to Reels tab
result = search_for_keyword(serial, keyword="fashion", ensure_reels=False)

# Search with custom timeout
result = search_for_keyword(serial, keyword="cats", timeout=20.0)
```

**Notes**: This tool handles the dynamic search flow that can't be done through static navigation edges. Includes human-like typing delays for natural interaction.

---

## Security & Timeouts

### Script Timeout Enforcement

The `run_script` tool enforces strict timeout limits to prevent runaway executions:

- **Default timeout**: 60 seconds
- **Maximum timeout**: 300 seconds (5 minutes)
- **Enforcement**: asyncio.wait_for with executor
- **Behavior on timeout**: Returns ScriptResult with error indicating timeout

```python
# Timeout example
result = run_script(serial, '''
    # Long-running operation
    for i in range(1000):
        d.swipe(0.5, 0.8, 0.5, 0.3)
        time.sleep(0.5)
''', timeout_seconds=120)  # Will timeout after 120s

if result.error and "timed out" in result.error:
    print("Script execution exceeded timeout")
```

### Thread Safety

The popup management system uses thread-safe mechanisms:

- **Global lock**: `threading.Lock()` protects shared state
- **Per-device state**: Patterns, history, and threads tracked separately per device
- **Ring buffer**: History limited to 100 entries per device (FIFO)
- **Daemon threads**: Background watchers won't prevent server shutdown

### Screen Detection Caching

The screen detector implements a 500ms UI hierarchy cache:

- **Purpose**: Avoid redundant UI dumps during rapid detection calls
- **Override**: Use `force_refresh=True` to bypass cache
- **Thread safety**: Cache invalidation is automatic and thread-safe

---

## Troubleshooting

### Common Issues

#### "Device not found: {serial}"

**Cause**: Device serial doesn't match any connected device

**Solution**:
```python
# List available devices
devices = list_devices()
for d in devices:
    print(f"Serial: {d['serial']}, Status: {d['status']}, Enabled: {d['enabled']}")

# Use correct serial
serial = devices[0]["serial"]
```

#### "Device not available: {serial} (status: offline)"

**Cause**: Device is offline or not properly connected

**Solution**:
```bash
# Check ADB connection
adb devices

# Restart ADB server
adb kill-server
adb start-server

# Reconnect device
adb connect <device_ip>:5555
```

#### "Script execution timed out after Xs"

**Cause**: Script exceeded timeout limit

**Solution**:
```python
# Option 1: Increase timeout
result = run_script(serial, code, timeout_seconds=120)

# Option 2: Break into smaller steps
result1 = run_script(serial, code_part1, timeout_seconds=60)
result2 = run_script(serial, code_part2, timeout_seconds=60)
```

#### "No popup patterns configured"

**Cause**: Attempted to enable popup watcher with no patterns

**Solution**:
```python
# Configure patterns first
popup_configure(serial, [
    {
        "name": "example",
        "detect_xpath": "//*[@text='Close']",
        "dismiss_xpath": "//*[@text='Close']"
    }
])

# Then enable
popup_enable(serial)
```

#### High unknown rate in screen detection

**Cause**: Encountering screens without signatures

**Solution**:
```python
# Dump UI for signature creation
dump = dump_for_signature(serial)
print(dump['resource_ids'])

# Create new signature in signatures/instagram.py
# Then add to registry
```

#### Navigation fails with "no_path" status

**Cause**: No navigation path exists from current screen to target

**Solution**:
```python
# Check available navigation paths
graph = get_navigation_graph(from_screen="current_screen")
print(f"Available destinations: {[e['to_screen'] for e in graph['edges']]}")

# Use recovery to get to known state first
recover_to_safe_state(serial, context="warmup")

# Then navigate to target
navigate_to(serial, target_screen="desired_screen")
```

### Performance Issues

#### Slow screen detection (>500ms)

**Possible causes**:
- Slow device connection
- Complex UI hierarchy
- Network latency (WiFi ADB)

**Solutions**:
```python
# Check detection stats
stats = get_detection_stats(serial)
print(f"Average time: {stats['average_time_ms']}ms")

# Use USB connection instead of WiFi ADB
# Reduce UI complexity (close background apps)
```

#### Screenshot tool returns empty/black images

**Possible causes**:
- App has FLAG_SECURE set (prevents screenshots)
- Display is off
- Permission issues

**Solutions**:
```bash
# Check if display is on
adb shell dumpsys power | grep "Display Power"

# Wake device
adb shell input keyevent KEYCODE_WAKEUP

# Check app permissions
# Some banking/DRM apps prevent screenshots
```

### MCP Server Issues

#### Server not appearing in Claude Code

**Solution**:
```bash
# Verify .mcp.json syntax
cat .mcp.json | jq .

# Check server starts manually
nix develop --command python mcp_server.py

# Restart Claude Code
```

#### "fastmcp module not found"

**Solution**:
```bash
# Ensure in Nix development environment
nix develop

# Verify Python path
which python
python -c "import fastmcp; print(fastmcp.__version__)"
```

### Debugging Tools

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Get device info
info = device_info(serial)
print(f"Device: {info['model']}")
print(f"Screen: {info['screen_width']}x{info['screen_height']}")
print(f"Current app: {info['current_app']}")

# Check popup watcher status
history = popup_history(serial)
print(f"Watcher active: {history['watcher_active']}")
print(f"Patterns configured: {history['pattern_count']}")

# Check screen detection
screen = detect_screen(serial)
print(f"Current screen: {screen['screen_id']}")
print(f"Confidence: {screen['confidence']:.2f}")
print(f"Detection time: {screen['detection_time_ms']:.1f}ms")

# View navigation statistics
nav_stats = get_navigation_stats(serial)
print(f"Success rate: {nav_stats['success_rate']:.1%}")
```

---

## Additional Resources

- **Project Repository**: `/home/aidev/phone-farm-tools/uiagent`
- **Signature Definitions**: `signatures/instagram.py`, `signatures/android_system.py`
- **Navigation Graph**: `navigation/graph.py`
- **Default Popup Patterns**: `popup_patterns.json`
- **FastMCP Documentation**: https://github.com/jlowin/fastmcp

## Version Information

- **MCP Server Version**: 1.0
- **FastMCP Version**: 0.2+
- **Python Version**: 3.11+
- **uiautomator2 Version**: 3.0+

---

**Last Updated**: December 2025
