# Search functionality for Instagram navigation
# Handles keyword search to reach search_results_reels screen

from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    import uiautomator2 as u2

from .detector import ScreenDetector
from .navigator import ScreenNavigator, NavigationStatus

logger = logging.getLogger(__name__)


class SearchResultType(str, Enum):
    """Type of search results displayed"""
    REELS = "reels"
    ACCOUNTS = "accounts"
    UNKNOWN = "unknown"
    FAILED = "failed"


@dataclass
class SearchResult:
    """Result of a keyword search operation"""
    success: bool
    keyword: str
    result_type: SearchResultType
    final_screen: str
    steps_taken: list[str]
    total_time_seconds: float
    error_message: str | None = None


# XPath selectors for search functionality
SEARCH_BAR_SELECTOR = "//*[contains(@resource-id, 'action_bar_search_edit_text')]"
SEARCH_EDITTEXT_SELECTOR = "//*[contains(@resource-id, 'action_bar_search_edit_text') and @class='android.widget.EditText']"
REELS_TAB_SELECTOR = "//*[@text='Reels' or @text='REELS']"
ACCOUNTS_TAB_SELECTOR = "//*[@text='Accounts' or @text='ACCOUNTS']"

# Detection selectors for result types
REEL_RESULT_SELECTOR = "//android.widget.ImageView[contains(@content-desc, 'Reel by')]"
ACCOUNT_RESULT_SELECTOR = "//*[contains(@resource-id, 'row_search_user_username')]"


def _human_delay(min_ms: int = 100, max_ms: int = 300) -> None:
    """Add human-like delay between actions"""
    time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))


def _type_with_delays(d: u2.Device, text: str, element_xpath: str) -> bool:
    """Type text character by character with human-like delays"""
    try:
        element = d.xpath(element_xpath)
        if not element.exists:
            logger.error(f"Element not found for typing: {element_xpath}")
            return False

        # Click to focus
        element.click()
        _human_delay(200, 400)

        # Clear existing text
        d.clear_text()
        _human_delay(100, 200)

        # Type each character with small delays
        for char in text:
            d.send_keys(char)
            _human_delay(50, 150)

        return True
    except Exception as e:
        logger.error(f"Error typing text: {e}")
        return False


def _detect_search_result_type(d: u2.Device, detector: ScreenDetector) -> SearchResultType:
    """Detect what type of search results are showing"""
    # First check screen detection
    screen_result = detector.detect_screen()

    if screen_result.screen_id == "search_results_reels":
        return SearchResultType.REELS
    elif screen_result.screen_id == "search_results_accounts":
        return SearchResultType.ACCOUNTS

    # Fallback: Check for reel content
    try:
        if d.xpath(REEL_RESULT_SELECTOR).exists:
            return SearchResultType.REELS
        if d.xpath(ACCOUNT_RESULT_SELECTOR).exists:
            return SearchResultType.ACCOUNTS
    except Exception as e:
        logger.warning(f"Error checking result type elements: {e}")

    return SearchResultType.UNKNOWN


