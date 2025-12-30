#!/usr/bin/env python3
"""
UIAgent MCP Server - Android UI Automation via Model Context Protocol

Provides Claude Code with direct access to Android devices through uiautomator2.
The key differentiator is the `run_script` tool which allows Claude to execute
complete Python automation scripts in a single call (vs individual tap/swipe commands).

Usage:
    # Start the MCP server
    python mcp_server.py

    # Or add to Claude Code CLI
    claude mcp add uiagent --transport stdio -- python /path/to/mcp_server.py
"""

import asyncio
import io
import json
import logging
import os
import re
import threading
import time as time_module
from collections import deque
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.utilities.types import Image as MCPImage
from pydantic import BaseModel, Field

# Import existing UIAgent components
from driver.android import AndroidDriver
from model import DeviceInfo, Node, ShellResponse
from provider import AndroidProvider
from utils.interactive_executor import execute_interactive_code

# Import screen detection and navigation system
from navigation.detector import ScreenDetector
from navigation.navigator import ScreenNavigator
from navigation.search import search_for_keyword as _search_for_keyword, SearchResultType
from signatures.base import get_registry, get_signatures_for_app

# Import signature modules to auto-register them
import signatures.instagram  # noqa: F401
import signatures.android_system  # noqa: F401

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="UIAgent Android Automation",
    instructions="Control Android devices with Python scripts via uiautomator2. Use list_devices() first, then run_script() for complex automation."
)

# ============================================================================
# Global State Management
# ============================================================================

_provider: Optional[AndroidProvider] = None
_drivers: Dict[str, AndroidDriver] = {}
_screen_detectors: Dict[str, ScreenDetector] = {}  # serial -> ScreenDetector
_screen_navigators: Dict[str, ScreenNavigator] = {}  # serial -> ScreenNavigator

# Popup Management State (per-device)
_popup_patterns: Dict[str, List[Dict[str, str]]] = {}  # serial -> [{name, detect_xpath, dismiss_xpath}]
_popup_history: Dict[str, deque] = {}  # serial -> deque of dismissed popup records
_popup_threads: Dict[str, threading.Thread] = {}  # serial -> watcher thread
_popup_enabled: Dict[str, threading.Event] = {}  # serial -> stop event
_popup_lock = threading.Lock()  # Thread safety for popup state
MAX_POPUP_HISTORY = 100  # Ring buffer size per device
_default_patterns_loaded = False  # Track if we've loaded default patterns

# Path to default popup patterns config
POPUP_PATTERNS_FILE = Path(__file__).parent / "popup_patterns.json"


def _load_default_patterns() -> List[Dict[str, str]]:
    """Load default popup patterns from config file."""
    if not POPUP_PATTERNS_FILE.exists():
        logger.warning(f"Popup patterns file not found: {POPUP_PATTERNS_FILE}")
        return []

    try:
        with open(POPUP_PATTERNS_FILE, "r") as f:
            config = json.load(f)
            patterns = config.get("patterns", [])
            logger.info(f"Loaded {len(patterns)} default popup patterns")
            return patterns
    except Exception as e:
        logger.error(f"Failed to load popup patterns: {e}")
        return []


def _auto_setup_popup_watcher(serial: str):
    """Auto-configure and enable popup watcher for a device on first access."""
    global _default_patterns_loaded

    with _popup_lock:
        # Skip if already set up for this device
        if serial in _popup_patterns and len(_popup_patterns[serial]) > 0:
            return

        # Load default patterns if not already loaded
        if not _default_patterns_loaded:
            default_patterns = _load_default_patterns()
            _default_patterns_loaded = True
        else:
            # Use cached patterns structure - just copy for new device
            # Find any existing device's patterns to copy
            for existing_serial, patterns in _popup_patterns.items():
                if patterns:
                    default_patterns = patterns.copy()
                    break
            else:
                default_patterns = _load_default_patterns()

        if not default_patterns:
            return

        # Set up patterns for this device
        _popup_patterns[serial] = default_patterns.copy()
        logger.info(f"[{serial}] Auto-configured {len(default_patterns)} popup patterns")

    # Start watcher thread (outside lock to avoid deadlock)
    _start_popup_watcher(serial)


def _start_popup_watcher(serial: str):
    """Start popup watcher for a device if not already running."""
    with _popup_lock:
        if serial in _popup_threads and _popup_threads[serial].is_alive():
            return  # Already running

        pattern_count = len(_popup_patterns.get(serial, []))
        if pattern_count == 0:
            return  # No patterns to watch

        stop_event = threading.Event()
        _popup_enabled[serial] = stop_event

        thread = threading.Thread(
            target=_popup_watcher_loop,
            args=(serial, stop_event),
            daemon=True,
            name=f"popup-watcher-{serial}"
        )
        thread.start()
        _popup_threads[serial] = thread
        logger.info(f"[{serial}] Auto-started popup watcher with {pattern_count} patterns")


def get_provider() -> AndroidProvider:
    """Get or create the AndroidProvider singleton."""
    global _provider
    if _provider is None:
        _provider = AndroidProvider()
    return _provider


@lru_cache(maxsize=16)
def get_driver(serial: str) -> AndroidDriver:
    """Get or create an AndroidDriver for the given device serial."""
    provider = get_provider()
    devices = provider.list_devices()

    device = next((d for d in devices if d.serial == serial), None)
    if not device:
        available = [d.serial for d in devices]
        raise ValueError(f"Device not found: {serial}. Available: {available}")

    if not device.enabled:
        raise ValueError(f"Device not available: {serial} (status: {device.status})")

    driver = provider.get_device_driver(serial)

    # Auto-setup popup watcher on first device access
    _auto_setup_popup_watcher(serial)

    return driver


def get_screen_detector(serial: str) -> ScreenDetector:
    """Get or create a ScreenDetector for the given device serial."""
    global _screen_detectors
    if serial not in _screen_detectors:
        driver = get_driver(serial)
        _screen_detectors[serial] = ScreenDetector(driver.ud)
    return _screen_detectors[serial]


def get_screen_navigator(serial: str, app_id: str = "instagram") -> ScreenNavigator:
    """Get or create a ScreenNavigator for the given device serial."""
    global _screen_navigators
    if serial not in _screen_navigators:
        driver = get_driver(serial)
        detector = get_screen_detector(serial)
        _screen_navigators[serial] = ScreenNavigator(driver.ud, detector, app_id=app_id)
    return _screen_navigators[serial]


# ============================================================================
# Response Models
# ============================================================================

class ScriptResult(BaseModel):
    """Result of Python script execution."""
    stdout: str = Field(description="Captured stdout output")
    stderr: str = Field(description="Captured stderr output")
    result: Optional[str] = Field(description="repr() of final expression result")
    error: Optional[str] = Field(description="Exception traceback if execution failed")
    debug_log: Optional[str] = Field(default=None, description="Line-by-line execution trace")


class TapResult(BaseModel):
    """Result of tap operation."""
    success: bool = Field(description="Whether tap was executed")
    x: int = Field(description="X coordinate tapped")
    y: int = Field(description="Y coordinate tapped")


class DeviceInfoDetailed(BaseModel):
    """Detailed device information."""
    serial: str
    model: str
    name: str
    screen_width: int
    screen_height: int
    current_app: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Currently running app (package, activity, pid)"
    )


class HierarchyResult(BaseModel):
    """UI hierarchy result."""
    xml: str = Field(description="Raw XML hierarchy dump")
    tree: Dict[str, Any] = Field(description="Parsed UI element tree")
    screen_width: int
    screen_height: int


# ============================================================================
# TOOL 1: list_devices
# ============================================================================

