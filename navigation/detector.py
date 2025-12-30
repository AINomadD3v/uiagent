# Screen Signature Detector
# Ported from ig-automation with multi-app support
#
# Fast, parallel screen detection using UI fingerprinting.
# Single UI dump → extract elements → score all signatures in parallel.
#
# Performance target: <500ms detection with 95%+ accuracy

import time
import threading
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Set, List, Dict, Any
from datetime import datetime

from signatures.base import (
    ScreenSignature,
    ScreenDetectionResult,
    get_signatures_for_app,
    get_registry,
)

logger = logging.getLogger(__name__)


class ScreenDetector:
    """
    Fast screen detection using parallel signature matching.

    Instead of checking states one-by-one (slow), this:
    1. Dumps the UI hierarchy ONCE
    2. Extracts all element identifiers into a Set
    3. Scores ALL signatures in parallel
    4. Returns the best match with confidence

    Usage:
        detector = ScreenDetector(device)
        result = detector.detect_screen("instagram")
        print(f"Screen: {result.screen_id}, Confidence: {result.confidence}")
    """

    # Cache settings
    CACHE_TTL_MS = 500  # UI dump valid for 500ms

    def __init__(self, device):
        """
        Initialize the screen detector.

        Args:
            device: uiautomator2 device instance
        """
        self.device = device
        self._lock = threading.RLock()

        # UI hierarchy cache
        self._cached_hierarchy: Optional[ET.Element] = None
        self._cache_timestamp: float = 0
        self._cached_elements: Set[str] = set()

        # Detection metrics
        self._detection_count = 0
        self._total_detection_time_ms = 0
        self._unknown_count = 0

    def detect_screen(
        self,
        app_id: str = "instagram",
        force_refresh: bool = False,
        include_system: bool = True,
    ) -> ScreenDetectionResult:
        """
        Detect the current screen using signature matching.

        Args:
            app_id: Which app's signatures to use
            force_refresh: If True, ignores cache and dumps fresh UI
            include_system: Include android_system signatures (permission dialogs)

        Returns:
            ScreenDetectionResult with screen_id, confidence, and metadata
        """
        start_time = time.time()

        try:
            # Step 1: Get UI hierarchy (cached or fresh)
            hierarchy = self._get_ui_hierarchy(force_refresh)
            if hierarchy is None:
                return ScreenDetectionResult(
                    app_id=app_id,
                    screen_id="unknown",
                    confidence=0.0,
                    detection_time_ms=(time.time() - start_time) * 1000,
                    error="Failed to dump UI hierarchy",
                )

            # Step 2: Extract elements from hierarchy
            elements = self._extract_elements(hierarchy)

            # Step 3: Get signatures for this app
            signatures = get_signatures_for_app(app_id, include_system)
            if not signatures:
                return ScreenDetectionResult(
                    app_id=app_id,
                    screen_id="unknown",
                    confidence=0.0,
                    detection_time_ms=(time.time() - start_time) * 1000,
                    error=f"No signatures registered for app: {app_id}",
                )

            # Step 4: Score all signatures
            scores: Dict[str, tuple[float, ScreenSignature]] = {}
            matched_elements_map: Dict[str, List[str]] = {}

            for sig in signatures:
                score, matched = self._score_signature(sig, elements)
                if score > 0:
                    scores[sig.screen_id] = (score, sig)
                    matched_elements_map[sig.screen_id] = matched

            # Step 5: Determine winner
            detection_time_ms = (time.time() - start_time) * 1000
            self._detection_count += 1
            self._total_detection_time_ms += detection_time_ms

            if not scores:
                self._unknown_count += 1
                self._log_unknown_screen(elements, app_id)
                return ScreenDetectionResult(
                    app_id=app_id,
                    screen_id="unknown",
                    confidence=0.0,
                    detection_time_ms=detection_time_ms,
                )

            # Sort by score descending
            sorted_scores = sorted(
                scores.items(),
                key=lambda x: x[1][0],
                reverse=True
            )
            winner_id, (winner_score, winner_sig) = sorted_scores[0]

            # Log close matches for debugging
            if len(sorted_scores) > 1:
                second_id, (second_score, _) = sorted_scores[1]
                if winner_score - second_score < 0.1:
                    logger.debug(
                        f"Close match: {winner_id}={winner_score:.2f} vs "
                        f"{second_id}={second_score:.2f}"
                    )

            return ScreenDetectionResult(
                app_id=winner_sig.app_id,
                screen_id=winner_id,
                confidence=winner_score,
                detection_time_ms=detection_time_ms,
                matched_elements=matched_elements_map.get(winner_id, []),
                candidates=[
                    (sid, score) for sid, (score, _) in sorted_scores[:5]
                ],
                description=winner_sig.description,
                is_safe_state=winner_sig.is_safe_state,
                recovery_action=winner_sig.recovery_action,
            )

        except Exception as e:
            detection_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Screen detection failed: {e}")
            return ScreenDetectionResult(
                app_id=app_id,
                screen_id="unknown",
                confidence=0.0,
                detection_time_ms=detection_time_ms,
                error=str(e),
            )

    def _get_ui_hierarchy(self, force_refresh: bool = False) -> Optional[ET.Element]:
        """Get UI hierarchy with caching."""
        with self._lock:
            now_ms = time.time() * 1000

            # Return cached if valid and not forcing refresh
            if (
                not force_refresh
                and self._cached_hierarchy is not None
                and (now_ms - self._cache_timestamp) < self.CACHE_TTL_MS
            ):
                return self._cached_hierarchy

            # Dump fresh hierarchy
            try:
                xml_str = self.device.dump_hierarchy()
                self._cached_hierarchy = ET.fromstring(xml_str)
                self._cache_timestamp = now_ms
                self._cached_elements = set()  # Clear element cache
                return self._cached_hierarchy
            except Exception as e:
                logger.error(f"UI dump failed: {e}")
                return None

    def _extract_elements(self, hierarchy: ET.Element) -> Set[str]:
        """
        Extract all identifiable elements from UI hierarchy.

        Builds a set of normalized identifiers for fast matching:
        - resource-id:com.instagram.android:id/search_bar
        - id:search_bar (just the ID part for clone-safe matching)
        - content-desc:Like
        - text:Your story
        - class-short:VideoView

        Returns:
            Set of element identifier strings
        """
        # Use cached if available
        if self._cached_elements:
            return self._cached_elements

        elements = set()

        for node in hierarchy.iter():
            attribs = node.attrib

            # Resource ID
            resource_id = attribs.get("resource-id", "")
            if resource_id:
                elements.add(f"resource-id:{resource_id}")
                # Also add just the ID part (after :id/) for clone-safe matching
                if ":id/" in resource_id:
                    elements.add(f"id:{resource_id.split(':id/')[-1]}")

            # Content description
            content_desc = attribs.get("content-desc", "")
            if content_desc:
                elements.add(f"content-desc:{content_desc}")
                elements.add(f"content-desc-lower:{content_desc.lower()}")

            # Text
            text = attribs.get("text", "")
            if text:
                elements.add(f"text:{text}")
                elements.add(f"text-lower:{text.lower()}")

            # Class name
            class_name = attribs.get("class", "")
            if class_name:
                elements.add(f"class:{class_name}")
                if "." in class_name:
                    elements.add(f"class-short:{class_name.split('.')[-1]}")

            # Clickable elements
            if attribs.get("clickable") == "true":
                if content_desc:
                    elements.add(f"clickable:{content_desc}")
                if text:
                    elements.add(f"clickable-text:{text}")

        self._cached_elements = elements
        return elements

    def _score_signature(
        self,
        signature: ScreenSignature,
        elements: Set[str]
    ) -> tuple[float, List[str]]:
        """
        Calculate how well elements match a signature.

        Scoring:
        - Unique match: 1.0 (instant win, but check forbidden)
        - Forbidden match: 0.0 (instant disqualification)
        - Required: score based on match ratio
        - Optional: small boost (up to 0.1)

        Returns:
            (score, list_of_matched_elements)
        """
        matched = []

        # Check unique identifiers first (fast path)
        for unique in signature.unique:
            if self._selector_matches(unique, elements):
                # Unique match - but still check forbidden
                for forbidden in signature.forbidden:
                    if self._selector_matches(forbidden, elements):
                        return (0.0, [])  # Disqualified
                matched.append(f"unique:{unique}")
                return (1.0, matched)

        # Check forbidden elements (disqualifies)
        for forbidden in signature.forbidden:
            if self._selector_matches(forbidden, elements):
                return (0.0, [])

        # Count required matches
        required_matches = 0
        for required in signature.required:
            if self._selector_matches(required, elements):
                required_matches += 1
                matched.append(f"required:{required}")

        # Must match at least one required
        if signature.required and required_matches == 0:
            return (0.0, [])

        # Base score from required matches
        if signature.required:
            base_score = required_matches / len(signature.required)
        else:
            base_score = 0.5  # No required = partial match

        # Optional element boost (max 0.1)
        optional_matches = 0
        for optional in signature.optional:
            if self._selector_matches(optional, elements):
                optional_matches += 1
                matched.append(f"optional:{optional}")

        if signature.optional:
            optional_boost = 0.1 * (optional_matches / len(signature.optional))
        else:
            optional_boost = 0.0

        final_score = min(1.0, base_score + optional_boost)
        return (final_score, matched)

    def _selector_matches(self, selector: str, elements: Set[str]) -> bool:
        """
        Check if a selector matches any element in the set.

        Selector formats supported:
        - :id/foo -> matches any package with :id/foo (clone-safe!)
        - content-desc:Like -> exact content-desc match
        - text:Your story -> exact text match
        - VideoView -> matches class-short:VideoView
        - Like OR Unlike -> either matches
        - contains:Reel by -> substring search
        """
        # Handle OR conditions (e.g., "Like OR Unlike")
        if " OR " in selector:
            parts = selector.split(" OR ")
            return any(self._selector_matches(part.strip(), elements) for part in parts)

        # Handle contains syntax (e.g., "contains:Reel by")
        if selector.startswith("contains:"):
            search_text = selector[9:].lower()
            for elem in elements:
                if search_text in elem.lower():
                    return True
            return False

        # Resource-id match - CLONE SAFE!
        # Matches any package name, just looks for the :id/xxx part
        if ":id/" in selector:
            id_part = selector.split(":id/")[-1]
            for elem in elements:
                if elem.startswith("resource-id:") and f":id/{id_part}" in elem:
                    return True
                if elem.startswith("id:") and elem == f"id:{id_part}":
                    return True
            return False

        # Short id format (e.g., "id:action_bar_search_edit_text")
        if selector.startswith("id:"):
            id_part = selector[3:]
            for elem in elements:
                if elem.startswith("resource-id:") and f":id/{id_part}" in elem:
                    return True
                if elem == selector:
                    return True
            return False

        # Content description match
        if selector.startswith("content-desc:"):
            return selector in elements

        # Text match
        if selector.startswith("text:"):
            return selector in elements

        # Class match (short name like VideoView)
        if selector[0].isupper() and ":" not in selector:
            return f"class-short:{selector}" in elements

        # Generic match - try multiple formats
        return (
            f"content-desc:{selector}" in elements
            or f"text:{selector}" in elements
            or f"id:{selector}" in elements
        )

    def _log_unknown_screen(self, elements: Set[str], app_id: str) -> None:
        """Log details about an unknown screen for debugging."""
        resource_ids = sorted([e for e in elements if e.startswith("id:")])[:10]
        content_descs = sorted([e for e in elements if e.startswith("content-desc:")])[:10]
        texts = sorted([e for e in elements if e.startswith("text:")])[:10]

        logger.warning(
            f"Unknown screen for {app_id}. Key elements:\n"
            f"  ids: {resource_ids[:5]}\n"
            f"  content-desc: {content_descs[:5]}\n"
            f"  texts: {texts[:5]}"
        )

    def invalidate_cache(self) -> None:
        """Force cache invalidation."""
        with self._lock:
            self._cached_hierarchy = None
            self._cached_elements = set()
            self._cache_timestamp = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get detection performance statistics."""
        avg_time = (
            self._total_detection_time_ms / self._detection_count
            if self._detection_count > 0
            else 0
        )
        return {
            "detection_count": self._detection_count,
            "average_time_ms": round(avg_time, 2),
            "unknown_count": self._unknown_count,
            "unknown_rate": round(
                self._unknown_count / self._detection_count
                if self._detection_count > 0
                else 0,
                3
            ),
        }

    def dump_for_signature(self) -> Dict[str, Any]:
        """
        Dump current UI for signature creation.

        Use this when detect_screen returns UNKNOWN. Returns structured
        data that can be used to create a new signature.

        Returns:
            Dict with all extracted elements organized by type
        """
        hierarchy = self._get_ui_hierarchy(force_refresh=True)
        if hierarchy is None:
            return {"error": "Failed to dump hierarchy"}

        elements = self._extract_elements(hierarchy)

        return {
            "timestamp": datetime.now().isoformat(),
            "resource_ids": sorted([e[3:] for e in elements if e.startswith("id:")]),
            "content_descs": sorted([
                e[13:] for e in elements
                if e.startswith("content-desc:") and not e.startswith("content-desc-lower:")
            ]),
            "texts": sorted([
                e[5:] for e in elements
                if e.startswith("text:") and not e.startswith("text-lower:")
            ]),
            "classes": sorted([e[12:] for e in elements if e.startswith("class-short:")]),
            "clickables": sorted([e[10:] for e in elements if e.startswith("clickable:")]),
            "total_elements": len(elements),
            "hint": "Use resource_ids for stable signatures (clone-safe with :id/xxx format)",
        }