def search_for_keyword(
    d: u2.Device,
    detector: ScreenDetector,
    navigator: ScreenNavigator,
    keyword: str,
    ensure_reels: bool = True,
    timeout: float = 15.0,
) -> SearchResult:
    """
    Search for a keyword and navigate to search results.

    Args:
        d: uiautomator2 device instance
        detector: ScreenDetector for current screen detection
        navigator: ScreenNavigator for navigation
        keyword: Search keyword to enter
        ensure_reels: If True, switch to Reels tab if results show accounts
        timeout: Maximum time for the entire operation

    Returns:
        SearchResult with success status, result type, and final screen
    """
    start_time = time.time()
    steps = []

    def elapsed() -> float:
        return time.time() - start_time

    def time_remaining() -> float:
        return timeout - elapsed()

    try:
        # Step 1: Check current screen
        current = detector.detect_screen()
        steps.append(f"Started at: {current.screen_id}")
        logger.info(f"Starting search from screen: {current.screen_id}")

        # Step 2: Navigate to explore_grid if not already there
        if current.screen_id != "explore_grid":
            steps.append("Navigating to explore_grid")
            nav_result = navigator.navigate_to(
                "explore_grid",
                max_attempts=2,
                verify_each_step=True
            )

            if not nav_result.success:
                return SearchResult(
                    success=False,
                    keyword=keyword,
                    result_type=SearchResultType.FAILED,
                    final_screen=current.screen_id,
                    steps_taken=steps,
                    total_time_seconds=elapsed(),
                    error_message=f"Failed to navigate to explore_grid: {nav_result.error_message}",
                )
            steps.append(f"Arrived at explore_grid in {nav_result.total_time_seconds:.1f}s")

        # Step 3: Click search bar
        steps.append("Clicking search bar")
        search_bar = d.xpath(SEARCH_BAR_SELECTOR)
        if not search_bar.wait(timeout=5):
            return SearchResult(
                success=False,
                keyword=keyword,
                result_type=SearchResultType.FAILED,
                final_screen="explore_grid",
                steps_taken=steps,
                total_time_seconds=elapsed(),
                error_message="Search bar not found",
            )

        search_bar.click()
        _human_delay(300, 500)

        # Step 4: Type keyword
        steps.append(f"Typing keyword: {keyword}")

        # Find the edit text field (may appear after clicking search bar)
        edit_text = d.xpath(SEARCH_EDITTEXT_SELECTOR)
        if not edit_text.wait(timeout=3):
            # Fallback: try the original search bar
            edit_text = d.xpath(SEARCH_BAR_SELECTOR)

        if not edit_text.exists:
            return SearchResult(
                success=False,
                keyword=keyword,
                result_type=SearchResultType.FAILED,
                final_screen="explore_grid",
                steps_taken=steps,
                total_time_seconds=elapsed(),
                error_message="Search input field not found",
            )

        # Clear and type
        edit_text.click()
        _human_delay(100, 200)
        d.clear_text()
        _human_delay(100, 200)

        # Type with delays for human-like behavior
        for char in keyword:
            d.send_keys(char)
            _human_delay(30, 100)

        _human_delay(200, 400)

        # Step 5: Press Enter/Search
        steps.append("Pressing Enter to search")
        d.press("enter")

        # Wait for results to load
        _human_delay(1000, 1500)

        # Step 6: Detect result type
        steps.append("Detecting search result type")

        # Wait for screen to stabilize
        for _ in range(5):
            if time_remaining() <= 0:
                break
            _human_delay(500, 800)
            result_type = _detect_search_result_type(d, detector)
            if result_type != SearchResultType.UNKNOWN:
                break

        steps.append(f"Result type detected: {result_type.value}")

        # Step 7: Switch to Reels tab if needed
        if ensure_reels and result_type == SearchResultType.ACCOUNTS:
            steps.append("Switching to Reels tab")
            reels_tab = d.xpath(REELS_TAB_SELECTOR)

            if reels_tab.wait(timeout=3):
                reels_tab.click()
                _human_delay(800, 1200)

                # Verify switch
                new_result_type = _detect_search_result_type(d, detector)
                if new_result_type == SearchResultType.REELS:
                    result_type = SearchResultType.REELS
                    steps.append("Successfully switched to Reels tab")
                else:
                    steps.append("Tab switch may not have worked, staying on current results")
            else:
                steps.append("Reels tab not found, staying on current results")

        # Final screen detection
        final_screen = detector.detect_screen()
        steps.append(f"Final screen: {final_screen.screen_id}")

        return SearchResult(
            success=True,
            keyword=keyword,
            result_type=result_type,
            final_screen=final_screen.screen_id,
            steps_taken=steps,
            total_time_seconds=elapsed(),
        )

    except Exception as e:
        logger.exception(f"Error during keyword search: {e}")

        # Try to detect final screen
        try:
            final = detector.detect_screen()
            final_screen = final.screen_id
        except Exception:
            final_screen = "unknown"

        return SearchResult(
            success=False,
            keyword=keyword,
            result_type=SearchResultType.FAILED,
            final_screen=final_screen,
            steps_taken=steps,
            total_time_seconds=elapsed(),
            error_message=str(e),
        )