@mcp.tool()
def list_devices() -> List[Dict[str, Any]]:
    """
    List all connected Android devices.

    Use this to discover available devices before performing automation.
    The 'serial' field is required for all device-specific operations.

    Returns:
        List of device info objects with serial, model, name, status, enabled

    Example:
        devices = list_devices()
        serial = devices[0]["serial"]  # Use this serial for other tools
    """
    provider = get_provider()
    devices = provider.list_devices()
    return [d.model_dump() for d in devices]


# ============================================================================
# TOOL 2: screenshot
# ============================================================================

@mcp.tool()
def screenshot(serial: str) -> MCPImage:
    """
    Capture a screenshot from the Android device.

    Returns an image that Claude can analyze visually (multimodal).
    Use this to understand current screen state before automation.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        JPEG image of the device screen

    Example:
        # First get a device serial
        devices = list_devices()
        serial = devices[0]["serial"]

        # Then capture screenshot
        image = screenshot(serial)
        # Claude can now analyze the image visually
    """
    driver = get_driver(serial)

    # Capture screenshot (0 = main display)
    pil_img = driver.screenshot(0)

    # Resize if needed to avoid MCP transport limits (4MB) and Claude auto-resize
    # Target: ≤1568px on long edge (Claude's auto-resize threshold)
    max_dimension = 1568
    if max(pil_img.size) > max_dimension:
        pil_img.thumbnail((max_dimension, max_dimension))
        logger.info(f"Resized screenshot to {pil_img.size}")

    # Convert to JPEG bytes with reasonable compression
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=80)

    # Return FastMCP Image object with correct MIME type
    return MCPImage(data=buf.getvalue(), format="jpeg")


# ============================================================================
# TOOL 3: run_script (CORE TOOL)
# ============================================================================

@mcp.tool()
async def run_script(
    serial: str,
    code: str,
    timeout_seconds: int = 60
) -> ScriptResult:
    """
    Execute Python automation code with full uiautomator2 access.

    THIS IS THE MAIN AUTOMATION TOOL. Use this for complex automation tasks.
    Much more efficient than individual tap/swipe commands.

    Available globals in execution context:
        d: uiautomator2.Device - The connected device instance
        u2: uiautomator2 module - For constants and utilities
        time: time module - For delays (use sparingly)
        json: json module - For data handling
        os, sys: Standard library modules

    Args:
        serial: Device serial number from list_devices()
        code: Python code to execute
        timeout_seconds: Max execution time (default: 60s, max: 300s)

    Returns:
        ScriptResult with stdout, stderr, result, and optional error

    Example - Click login and wait for home:
        result = run_script(serial, '''
            d.xpath("//button[@resource-id='com.app:id/login']").click()
            d.xpath("//view[@resource-id='com.app:id/home']").wait(timeout=10)
            print("Login successful")
        ''')

    Example - Scroll through feed:
        result = run_script(serial, '''
            for i in range(5):
                d.swipe(0.5, 0.8, 0.5, 0.3)
                time.sleep(1)
            print("Scrolled 5 times")
        ''')

    Example - Conditional logic:
        result = run_script(serial, '''
            if d.xpath("//button[@text='Accept']").exists(timeout=2):
                d.xpath("//button[@text='Accept']").click()
                print("Dismissed popup")
            d.xpath("//button[@text='Login']").click()
        ''')
    """
    driver = get_driver(serial)

    # Cap timeout at 5 minutes
    effective_timeout = min(timeout_seconds, 300)

    try:
        # Run blocking code in executor with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                execute_interactive_code,
                code,
                driver.ud,  # uiautomator2 device instance
                False       # enable_tracing
            ),
            timeout=effective_timeout
        )

        return ScriptResult(
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            result=result.get("result"),
            error=result.get("execution_error"),
            debug_log=result.get("debug_log")
        )

    except asyncio.TimeoutError:
        return ScriptResult(
            stdout="",
            stderr="",
            result=None,
            error=f"Script execution timed out after {effective_timeout}s. "
                  f"Consider breaking into smaller steps or increasing timeout.",
            debug_log=None
        )
    except Exception as e:
        return ScriptResult(
            stdout="",
            stderr=str(e),
            result=None,
            error=f"Execution error: {str(e)}",
            debug_log=None
        )


# ============================================================================
# TOOL 4: ui_hierarchy
# ============================================================================

@mcp.tool()
def ui_hierarchy(serial: str) -> HierarchyResult:
    """
    Get the UI element hierarchy from the device screen.

    WARNING: Returns LARGE data (10k+ lines for complex screens).
    Use sparingly - prefer screenshot() for initial analysis.

    Use this when you need to:
        - Find element resource-ids or content-desc values
        - Build xpath selectors for automation
        - Locate clickable elements programmatically

    Args:
        serial: Device serial number from list_devices()

    Returns:
        HierarchyResult with XML dump and parsed tree

    Key properties to look for in elements:
        - resource-id: Most stable selector (e.g., 'com.app:id/login_btn')
        - content-desc: Accessibility label
        - text: Visible text (least stable)
        - clickable: Whether element accepts clicks
        - bounds: Element position [x1,y1][x2,y2]
    """
    driver = get_driver(serial)

    xml_data, tree = driver.dump_hierarchy()
    width, height = driver.window_size()

    return HierarchyResult(
        xml=xml_data,
        tree=tree.model_dump(),
        screen_width=width,
        screen_height=height
    )


# ============================================================================
# TOOL 5: tap
# ============================================================================

@mcp.tool()
def tap(serial: str, x: int, y: int) -> TapResult:
    """
    Tap at specific screen coordinates.

    Quick helper for simple taps when you know exact pixel coordinates.
    For complex automation with element selection, prefer run_script().

    Args:
        serial: Device serial number from list_devices()
        x: X coordinate in pixels (0 = left edge)
        y: Y coordinate in pixels (0 = top edge)

    Returns:
        TapResult confirming the tap location

    Example:
        # Get screen size first if needed
        info = device_info(serial)
        center_x = info["screen_width"] // 2
        center_y = info["screen_height"] // 2
        tap(serial, center_x, center_y)
    """
    try:
        driver = get_driver(serial)
        driver.tap(x, y)
        return TapResult(success=True, x=x, y=y)
    except Exception as e:
        logger.error(f"Tap failed: {e}")
        raise ValueError(f"Tap failed at ({x}, {y}): {str(e)}")


# ============================================================================
# TOOL 6: shell
# ============================================================================

@mcp.tool()
def shell(serial: str, command: str) -> Dict[str, Any]:
    """
    Execute a shell command on the Android device via ADB.

    Use this for low-level device operations:
        - Get system properties: getprop ro.build.version.release
        - List files: ls /sdcard/
        - Check processes: ps | grep com.app
        - Manage apps: pm list packages

    Args:
        serial: Device serial number from list_devices()
        command: Shell command string

    Returns:
        Dict with 'output' and 'error' fields

    Examples:
        # Get Android version
        shell(serial, "getprop ro.build.version.release")

        # List installed packages
        shell(serial, "pm list packages | grep instagram")

        # Check current activity
        shell(serial, "dumpsys activity activities | grep mResumedActivity")
    """
    driver = get_driver(serial)
    result: ShellResponse = driver.shell(command)
    return result.model_dump()


# ============================================================================
# TOOL 7: device_info
# ============================================================================

@mcp.tool()
def device_info(serial: str) -> Dict[str, Any]:
    """
    Get detailed information about a device in one call.

    Combines device metadata, screen size, and current app info.
    More efficient than calling multiple separate tools.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        DeviceInfoDetailed with serial, model, screen dimensions, and current app
    """
    driver = get_driver(serial)
    provider = get_provider()

    # Get screen dimensions
    width, height = driver.window_size()

    # Get current app info
    current_app = None
    try:
        app_info = driver.app_current()
        current_app = {
            "package": app_info.package,
            "activity": app_info.activity,
            "pid": app_info.pid
        }
    except Exception as e:
        logger.warning(f"Could not get current app info: {e}")

    # Get device metadata
    devices = provider.list_devices()
    device = next((d for d in devices if d.serial == serial), None)

    result = DeviceInfoDetailed(
        serial=serial,
        model=device.model if device else "",
        name=device.name if device else "",
        screen_width=width,
        screen_height=height,
        current_app=current_app
    )

    return result.model_dump()


