# Screen Signature Base Classes
# Ported from ig-automation with multi-app support
#
# The signature system allows Claude to know "where am I?" in any app
# by matching UI element fingerprints against known screens.

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from enum import Enum


@dataclass
class ScreenSignature:
    """
    Defines the UI fingerprint for a specific app screen.

    This is the core abstraction for screen detection. Each signature
    describes what elements should/shouldn't be present on a screen.

    Attributes:
        app_id: App identifier (e.g., "instagram", "tiktok", "android_system")
        screen_id: Unique identifier for this screen within the app
        required: List of element selectors that MUST ALL be present
        forbidden: List of element selectors that MUST NOT be present
        unique: List of element selectors where ANY ONE = instant 100% match
        optional: List of element selectors that boost confidence if present
        priority: Higher values checked first (overlays = 100, base screens = 10-50)
        recovery_action: Default recovery action if stuck on this screen
        description: Human-readable description for Claude
        is_safe_state: Whether this is a "safe" screen for operations

    Selector Format (Clone-Safe):
        - ":id/element_id" - Resource ID (matches any package prefix)
        - "text:exact text" - Exact text match
        - "content-desc:label" - Accessibility content description
        - "contains:substring" - Text contains substring
        - "class:android.widget.Button" - Element class type

    Example:
        ScreenSignature(
            app_id="instagram",
            screen_id="explore_grid",
            required=[":id/explore_action_bar", ":id/search_row_container"],
            forbidden=[":id/comments_view"],
            unique=[":id/explore_action_bar"],
            priority=50,
            description="Instagram Explore/Search landing page",
            is_safe_state=True,
        )
    """
    app_id: str
    screen_id: str
    required: List[str] = field(default_factory=list)
    forbidden: List[str] = field(default_factory=list)
    unique: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    priority: int = 50
    recovery_action: Optional[str] = None
    description: str = ""
    is_safe_state: bool = False

    def __post_init__(self):
        """Validate signature configuration."""
        if not self.required and not self.unique:
            raise ValueError(
                f"Signature {self.app_id}/{self.screen_id} must have required or unique elements"
            )

    @property
    def full_id(self) -> str:
        """Return full identifier as app_id/screen_id."""
        return f"{self.app_id}/{self.screen_id}"


@dataclass
class ScreenDetectionResult:
    """
    Result of screen detection.

    This is what Claude receives when calling detect_screen().
    Provides confidence score, matched elements, and alternative candidates.

    Attributes:
        app_id: Which app's signatures were matched
        screen_id: Detected screen identifier
        confidence: 0.0 to 1.0 confidence score
        detection_time_ms: How long detection took
        matched_elements: Which selectors matched
        candidates: Alternative matches ranked by score [(screen_id, score), ...]
        description: Human-readable screen description
        is_safe_state: Whether operations can proceed
        recovery_action: Suggested action if recovery needed
        error: Error message if detection failed
    """
    app_id: str
    screen_id: str
    confidence: float
    detection_time_ms: float = 0.0
    matched_elements: List[str] = field(default_factory=list)
    candidates: List[tuple] = field(default_factory=list)
    description: str = ""
    is_safe_state: bool = False
    recovery_action: Optional[str] = None
    error: Optional[str] = None

    @property
    def is_confident(self) -> bool:
        """Returns True if confidence is above threshold (0.8)."""
        return self.confidence >= 0.8

    @property
    def is_unknown(self) -> bool:
        """Returns True if screen could not be identified."""
        return self.screen_id == "unknown"

    @property
    def full_id(self) -> str:
        """Return full identifier as app_id/screen_id."""
        return f"{self.app_id}/{self.screen_id}"

    def to_dict(self) -> dict:
        """Convert to dictionary for MCP tool response."""
        return {
            "app_id": self.app_id,
            "screen_id": self.screen_id,
            "full_id": self.full_id,
            "confidence": self.confidence,
            "is_confident": self.is_confident,
            "is_unknown": self.is_unknown,
            "detection_time_ms": self.detection_time_ms,
            "matched_elements": self.matched_elements,
            "candidates": [
                {"screen_id": sid, "score": score}
                for sid, score in self.candidates[:5]  # Top 5
            ],
            "description": self.description,
            "is_safe_state": self.is_safe_state,
            "recovery_action": self.recovery_action,
            "error": self.error,
        }


class SignatureRegistry:
    """
    Central registry for all app screen signatures.

    Signatures are organized by app_id, allowing detection to focus
    on the relevant app's screens.

    Usage:
        registry = SignatureRegistry()
        registry.register("instagram", instagram_signatures)
        registry.register("android_system", system_signatures)

        # Get signatures for detection
        sigs = registry.get_signatures("instagram")

        # Get combined (app + system overlays)
        sigs = registry.get_signatures("instagram", include_system=True)
    """

    def __init__(self):
        self._signatures: Dict[str, List[ScreenSignature]] = {}
        self._by_screen_id: Dict[str, Dict[str, ScreenSignature]] = {}

    def register(self, app_id: str, signatures: List[ScreenSignature]) -> None:
        """Register signatures for an app."""
        self._signatures[app_id] = signatures
        self._by_screen_id[app_id] = {
            sig.screen_id: sig for sig in signatures
        }
        # Sort by priority (highest first)
        self._signatures[app_id].sort(key=lambda s: s.priority, reverse=True)

    def get_signatures(
        self,
        app_id: str,
        include_system: bool = True
    ) -> List[ScreenSignature]:
        """
        Get signatures for an app, optionally including system dialogs.

        Args:
            app_id: App identifier
            include_system: Include android_system signatures (permission dialogs, etc.)

        Returns:
            List of signatures sorted by priority (highest first)
        """
        sigs = list(self._signatures.get(app_id, []))

        if include_system and app_id != "android_system":
            system_sigs = self._signatures.get("android_system", [])
            sigs.extend(system_sigs)
            # Re-sort by priority
            sigs.sort(key=lambda s: s.priority, reverse=True)

        return sigs

    def get_signature(self, app_id: str, screen_id: str) -> Optional[ScreenSignature]:
        """Get a specific signature by app and screen ID."""
        app_sigs = self._by_screen_id.get(app_id, {})
        return app_sigs.get(screen_id)

    def get_all_screen_ids(self, app_id: str) -> List[str]:
        """Get all registered screen IDs for an app."""
        return list(self._by_screen_id.get(app_id, {}).keys())

    def get_safe_states(self, app_id: str) -> List[str]:
        """Get screen IDs that are marked as safe states."""
        return [
            sig.screen_id
            for sig in self._signatures.get(app_id, [])
            if sig.is_safe_state
        ]

    def list_apps(self) -> List[str]:
        """List all registered app IDs."""
        return list(self._signatures.keys())


# Global registry instance
_registry = SignatureRegistry()


def get_signatures_for_app(
    app_id: str,
    include_system: bool = True
) -> List[ScreenSignature]:
    """Get signatures for an app from the global registry."""
    return _registry.get_signatures(app_id, include_system)


def register_signatures(app_id: str, signatures: List[ScreenSignature]) -> None:
    """Register signatures for an app in the global registry."""
    _registry.register(app_id, signatures)


def get_registry() -> SignatureRegistry:
    """Get the global signature registry."""
    return _registry
