# Android System Screen Signatures
# Common system dialogs that can appear over any app
#
# These have the HIGHEST priority (100) since they overlay app content
# and must be detected/handled before the underlying app screen.

from typing import List
from .base import ScreenSignature, register_signatures

APP_ID = "android_system"

ANDROID_SYSTEM_SIGNATURES: List[ScreenSignature] = [
    # -------------------------------------------------------------------------
    # PERMISSION DIALOGS (Priority 100)
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="permission_dialog",
        description="Android permission request dialog (Allow/Deny)",
        required=[
            "text:Allow",
            "text:Deny",
        ],
        forbidden=[],
        unique=[":id/permission_message"],
        optional=[
            "text:Don't allow",
            "text:While using the app",
            "text:Only this time",
            ":id/permission_icon",
            "contains:access to",
        ],
        priority=100,
        recovery_action="click_deny",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="permission_dialog_v2",
        description="Android 13+ permission dialog with radio buttons",
        required=[
            "text:Allow",
        ],
        forbidden=[],
        unique=[
            "text:While using the app",
            "text:Only this time",
        ],
        optional=[
            "text:Don't allow",
            ":id/permission_allow_button",
            ":id/permission_deny_button",
        ],
        priority=100,
        recovery_action="click_deny",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # APP CRASH/ERROR DIALOGS
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="app_crash_dialog",
        description="App has stopped/crashed dialog",
        required=["contains:has stopped"],
        forbidden=[],
        unique=["contains:has stopped"],
        optional=[
            "text:Close app",
            "text:Open app again",
            "text:Send feedback",
            "text:App info",
        ],
        priority=100,
        recovery_action="click_close_app",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="app_not_responding",
        description="App not responding (ANR) dialog",
        required=["contains:isn't responding"],
        forbidden=[],
        unique=["contains:isn't responding"],
        optional=[
            "text:Close app",
            "text:Wait",
            "text:Send feedback",
        ],
        priority=100,
        recovery_action="click_wait",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # BATTERY OPTIMIZATION
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="battery_optimization",
        description="Battery optimization dialog",
        required=["contains:battery optimization"],
        forbidden=[],
        unique=["contains:battery optimization"],
        optional=[
            "text:Allow",
            "text:Deny",
            "text:Don't optimize",
        ],
        priority=100,
        recovery_action="click_deny",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # SYSTEM ALERTS
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="system_alert_window",
        description="Display over other apps permission",
        required=["contains:display over other apps"],
        forbidden=[],
        unique=["contains:display over other apps"],
        optional=[
            "text:Allow",
            "text:Deny",
        ],
        priority=100,
        recovery_action="click_deny",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="accessibility_service",
        description="Accessibility service confirmation",
        required=["contains:Accessibility"],
        forbidden=[],
        unique=["contains:full control of your device"],
        optional=[
            "text:Allow",
            "text:Deny",
            "text:Use service",
        ],
        priority=100,
        recovery_action="click_allow",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # NETWORK/CONNECTION
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="no_internet_dialog",
        description="No internet connection dialog",
        required=["contains:No internet"],
        forbidden=[],
        unique=["contains:No internet"],
        optional=[
            "text:OK",
            "text:Retry",
            "text:Settings",
        ],
        priority=95,
        recovery_action="click_ok",
        is_safe_state=False,
    ),

    ScreenSignature(
        app_id=APP_ID,
        screen_id="wifi_connection_prompt",
        description="WiFi connection prompt",
        required=["contains:Wi-Fi"],
        forbidden=[],
        optional=[
            "text:Connect",
            "text:Cancel",
            ":id/alertTitle",
        ],
        priority=90,
        recovery_action="click_cancel",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # STORAGE/DATA
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="low_storage_warning",
        description="Low storage space warning",
        required=["contains:Storage space"],
        forbidden=[],
        unique=["contains:running low"],
        optional=[
            "text:OK",
            "text:Manage storage",
        ],
        priority=95,
        recovery_action="click_ok",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # APP UPDATES
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="app_update_available",
        description="App update available dialog (modal)",
        required=[
            # Dialogs have alertTitle or similar dialog elements
            ":id/alertTitle|:id/message|:id/button1|:id/button2",
        ],
        forbidden=[],
        unique=[
            "text:Update|text:Update now",  # Button text, not notification
        ],
        optional=[
            "text:Not now",
            "text:Later",
            "contains:new version",
            "contains:update available",
        ],
        priority=90,
        recovery_action="click_not_now",
        is_safe_state=False,
    ),

    # -------------------------------------------------------------------------
    # GOOGLE PLAY SERVICES
    # -------------------------------------------------------------------------

    ScreenSignature(
        app_id=APP_ID,
        screen_id="google_play_services_update",
        description="Google Play Services update required",
        required=["contains:Google Play services"],
        forbidden=[],
        unique=["contains:Google Play services"],
        optional=[
            "text:Update",
            "text:Cancel",
        ],
        priority=95,
        recovery_action="click_cancel",
        is_safe_state=False,
    ),
]


def register_android_system_signatures():
    """Register all Android system signatures with the global registry."""
    register_signatures(APP_ID, ANDROID_SYSTEM_SIGNATURES)


# Auto-register on import
register_android_system_signatures()