# ============================================================================
# TOOL 8: get_elements
# ============================================================================

@mcp.tool()
def get_elements(
    serial: str,
    filter: str = "interactive",
    max_elements: int = 50
) -> List[Dict[str, Any]]:
    """
    Get filtered UI elements in a Claude-consumable format.

    MUCH more efficient than ui_hierarchy for navigation tasks.
    Returns only the essential info needed to interact with elements.

    Args:
        serial: Device serial number from list_devices()
        filter: Element filter mode:
            - "interactive": Clickable, checkable, or focusable elements (default)
            - "text": Elements with visible text or content description
            - "inputs": Editable text fields
            - "all": All elements (warning: can be large)
            - Custom xpath: e.g., "//*[@resource-id='com.app:id/btn']"
        max_elements: Maximum elements to return (default: 50)

    Returns:
        List of element dicts with:
            - index: Position in results (use for reference)
            - selector: XPath selector to target this element
            - text: Visible text (if any)
            - desc: Content description / accessibility label (if any)
            - resource_id: Resource ID (if any)
            - type: Simplified element type (Button, TextView, EditText, etc.)
            - bounds: [x1, y1, x2, y2] screen coordinates
            - clickable: Whether element is clickable
            - center: [x, y] center point for tapping

    Example workflow:
        # 1. Screenshot to see the screen
        screenshot(serial)

        # 2. Get interactive elements
        elements = get_elements(serial, filter="interactive")
        # Returns: [{"index": 0, "selector": "...", "text": "Login", ...}, ...]

        # 3. Use selector in run_script
        run_script(serial, '''
            d.xpath("//android.widget.Button[@text='Login']").click()
        ''')

    Example - Find specific elements:
        # Get all text inputs
        inputs = get_elements(serial, filter="inputs")

        # Custom xpath - find by partial resource-id
        buttons = get_elements(serial, filter="//*[contains(@resource-id, 'btn')]")
    """
    driver = get_driver(serial)
    d = driver.ud  # uiautomator2 device

    # Build xpath based on filter
    if filter == "interactive":
        # Clickable OR checkable OR focusable elements
        xpath = "//*[@clickable='true' or @checkable='true' or @long-clickable='true']"
    elif filter == "text":
        # Elements with text or content-desc
        xpath = "//*[@text!='' or @content-desc!='']"
    elif filter == "inputs":
        # Editable text fields
        xpath = "//*[@class='android.widget.EditText' or contains(@class, 'EditText')]"
    elif filter == "all":
        xpath = "//*"
    elif filter.startswith("/"):
        # Custom xpath
        xpath = filter
    else:
        raise ValueError(f"Unknown filter: {filter}. Use 'interactive', 'text', 'inputs', 'all', or a custom xpath.")

    # Query elements using uiautomator2's xpath
    elements = []
    try:
        matches = d.xpath(xpath).all()

        for i, el in enumerate(matches[:max_elements]):
            # Get element info
            info = el.info

            # Parse bounds dict {left, top, right, bottom} -> [x1, y1, x2, y2]
            bounds_dict = info.get("bounds", {})
            bounds = None
            center = None
            if bounds_dict and isinstance(bounds_dict, dict):
                left = bounds_dict.get("left", 0)
                top = bounds_dict.get("top", 0)
                right = bounds_dict.get("right", 0)
                bottom = bounds_dict.get("bottom", 0)
                bounds = [left, top, right, bottom]
                center = [(left + right) // 2, (top + bottom) // 2]

            # Simplify class name: "android.widget.Button" -> "Button"
            class_name = info.get("className", "")
            simple_type = class_name.split(".")[-1] if class_name else "Unknown"

            # Build a useful selector for this element
            resource_id = info.get("resourceId", "")
            text = info.get("text", "")
            desc = info.get("contentDescription", "")

            # Prefer resource-id, then text, then content-desc for selector
            if resource_id:
                selector = f"//*[@resource-id='{resource_id}']"
            elif text:
                # Escape quotes in text for xpath
                safe_text = text.replace("'", "\\'")
                selector = f"//*[@text='{safe_text}']"
            elif desc:
                safe_desc = desc.replace("'", "\\'")
                selector = f"//*[@content-desc='{safe_desc}']"
            else:
                # Fall back to class with index suggestion
                selector = f"//{class_name}  # Use tap({center[0]}, {center[1]}) for coords" if center else f"//{class_name}"

            elements.append({
                "index": i,
                "selector": selector,
                "text": text or None,
                "desc": desc or None,
                "resource_id": resource_id.split("/")[-1] if resource_id else None,  # Just the ID part
                "type": simple_type,
                "bounds": bounds,
                "clickable": info.get("clickable", False),
                "center": center
            })

    except Exception as e:
        logger.error(f"get_elements failed: {e}")
        raise ValueError(f"Failed to query elements with xpath '{xpath}': {str(e)}")

    return elements


# ============================================================================
# TOOL 9: wait_for (HIGH VALUE)
# ============================================================================

@mcp.tool()
def wait_for(
    serial: str,
    text: Optional[str] = None,
    text_gone: Optional[str] = None,
    xpath: Optional[str] = None,
    timeout: float = 10.0
) -> Dict[str, Any]:
    """
    Wait for a condition on the device screen.

    Essential for async UI operations - wait for elements to appear/disappear
    before proceeding with automation.

    Args:
        serial: Device serial number from list_devices()
        text: Wait for this text to appear on screen
        text_gone: Wait for this text to disappear from screen
        xpath: Wait for element matching this xpath to exist
        timeout: Max wait time in seconds (default: 10)

    Returns:
        Dict with:
            - found: Whether condition was met
            - elapsed: Time waited in seconds
            - message: Description of result

    Examples:
        # Wait for loading to finish
        wait_for(serial, text_gone="Loading...")

        # Wait for login button to appear
        wait_for(serial, text="Login", timeout=15)

        # Wait for specific element
        wait_for(serial, xpath="//*[@resource-id='com.app:id/home_feed']")
    """
    import time as time_module
    driver = get_driver(serial)
    d = driver.ud

    start = time_module.time()

    try:
        if text:
            # Wait for text to appear
            result = d(text=text).wait(timeout=timeout)
            elapsed = time_module.time() - start
            return {
                "found": result,
                "elapsed": round(elapsed, 2),
                "message": f"Text '{text}' {'found' if result else 'not found'} after {elapsed:.1f}s"
            }

        elif text_gone:
            # Wait for text to disappear
            result = d(text=text_gone).wait_gone(timeout=timeout)
            elapsed = time_module.time() - start
            return {
                "found": result,
                "elapsed": round(elapsed, 2),
                "message": f"Text '{text_gone}' {'disappeared' if result else 'still present'} after {elapsed:.1f}s"
            }

        elif xpath:
            # Wait for xpath element to exist
            result = d.xpath(xpath).wait(timeout=timeout)
            elapsed = time_module.time() - start
            return {
                "found": result,
                "elapsed": round(elapsed, 2),
                "message": f"Element '{xpath}' {'found' if result else 'not found'} after {elapsed:.1f}s"
            }

        else:
            # Just wait for specified time
            time_module.sleep(timeout)
            return {
                "found": True,
                "elapsed": timeout,
                "message": f"Waited {timeout}s"
            }

    except Exception as e:
        elapsed = time_module.time() - start
        return {
            "found": False,
            "elapsed": round(elapsed, 2),
            "message": f"Wait failed: {str(e)}"
        }


# ============================================================================
# TOOL 10: swipe (HIGH VALUE)
# ============================================================================

@mcp.tool()
def swipe(
    serial: str,
    direction: Optional[str] = None,
    start_x: Optional[float] = None,
    start_y: Optional[float] = None,
    end_x: Optional[float] = None,
    end_y: Optional[float] = None,
    duration: float = 0.3
) -> Dict[str, Any]:
    """
    Perform a swipe gesture on the device.

    Can use named directions OR explicit coordinates.
    Coordinates can be absolute pixels or relative (0.0-1.0).

    Args:
        serial: Device serial number from list_devices()
        direction: Named direction - "up", "down", "left", "right"
        start_x: Starting X coordinate (pixels or 0.0-1.0 relative)
        start_y: Starting Y coordinate (pixels or 0.0-1.0 relative)
        end_x: Ending X coordinate (pixels or 0.0-1.0 relative)
        end_y: Ending Y coordinate (pixels or 0.0-1.0 relative)
        duration: Swipe duration in seconds (default: 0.3)

    Returns:
        Dict confirming the swipe performed

    Examples:
        # Scroll down (swipe up)
        swipe(serial, direction="up")

        # Scroll up (swipe down)
        swipe(serial, direction="down")

        # Swipe left to go to next item
        swipe(serial, direction="left")

        # Custom swipe with relative coords (center to top)
        swipe(serial, start_x=0.5, start_y=0.7, end_x=0.5, end_y=0.3)
    """
    driver = get_driver(serial)
    d = driver.ud

    if direction:
        # Named direction swipes
        direction = direction.lower()
        if direction == "up":
            # Swipe up = scroll down (finger moves up)
            d.swipe(0.5, 0.7, 0.5, 0.3, duration=duration)
        elif direction == "down":
            # Swipe down = scroll up (finger moves down)
            d.swipe(0.5, 0.3, 0.5, 0.7, duration=duration)
        elif direction == "left":
            d.swipe(0.8, 0.5, 0.2, 0.5, duration=duration)
        elif direction == "right":
            d.swipe(0.2, 0.5, 0.8, 0.5, duration=duration)
        else:
            raise ValueError(f"Unknown direction: {direction}. Use 'up', 'down', 'left', 'right'.")

        return {
            "success": True,
            "direction": direction,
            "duration": duration
        }

    elif all(v is not None for v in [start_x, start_y, end_x, end_y]):
        # Custom coordinates
        d.swipe(start_x, start_y, end_x, end_y, duration=duration)
        return {
            "success": True,
            "start": [start_x, start_y],
            "end": [end_x, end_y],
            "duration": duration
        }

    else:
        raise ValueError("Provide either 'direction' OR all of (start_x, start_y, end_x, end_y)")


# ============================================================================
# TOOL 11: app_launch (MEDIUM VALUE)
# ============================================================================

@mcp.tool()
def app_launch(
    serial: str,
    package: str,
    activity: Optional[str] = None,
    wait: bool = True
) -> Dict[str, Any]:
    """
    Launch an app by package name.

    Args:
        serial: Device serial number from list_devices()
        package: App package name (e.g., "com.instagram.android")
        activity: Specific activity to launch (optional)
        wait: Wait for app to launch (default: True)

    Returns:
        Dict with launch status and current app info

    Examples:
        # Launch Instagram
        app_launch(serial, package="com.instagram.android")

        # Launch Chrome
        app_launch(serial, package="com.android.chrome")

        # Launch with specific activity
        app_launch(serial, package="com.app", activity=".MainActivity")
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        if activity:
            d.app_start(package, activity=activity, wait=wait)
        else:
            d.app_start(package, wait=wait)

        # Get current app info to confirm
        current = d.app_current()

        return {
            "success": True,
            "package": package,
            "current_package": current.get("package", ""),
            "current_activity": current.get("activity", "")
        }
    except Exception as e:
        return {
            "success": False,
            "package": package,
            "error": str(e)
        }


# ============================================================================
# TOOL 12: app_terminate (MEDIUM VALUE)
# ============================================================================

@mcp.tool()
def app_terminate(serial: str, package: str) -> Dict[str, Any]:
    """
    Stop/kill an app by package name.

    Args:
        serial: Device serial number from list_devices()
        package: App package name to terminate

    Returns:
        Dict confirming termination

    Examples:
        # Stop Instagram
        app_terminate(serial, package="com.instagram.android")
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        d.app_stop(package)
        return {
            "success": True,
            "package": package,
            "message": f"Terminated {package}"
        }
    except Exception as e:
        return {
            "success": False,
            "package": package,
            "error": str(e)
        }


# ============================================================================
# TOOL 13: app_list (LOW VALUE)
# ============================================================================

@mcp.tool()
def app_list(
    serial: str,
    filter: str = "third_party"
) -> List[Dict[str, Any]]:
    """
    List installed apps on the device.

    Args:
        serial: Device serial number from list_devices()
        filter: Which apps to list:
            - "third_party": User-installed apps only (default)
            - "system": System apps only
            - "all": All apps

    Returns:
        List of app info dicts with package name

    Example:
        # Get user-installed apps
        apps = app_list(serial)

        # Get all apps including system
        apps = app_list(serial, filter="all")
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        # uiautomator2 app_list takes pm list flags:
        # -3 = third party only, -s = system only, None = all
        if filter == "third_party":
            packages = d.app_list("-3")
        elif filter == "system":
            packages = d.app_list("-s")
        else:  # "all"
            packages = d.app_list()

        return [{"package": pkg} for pkg in sorted(packages)]

    except Exception as e:
        logger.error(f"app_list failed: {e}")
        raise ValueError(f"Failed to list apps: {str(e)}")


# ============================================================================
# TOOL 14: file_push (LOW VALUE)
# ============================================================================

@mcp.tool()
def file_push(
    serial: str,
    local_path: str,
    remote_path: str
) -> Dict[str, Any]:
    """
    Push a file from local machine to the Android device.

    Args:
        serial: Device serial number from list_devices()
        local_path: Path to local file
        remote_path: Destination path on device (e.g., "/sdcard/Download/file.txt")

    Returns:
        Dict with transfer status

    Example:
        file_push(serial, "/tmp/config.json", "/sdcard/Download/config.json")
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        d.push(local_path, remote_path)
        return {
            "success": True,
            "local": local_path,
            "remote": remote_path,
            "message": f"Pushed {local_path} to {remote_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "local": local_path,
            "remote": remote_path,
            "error": str(e)
        }


# ============================================================================
# TOOL 15: file_pull (LOW VALUE)
# ============================================================================

@mcp.tool()
def file_pull(
    serial: str,
    remote_path: str,
    local_path: str
) -> Dict[str, Any]:
    """
    Pull a file from the Android device to local machine.

    Args:
        serial: Device serial number from list_devices()
        remote_path: Path to file on device
        local_path: Destination path on local machine

    Returns:
        Dict with transfer status

    Example:
        file_pull(serial, "/sdcard/screenshot.png", "/tmp/screenshot.png")
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        d.pull(remote_path, local_path)
        return {
            "success": True,
            "remote": remote_path,
            "local": local_path,
            "message": f"Pulled {remote_path} to {local_path}"
        }
    except Exception as e:
        return {
            "success": False,
            "remote": remote_path,
            "local": local_path,
            "error": str(e)
        }


# ============================================================================
# TOOL 16: get_orientation (LOW VALUE)
# ============================================================================

@mcp.tool()
def get_orientation(serial: str) -> Dict[str, Any]:
    """
    Get the current screen orientation.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with orientation info:
            - orientation: "portrait", "landscape", "portrait-reverse", "landscape-reverse"
            - rotation: 0, 90, 180, or 270 degrees
    """
    driver = get_driver(serial)
    d = driver.ud

    try:
        # Get rotation (0, 1, 2, 3) -> (0°, 90°, 180°, 270°)
        rotation = d.info.get("displayRotation", 0)

        orientations = {
            0: ("portrait", 0),
            1: ("landscape", 90),
            2: ("portrait-reverse", 180),
            3: ("landscape-reverse", 270)
        }

        name, degrees = orientations.get(rotation, ("unknown", rotation * 90))

        return {
            "orientation": name,
            "rotation": degrees,
            "raw": rotation
        }
    except Exception as e:
        return {
            "orientation": "unknown",
            "error": str(e)
        }


# ============================================================================
# TOOL 17: set_orientation (LOW VALUE)
# ============================================================================

@mcp.tool()
def set_orientation(
    serial: str,
    orientation: str
) -> Dict[str, Any]:
    """
    Set the screen orientation.

    Args:
        serial: Device serial number from list_devices()
        orientation: Target orientation:
            - "natural" or "portrait": Default portrait
            - "left" or "landscape": Rotate left (landscape)
            - "right": Rotate right (landscape)
            - "upsidedown": Upside down portrait

    Returns:
        Dict confirming orientation change

    Example:
        # Force landscape
        set_orientation(serial, "landscape")

        # Back to portrait
        set_orientation(serial, "portrait")
    """
    driver = get_driver(serial)
    d = driver.ud

    orientation = orientation.lower()

    orientation_map = {
        "natural": "natural",
        "portrait": "natural",
        "left": "left",
        "landscape": "left",
        "right": "right",
        "upsidedown": "upsidedown"
    }

    if orientation not in orientation_map:
        raise ValueError(f"Unknown orientation: {orientation}. Use: natural, portrait, landscape, left, right, upsidedown")

    try:
        target = orientation_map[orientation]
        d.set_orientation(target)

        return {
            "success": True,
            "orientation": target,
            "message": f"Set orientation to {target}"
        }
    except Exception as e:
        return {
            "success": False,
            "orientation": orientation,
            "error": str(e)
        }


# ============================================================================
# POPUP MANAGEMENT SYSTEM
# ============================================================================

def _popup_watcher_loop(serial: str, stop_event: threading.Event):
    """
    Background thread that continuously checks for and dismisses known popups.
    Also captures Android toasts using native toast API.
    Records all events to history for Claude visibility.
    """
    logger.info(f"[{serial}] Popup watcher started")
    _last_toast_text = None  # Track last toast to avoid duplicates

    while not stop_event.is_set():
        try:
            with _popup_lock:
                patterns = _popup_patterns.get(serial, [])

            driver = get_driver(serial)
            d = driver.ud

            # ============================================================
            # NATIVE TOAST CAPTURE - uses AccessibilityService via d.last_toast
            # Captures real Android toasts (3500ms window for long, 2000ms for short)
            # Uses non-blocking d.last_toast property (faster than get_message)
            # ============================================================
            try:
                # Use non-blocking last_toast property instead of get_message()
                toast_msg = getattr(d, 'last_toast', None)
                if toast_msg and toast_msg != _last_toast_text:
                    _last_toast_text = toast_msg
                    logger.info(f"[{serial}] Native toast captured: {toast_msg}")

                    # Record to history
                    record = {
                        "name": "native_toast",
                        "type": "toast",
                        "timestamp": datetime.now().isoformat(),
                        "captured_text": toast_msg,
                        "message": f"Toast: {toast_msg}"
                    }

                    with _popup_lock:
                        if serial not in _popup_history:
                            _popup_history[serial] = deque(maxlen=MAX_POPUP_HISTORY)
                        _popup_history[serial].append(record)

                    # Reset cache to catch next toast
                    d.toast.reset()
            except Exception as toast_err:
                logger.debug(f"[{serial}] Toast capture error: {toast_err}")

            if not patterns:
                stop_event.wait(0.5)  # Sleep but wake on stop
                continue

            # ============================================================
            # XPATH-BASED POPUP DETECTION - for dialogs, prompts, etc.
            # ============================================================
            for pattern in patterns:
                if stop_event.is_set():
                    break

                name = pattern.get("name", "unnamed")
                detect_xpath = pattern.get("detect_xpath", "")
                dismiss_xpath = pattern.get("dismiss_xpath", "")

                if not detect_xpath:
                    continue

                try:
                    # Check if popup/toast is present (quick check, no wait)
                    if d.xpath(detect_xpath).exists:
                        pattern_type = pattern.get("type", "popup")

                        if pattern_type == "toast":
                            # Toast handling: capture text, don't dismiss
                            logger.info(f"[{serial}] Toast detected: {name}")

                            # Try to capture toast text content
                            captured_text = None
                            try:
                                el = d.xpath(detect_xpath).get()
                                if el:
                                    # Try multiple ways to get text
                                    captured_text = (
                                        el.info.get("text") or
                                        el.info.get("contentDescription") or
                                        el.text
                                    )
                            except Exception:
                                pass

                            # Record to history
                            record = {
                                "name": name,
                                "type": "toast",
                                "timestamp": datetime.now().isoformat(),
                                "detect_xpath": detect_xpath,
                                "captured_text": captured_text,
                                "message": f"Toast '{name}': {captured_text}" if captured_text else f"Toast '{name}' detected"
                            }

                            with _popup_lock:
                                if serial not in _popup_history:
                                    _popup_history[serial] = deque(maxlen=MAX_POPUP_HISTORY)
                                _popup_history[serial].append(record)

                            logger.info(f"[{serial}] Toast captured: {name} = {captured_text}")

                        else:
                            # Popup handling: detect and dismiss
                            logger.info(f"[{serial}] Popup detected: {name}")

                            # Try to dismiss and verify it worked
                            dismissed = False
                            verified = False
                            if dismiss_xpath:
                                try:
                                    if d.xpath(dismiss_xpath).exists:
                                        d.xpath(dismiss_xpath).click()
                                        dismissed = True
                                        # Verify popup is gone (wait up to 1.5s)
                                        verified = d.xpath(detect_xpath).wait_gone(timeout=1.5)
                                except Exception as click_err:
                                    logger.warning(f"[{serial}] Failed to click dismiss for {name}: {click_err}")

                            # Record to history with verification status
                            if dismissed and verified:
                                message = f"Auto-dismissed '{name}' ✓"
                            elif dismissed:
                                message = f"Clicked dismiss for '{name}' but popup still visible"
                            else:
                                message = f"Detected '{name}' but dismiss button not found"

                            record = {
                                "name": name,
                                "type": "popup",
                                "timestamp": datetime.now().isoformat(),
                                "detect_xpath": detect_xpath,
                                "dismiss_xpath": dismiss_xpath,
                                "dismissed": dismissed,
                                "verified": verified,
                                "message": message
                            }

                            with _popup_lock:
                                if serial not in _popup_history:
                                    _popup_history[serial] = deque(maxlen=MAX_POPUP_HISTORY)
                                _popup_history[serial].append(record)

                            logger.info(f"[{serial}] Popup handled: {name} (dismissed={dismissed})")

                except Exception as e:
                    # Don't crash watcher on individual pattern errors
                    logger.debug(f"[{serial}] Pattern check error for {name}: {e}")

            # Check every 500ms (optimized for toast capture - 3500ms window)
            stop_event.wait(0.5)

        except Exception as e:
            logger.error(f"[{serial}] Popup watcher error: {e}")
            stop_event.wait(2.0)  # Back off on error

    logger.info(f"[{serial}] Popup watcher stopped")


# ============================================================================
# TOOL 18: popup_configure
# ============================================================================

@mcp.tool()
def popup_configure(
    serial: str,
    patterns: List[Dict[str, str]],
    append: bool = True
) -> Dict[str, Any]:
    """
    Configure popup patterns for automatic dismissal.

    Each pattern needs:
        - name: Human-readable identifier (e.g., "save_login_info")
        - detect_xpath: XPath to detect popup presence
        - dismiss_xpath: XPath for element to click to dismiss

    Args:
        serial: Device serial number from list_devices()
        patterns: List of pattern dicts with name, detect_xpath, dismiss_xpath
        append: If True, add to existing patterns. If False, replace all.

    Returns:
        Dict with configured pattern count

    Example:
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
    """
    with _popup_lock:
        if serial not in _popup_patterns or not append:
            _popup_patterns[serial] = []

        # Validate and add patterns
        added = 0
        for p in patterns:
            if "detect_xpath" not in p:
                continue

            pattern = {
                "name": p.get("name", f"pattern_{len(_popup_patterns[serial])}"),
                "detect_xpath": p["detect_xpath"],
                "dismiss_xpath": p.get("dismiss_xpath", "")
            }
            _popup_patterns[serial].append(pattern)
            added += 1

        total = len(_popup_patterns[serial])

    return {
        "success": True,
        "patterns_added": added,
        "total_patterns": total,
        "message": f"Configured {total} popup patterns for {serial}"
    }


# ============================================================================
# TOOL 19: popup_enable
# ============================================================================

@mcp.tool()
def popup_enable(serial: str) -> Dict[str, Any]:
    """
    Start automatic popup dismissal in background.

    Launches a background thread that continuously monitors for configured
    popup patterns and dismisses them automatically. All dismissals are
    recorded to history for later review via popup_history().

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with watcher status

    Example:
        # First configure patterns
        popup_configure(serial, [...])

        # Then enable auto-dismiss
        popup_enable(serial)

        # Now popups will be auto-dismissed in background
        # Check what was dismissed:
        popup_history(serial)
    """
    with _popup_lock:
        # Check if already running
        if serial in _popup_threads and _popup_threads[serial].is_alive():
            pattern_count = len(_popup_patterns.get(serial, []))
            return {
                "success": True,
                "status": "already_running",
                "pattern_count": pattern_count,
                "message": f"Popup watcher already running with {pattern_count} patterns"
            }

        # Check if any patterns configured
        pattern_count = len(_popup_patterns.get(serial, []))
        if pattern_count == 0:
            return {
                "success": False,
                "status": "no_patterns",
                "message": "No popup patterns configured. Use popup_configure() first."
            }

        # Create stop event and start thread
        stop_event = threading.Event()
        _popup_enabled[serial] = stop_event

        thread = threading.Thread(
            target=_popup_watcher_loop,
            args=(serial, stop_event),
            daemon=True,
            name=f"popup-watcher-{serial}"
        )
        thread.start()
        _popup_threads[serial] = thread

    return {
        "success": True,
        "status": "started",
        "pattern_count": pattern_count,
        "message": f"Popup watcher started with {pattern_count} patterns"
    }


# ============================================================================
# TOOL 20: popup_disable
# ============================================================================

@mcp.tool()
def popup_disable(serial: str) -> Dict[str, Any]:
    """
    Stop automatic popup dismissal.

    Stops the background watcher thread. Patterns are preserved and can
    be re-enabled with popup_enable(). History is also preserved.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with stop status
    """
    with _popup_lock:
        if serial not in _popup_enabled:
            return {
                "success": True,
                "status": "not_running",
                "message": "Popup watcher was not running"
            }

        # Signal stop
        _popup_enabled[serial].set()

        # Wait for thread to finish (with timeout)
        if serial in _popup_threads:
            thread = _popup_threads[serial]
            thread.join(timeout=3.0)

            if thread.is_alive():
                logger.warning(f"[{serial}] Popup watcher thread did not stop cleanly")

            del _popup_threads[serial]

        del _popup_enabled[serial]

    return {
        "success": True,
        "status": "stopped",
        "message": "Popup watcher stopped"
    }


# ============================================================================
# TOOL 21: popup_history
# ============================================================================

@mcp.tool()
def popup_history(
    serial: str,
    clear: bool = False,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get history of auto-dismissed popups.

    Use this to see what popups were handled while you weren't looking.
    Essential for understanding automation flow and debugging.

    Args:
        serial: Device serial number from list_devices()
        clear: If True, clear history after returning
        limit: Max records to return (default: 20, newest first)

    Returns:
        Dict with:
            - entries: List of popup dismissal records
            - total: Total records in history
            - watcher_active: Whether watcher is currently running

    Example:
        # After running some automation...
        history = popup_history(serial)

        # Shows: [
        #   {"name": "save_login_info", "timestamp": "...", "dismissed": True},
        #   {"name": "notifications", "timestamp": "...", "dismissed": True}
        # ]
    """
    with _popup_lock:
        history = _popup_history.get(serial, deque())
        total = len(history)

        # Get newest first (reverse order), limited
        entries = list(reversed(list(history)))[:limit]

        watcher_active = (
            serial in _popup_threads and
            _popup_threads[serial].is_alive()
        )

        if clear and serial in _popup_history:
            _popup_history[serial].clear()

    return {
        "entries": entries,
        "total": total,
        "returned": len(entries),
        "watcher_active": watcher_active,
        "pattern_count": len(_popup_patterns.get(serial, []))
    }


# ============================================================================
# TOOL 22: popup_check
# ============================================================================

@mcp.tool()
def popup_check(
    serial: str,
    patterns: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    One-shot check for popups on screen right now.

    Unlike the background watcher, this is a single check that returns
    immediately with what's currently visible. Useful for:
        - Discovery: Finding new popup patterns
        - Debugging: Seeing what's blocking automation
        - Manual handling: When you want to decide what to do

    Args:
        serial: Device serial number from list_devices()
        patterns: Optional patterns to check. If None, uses configured patterns.

    Returns:
        Dict with:
            - found: List of popup patterns currently visible on screen
            - checked: Number of patterns checked

    Example:
        # Check configured patterns
        result = popup_check(serial)
        # Returns: {"found": [{"name": "save_login", ...}], "checked": 5}

        # Check custom patterns (discovery mode)
        popup_check(serial, patterns=[
            {"name": "test", "detect_xpath": "//*[contains(@text, 'Error')]"}
        ])
    """
    driver = get_driver(serial)
    d = driver.ud

    with _popup_lock:
        check_patterns = patterns if patterns else _popup_patterns.get(serial, [])

    found = []

    for pattern in check_patterns:
        name = pattern.get("name", "unnamed")
        detect_xpath = pattern.get("detect_xpath", "")

        if not detect_xpath:
            continue

        try:
            if d.xpath(detect_xpath).exists:
                found.append({
                    "name": name,
                    "detect_xpath": detect_xpath,
                    "dismiss_xpath": pattern.get("dismiss_xpath", ""),
                    "visible": True
                })
        except Exception as e:
            logger.debug(f"Pattern check error for {name}: {e}")

    return {
        "found": found,
        "checked": len(check_patterns),
        "any_visible": len(found) > 0,
        "message": f"Found {len(found)} popup(s) currently visible" if found else "No configured popups visible"
    }


# ============================================================================
# SCREEN DETECTION & NAVIGATION TOOLS
# ============================================================================

# ============================================================================
# TOOL 23: detect_screen
# ============================================================================

@mcp.tool()
def detect_screen(
    serial: str,
    app_id: str = "instagram",
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Detect the current screen using signature-based fingerprinting.

    This uses pre-defined UI signatures to identify which screen the app
    is currently showing. Much faster than analyzing screenshots for every
    interaction - use this to know "where am I?" before taking actions.

    The detection system:
    - Dumps UI hierarchy once
    - Extracts element identifiers (resource-ids, text, content-desc)
    - Matches against 40+ known screen signatures
    - Returns confidence score and matched elements

    Args:
        serial: Device serial number from list_devices()
        app_id: App to detect screens for ("instagram", "android_system")
        force_refresh: If True, bypasses 500ms UI cache

    Returns:
        Dict with:
            - app_id: App the screen belongs to
            - screen_id: Detected screen identifier (e.g., "home_feed", "explore_grid")
            - full_id: Combined "app_id/screen_id" format
            - confidence: 0.0 to 1.0 confidence score
            - is_confident: True if confidence >= 0.8
            - is_unknown: True if screen couldn't be identified
            - detection_time_ms: How long detection took
            - matched_elements: Which signature selectors matched
            - candidates: Alternative matches [(screen_id, score), ...]
            - description: Human-readable screen description
            - is_safe_state: Whether this is a safe state for operations
            - recovery_action: Suggested recovery action if stuck

    Example workflow:
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

    Known screens (Instagram):
        - home_feed, explore_grid, profile_page, dm_inbox, reels_tab
        - reel_viewing, story_viewing, comments_view, likes_page
        - login_page, login_2fa_code, login_save_info
        - create_post_select, create_post_edit, create_reel_camera
        - search_results_reels, profile_grid, profile_followers
        - ...and 30+ more

    System overlays detected automatically:
        - permission_dialog, app_crash_dialog, app_not_responding
        - battery_optimization, no_internet_dialog
    """
    detector = get_screen_detector(serial)
    result = detector.detect_screen(
        app_id=app_id,
        force_refresh=force_refresh,
        include_system=True  # Always check for system overlays
    )
    return result.to_dict()


# ============================================================================
# TOOL 24: dump_for_signature
# ============================================================================

@mcp.tool()
def dump_for_signature(serial: str) -> Dict[str, Any]:
    """
    Dump current UI for creating new screen signatures.

    Use this when detect_screen returns "unknown" and you want to create
    a new signature for this screen. Returns structured element data
    organized by type for easy signature creation.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with:
            - timestamp: When dump was taken
            - resource_ids: List of element IDs (use ":id/xxx" format in signatures)
            - content_descs: List of content descriptions
            - texts: List of visible text values
            - classes: List of element class types
            - clickables: List of clickable element descriptions
            - total_elements: Total extracted elements
            - hint: Usage guidance for creating signatures

    Creating a new signature from dump:
        1. Call dump_for_signature when on unknown screen
        2. Identify unique elements in resource_ids
        3. Create ScreenSignature with:
           - unique: Elements that ONLY appear on this screen
           - required: Elements that MUST be present
           - forbidden: Elements that MUST NOT be present
           - optional: Elements that boost confidence if present

    Example:
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
    """
    detector = get_screen_detector(serial)
    return detector.dump_for_signature()


# ============================================================================
# TOOL 25: get_screen_info
# ============================================================================

@mcp.tool()
def get_screen_info(
    app_id: str = "instagram",
    screen_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get information about available screens and signatures.

    Use this to:
    - List all known screens for an app
    - Get details about a specific screen signature
    - Find safe states for automation
    - Understand the screen detection system

    Args:
        app_id: App to get screen info for ("instagram", "android_system")
        screen_id: Optional specific screen to get details for

    Returns:
        If screen_id is None (list mode):
            - app_id: App identifier
            - screens: List of all screen_ids
            - safe_states: Screen IDs marked as safe for operations
            - total_count: Total number of signatures
            - apps_available: All registered app IDs

        If screen_id is provided (detail mode):
            - app_id, screen_id: Identifiers
            - description: Human-readable description
            - required: Required element selectors
            - forbidden: Forbidden element selectors
            - unique: Unique identifier selectors
            - optional: Optional boost selectors
            - priority: Detection priority (higher = checked first)
            - recovery_action: Suggested recovery if stuck
            - is_safe_state: Whether safe for operations

    Example - List all screens:
        info = get_screen_info(app_id="instagram")
        print(f"Known screens: {info['screens']}")
        print(f"Safe states: {info['safe_states']}")

    Example - Get specific screen details:
        info = get_screen_info(app_id="instagram", screen_id="home_feed")
        print(f"Description: {info['description']}")
        print(f"Unique elements: {info['unique']}")
    """
    registry = get_registry()

    if screen_id:
        # Detail mode - get specific signature
        sig = registry.get_signature(app_id, screen_id)
        if not sig:
            return {
                "error": f"Screen '{screen_id}' not found for app '{app_id}'",
                "available_screens": registry.get_all_screen_ids(app_id)
            }

        return {
            "app_id": sig.app_id,
            "screen_id": sig.screen_id,
            "full_id": sig.full_id,
            "description": sig.description,
            "required": sig.required,
            "forbidden": sig.forbidden,
            "unique": sig.unique,
            "optional": sig.optional,
            "priority": sig.priority,
            "recovery_action": sig.recovery_action,
            "is_safe_state": sig.is_safe_state,
        }
    else:
        # List mode - all screens for app
        return {
            "app_id": app_id,
            "screens": registry.get_all_screen_ids(app_id),
            "safe_states": registry.get_safe_states(app_id),
            "total_count": len(registry.get_all_screen_ids(app_id)),
            "apps_available": registry.list_apps(),
        }


# ============================================================================
# TOOL 26: get_detection_stats
# ============================================================================

@mcp.tool()
def get_detection_stats(serial: str) -> Dict[str, Any]:
    """
    Get screen detection performance statistics.

    Use this to monitor detection system health and performance.
    Useful for debugging slow detection or high unknown rates.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with:
            - detection_count: Total detections performed
            - average_time_ms: Average detection time
            - unknown_count: Times detection returned "unknown"
            - unknown_rate: Ratio of unknown detections (0.0-1.0)

    Performance targets:
        - average_time_ms: <500ms (typically 100-300ms)
        - unknown_rate: <0.05 (5% unknown is concerning)

    Example:
        stats = get_detection_stats(serial)
        if stats['unknown_rate'] > 0.1:
            print("High unknown rate - may need new signatures")
        if stats['average_time_ms'] > 500:
            print("Detection running slow - check device connection")
    """
    detector = get_screen_detector(serial)
    return detector.get_stats()


# ============================================================================
# TOOL 27: navigate_to
# ============================================================================

@mcp.tool()
def navigate_to(
    serial: str,
    target_screen: str,
    app_id: str = "instagram",
    max_attempts: int = 3,
    verify_steps: bool = True
) -> Dict[str, Any]:
    """
    Navigate to a target screen using BFS pathfinding.

    Automatically:
    1. Detects current screen
    2. Finds shortest path to target
    3. Executes navigation actions (clicks, back presses)
    4. Verifies each step
    5. Re-pathfinds if navigation goes off-track

    Args:
        serial: Device serial number from list_devices()
        target_screen: Screen ID to navigate to (e.g., "explore_grid", "home_feed")
        app_id: App to navigate in (default: "instagram")
        max_attempts: Maximum retry attempts (default: 3)
        verify_steps: Verify screen after each step (default: True)

    Returns:
        Dict with:
            - status: "success", "already_there", "failed", "no_path"
            - success: True if navigation completed
            - start_screen: Where navigation started
            - target_screen: Where we wanted to go
            - final_screen: Where we ended up
            - steps_completed: Number of steps taken
            - total_time_seconds: How long navigation took
            - path_summary: List of "from → to" transitions
            - error_message: Error details if failed

    Known screens (Instagram):
        - home_feed, explore_grid, reels_tab, profile_page
        - reel_viewing, comments_view, likes_page
        - search_results_reels, search_results_accounts
        - dm_inbox, story_viewing, create_post_select
        - profile_followers, profile_following

    Example:
        # Navigate from anywhere to explore
        result = navigate_to(serial, "explore_grid")
        if result['success']:
            print(f"Arrived in {result['total_time_seconds']:.1f}s")

        # Navigate to home feed
        navigate_to(serial, "home_feed")

        # Navigate to reels viewing
        navigate_to(serial, "reel_viewing")
    """
    navigator = get_screen_navigator(serial, app_id=app_id)
    result = navigator.navigate_to(
        target=target_screen,
        max_attempts=max_attempts,
        verify_each_step=verify_steps
    )
    return result.to_dict()


# ============================================================================
# TOOL 28: recover_to_safe_state
# ============================================================================

@mcp.tool()
def recover_to_safe_state(
    serial: str,
    context: str = "warmup",
    app_id: str = "instagram"
) -> Dict[str, Any]:
    """
    Navigate to a known safe state for recovery.

    Use this when automation gets stuck or is in an unknown state.
    Will navigate to a predictable screen based on context.

    Args:
        serial: Device serial number from list_devices()
        context: Recovery context:
            - "warmup": For warmup operations (targets: explore_grid, search_results_reels)
            - "login": After login (targets: home_feed, explore_grid)
            - "browse": General browsing (targets: explore_grid)
        app_id: App to recover in (default: "instagram")

    Returns:
        Dict with navigation result (same as navigate_to)

    Safe states by context:
        - warmup: explore_grid, search_results_reels, reel_viewing, home_feed
        - login: home_feed, explore_grid, profile_page
        - browse: explore_grid, search_results_reels

    Example:
        # Recover after getting stuck
        result = recover_to_safe_state(serial, context="warmup")
        if result['success']:
            print(f"Recovered to {result['final_screen']}")
    """
    navigator = get_screen_navigator(serial, app_id=app_id)
    result = navigator.recover_to_safe_state(context=context)
    return result.to_dict()


# ============================================================================
# TOOL 29: get_navigation_graph
# ============================================================================

@mcp.tool()
def get_navigation_graph(
    from_screen: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get information about the navigation graph.

    Use this to understand what navigation paths are available.

    Args:
        from_screen: If provided, get only edges from this screen.
                     If None, returns summary of entire graph.

    Returns:
        If from_screen is None (summary mode):
            - total_screens: Number of screens with outgoing edges
            - all_screens: List of all screen IDs in graph
            - safe_states: Screens marked as safe for recovery

        If from_screen is provided (detail mode):
            - screen_id: The source screen
            - edges: List of possible transitions with:
                - to_screen: Destination
                - cost: Navigation cost
                - reliability: Success probability
                - description: Human-readable description

    Example:
        # Get graph overview
        info = get_navigation_graph()
        print(f"Total screens: {info['total_screens']}")

        # Get edges from explore_grid
        edges = get_navigation_graph(from_screen="explore_grid")
        for e in edges['edges']:
            print(f"  → {e['to_screen']} ({e['description']})")
    """
    from navigation.graph import get_full_graph, get_outgoing_edges, WARMUP_SAFE_STATES

    if from_screen:
        edges = get_outgoing_edges(from_screen)
        return {
            "screen_id": from_screen,
            "edges": [
                {
                    "to_screen": e.to_screen,
                    "cost": e.cost,
                    "reliability": e.reliability,
                    "description": e.description,
                    "actions_count": len(e.actions),
                }
                for e in edges
            ],
            "edge_count": len(edges),
        }
    else:
        graph = get_full_graph()
        return {
            "total_screens": len(graph),
            "all_screens": sorted(graph.keys()),
            "safe_states": list(WARMUP_SAFE_STATES),
        }


# ============================================================================
# TOOL 30: get_navigation_stats
# ============================================================================

@mcp.tool()
def get_navigation_stats(serial: str) -> Dict[str, Any]:
    """
    Get navigation performance statistics.

    Use this to monitor navigation success rate and timing.

    Args:
        serial: Device serial number from list_devices()

    Returns:
        Dict with:
            - total_navigations: Total navigation attempts
            - successful_navigations: Successful navigations
            - success_rate: Success ratio (0.0-1.0)
            - total_steps_executed: Total steps taken
            - average_navigation_time_seconds: Average time per navigation
            - graph_screens: Number of screens in navigation graph

    Example:
        stats = get_navigation_stats(serial)
        print(f"Success rate: {stats['success_rate']:.1%}")
        print(f"Avg time: {stats['average_navigation_time_seconds']:.1f}s")
    """
    navigator = get_screen_navigator(serial)
    return navigator.get_stats()


# ============================================================================
# TOOL 31: search_for_keyword
# ============================================================================

@mcp.tool()
def search_for_keyword(
    serial: str,
    keyword: str,
    ensure_reels: bool = True,
    timeout: float = 15.0,
    app_id: str = "instagram",
) -> Dict[str, Any]:
    """
    Search for a keyword and navigate to search results.

    This tool handles the dynamic search flow that can't be done through static
    navigation edges. It will:
    1. Navigate to explore_grid if not already there
    2. Click search bar
    3. Type the keyword with human-like delays
    4. Press Enter to search
    5. Wait for results
    6. Optionally switch to Reels tab if showing accounts

    Args:
        serial: Device serial number from list_devices()
        keyword: Search keyword to enter (e.g., "dance", "funny", "trending")
        ensure_reels: If True, switch to Reels tab if results show accounts (default: True)
        timeout: Maximum time for the entire operation in seconds (default: 15)
        app_id: App to search in (default: "instagram")

    Returns:
        Dict with:
            - success: True if search completed
            - keyword: The keyword that was searched
            - result_type: "reels", "accounts", "unknown", or "failed"
            - final_screen: Current screen after search
            - steps_taken: List of steps performed
            - total_time_seconds: How long the operation took
            - error_message: Error details if failed

    Example:
        # Search for dance reels
        result = search_for_keyword(serial, keyword="dance")
        if result['success'] and result['result_type'] == 'reels':
            print(f"Ready to browse reels!")

        # Search without auto-switching to Reels tab
        result = search_for_keyword(serial, keyword="fashion", ensure_reels=False)

        # Search with custom timeout
        result = search_for_keyword(serial, keyword="cats", timeout=20.0)
    """
    driver = get_driver(serial)
    detector = get_screen_detector(serial)
    navigator = get_screen_navigator(serial, app_id=app_id)

    result = _search_for_keyword(
        d=driver.ud,  # Pass raw u2.Device, not AndroidDriver wrapper
        detector=detector,
        navigator=navigator,
        keyword=keyword,
        ensure_reels=ensure_reels,
        timeout=timeout,
    )

    return {
        "success": result.success,
        "keyword": result.keyword,
        "result_type": result.result_type.value,
        "final_screen": result.final_screen,
        "steps_taken": result.steps_taken,
        "total_time_seconds": result.total_time_seconds,
        "error_message": result.error_message,
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UIAgent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: stdio (local) or sse (HTTP for remote access)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind SSE server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for SSE server (default: 8765)"
    )
    args = parser.parse_args()

    logger.info("Starting UIAgent MCP Server...")
    logger.info(f"Transport: {args.transport}")
    logger.info(
        "Available tools: list_devices, screenshot, run_script, ui_hierarchy, tap, shell, "
        "device_info, get_elements, wait_for, swipe, app_launch, app_terminate, app_list, "
        "file_push, file_pull, get_orientation, set_orientation, popup_configure, popup_enable, "
        "popup_disable, popup_history, popup_check, detect_screen, dump_for_signature, "
        "get_screen_info, get_detection_stats, navigate_to, recover_to_safe_state, "
        "get_navigation_graph, get_navigation_stats, search_for_keyword"
    )

    if args.transport == "sse":
        logger.info(f"SSE server listening on http://{args.host}:{args.port}")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run()
