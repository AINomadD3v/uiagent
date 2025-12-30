# Screen Signature System for UIAgent
# Ported from ig-automation's battle-tested detection system
#
# This module provides:
# - ScreenSignature: UI fingerprint definitions
# - ScreenDetectionResult: Detection results with confidence
# - Registry for app-specific signatures

from .base import (
    ScreenSignature,
    ScreenDetectionResult,
    SignatureRegistry,
    get_signatures_for_app,
    register_signatures,
)

__all__ = [
    "ScreenSignature",
    "ScreenDetectionResult",
    "SignatureRegistry",
    "get_signatures_for_app",
    "register_signatures",
]
