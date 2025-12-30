# Screen Navigator - BFS pathfinding and action execution
# Ported from ig-automation for UIAgent MCP server
#
# Provides:
# - BFS shortest path between screens
# - Action execution (click, tap, swipe, etc.)
# - Navigation with verification and re-pathfinding

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Set, Any

from .detector import ScreenDetector
from .graph import (
    ActionType,
    NavigationAction,
    NavigationEdge,
    get_full_graph,
    WARMUP_SAFE_STATES,
    LOGIN_SAFE_STATES,
)

logger = logging.getLogger(__name__)


class NavigationStatus(str, Enum):
    """Status of navigation attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    NO_PATH = "no_path"
    TIMEOUT = "timeout"
    ALREADY_THERE = "already_there"


@dataclass
class NavigationStep:
    """A single step in a navigation path."""
    from_screen: str
    to_screen: str
    edge: NavigationEdge


@dataclass
class NavigationPath:
    """A complete path from source to destination."""
    steps: List[NavigationStep]
    total_cost: float
    estimated_reliability: float

    def __len__(self):
        return len(self.steps)


@dataclass
class NavigationResult:
    """Result of a navigation attempt."""
    status: NavigationStatus
    start_screen: str
    target_screen: str
    final_screen: str
    path_taken: List[NavigationStep] = field(default_factory=list)
    steps_completed: int = 0
    total_time_seconds: float = 0.0
    error_message: Optional[str] = None
    recovery_attempts: int = 0

    @property
    def success(self) -> bool:
        return self.status in (NavigationStatus.SUCCESS, NavigationStatus.ALREADY_THERE)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "status": self.status.value,
            "success": self.success,
            "start_screen": self.start_screen,
            "target_screen": self.target_screen,
            "final_screen": self.final_screen,
            "steps_completed": self.steps_completed,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "error_message": self.error_message,
            "recovery_attempts": self.recovery_attempts,
            "path_summary": [
                f"{s.from_screen} → {s.to_screen}"
                for s in self.path_taken
            ],
        }


class ScreenNavigator:
    """
    Graph-based navigation system for Instagram screens.

    Uses BFS pathfinding to find shortest paths and executes
    navigation sequences with verification.

    Usage:
        navigator = ScreenNavigator(device, detector)
        result = navigator.navigate_to("explore_grid")
    """

    def __init__(
        self,
        device,
        detector: ScreenDetector,
        app_id: str = "instagram",
    ):
        """
        Initialize the navigator.

        Args:
            device: uiautomator2 device instance
            detector: ScreenDetector instance
            app_id: App to navigate in (default: instagram)
        """
        self.device = device
        self.detector = detector
        self.app_id = app_id

        # Build navigation graph
        self._graph = get_full_graph()

        # Statistics
        self._total_navigations = 0
        self._successful_navigations = 0
        self._total_steps_executed = 0
        self._total_navigation_time = 0.0

        logger.info(f"Navigator initialized with {len(self._graph)} source screens")

    def find_path(
        self,
        from_screen: str,
        to_screen: str
    ) -> Optional[NavigationPath]:
        """
        Find shortest path between two screens using BFS.

        Args:
            from_screen: Starting screen ID
            to_screen: Destination screen ID

        Returns:
            NavigationPath if path exists, None otherwise
        """
        if from_screen == to_screen:
            return NavigationPath(steps=[], total_cost=0.0, estimated_reliability=1.0)

        # BFS: (current_screen, path_so_far, total_cost, total_reliability)
        queue = deque([(from_screen, [], 0.0, 1.0)])
        visited: Set[str] = {from_screen}

        while queue:
            current, path, cost, reliability = queue.popleft()

            edges = self._graph.get(current, [])
            for edge in edges:
                if edge.to_screen in visited:
                    continue

                new_step = NavigationStep(
                    from_screen=current,
                    to_screen=edge.to_screen,
                    edge=edge
                )
                new_path = path + [new_step]
                new_cost = cost + edge.cost
                new_reliability = reliability * edge.reliability

                if edge.to_screen == to_screen:
                    return NavigationPath(
                        steps=new_path,
                        total_cost=new_cost,
                        estimated_reliability=new_reliability
                    )

                visited.add(edge.to_screen)
                queue.append((edge.to_screen, new_path, new_cost, new_reliability))

        return None

    def find_path_to_any(
        self,
        from_screen: str,
        targets: Set[str]
    ) -> Optional[NavigationPath]:
        """
        Find shortest path to any screen in target set.

        Args:
            from_screen: Starting screen
            targets: Set of acceptable destinations

        Returns:
            NavigationPath to closest target, None if unreachable
        """
        if from_screen in targets:
            return NavigationPath(steps=[], total_cost=0.0, estimated_reliability=1.0)

        queue = deque([(from_screen, [], 0.0, 1.0)])
        visited: Set[str] = {from_screen}

        while queue:
            current, path, cost, reliability = queue.popleft()

            edges = self._graph.get(current, [])
            for edge in edges:
                if edge.to_screen in visited:
                    continue

                new_step = NavigationStep(
                    from_screen=current,
                    to_screen=edge.to_screen,
                    edge=edge
                )
                new_path = path + [new_step]
                new_cost = cost + edge.cost
                new_reliability = reliability * edge.reliability

                if edge.to_screen in targets:
                    return NavigationPath(
                        steps=new_path,
                        total_cost=new_cost,
                        estimated_reliability=new_reliability
                    )

                visited.add(edge.to_screen)
                queue.append((edge.to_screen, new_path, new_cost, new_reliability))

        return None

    def navigate_to(
        self,
        target: str,
        max_attempts: int = 3,
        verify_each_step: bool = True,
    ) -> NavigationResult:
        """
        Navigate to target screen with automatic re-pathfinding.

        Args:
            target: Destination screen ID
            max_attempts: Maximum navigation attempts
            verify_each_step: If True, verify screen after each step

        Returns:
            NavigationResult with status and details
        """
        self._total_navigations += 1
        start_time = time.time()
        all_steps_taken: List[NavigationStep] = []
        recovery_attempts = 0
        start_screen = "unknown"

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Navigation attempt {attempt}/{max_attempts} to {target}")

            # Detect current screen
            detection = self.detector.detect_screen(app_id=self.app_id, force_refresh=True)
            current_screen = detection.screen_id
            if start_screen == "unknown":
                start_screen = current_screen

            if current_screen == "unknown":
                logger.warning(f"Unknown screen on attempt {attempt}")
                recovery_attempts += 1
                time.sleep(1.0)
                continue

            # Already at target?
            if current_screen == target:
                self._successful_navigations += 1
                elapsed = time.time() - start_time
                return NavigationResult(
                    status=NavigationStatus.ALREADY_THERE if attempt == 1 else NavigationStatus.SUCCESS,
                    start_screen=start_screen,
                    target_screen=target,
                    final_screen=current_screen,
                    path_taken=all_steps_taken,
                    steps_completed=len(all_steps_taken),
                    total_time_seconds=elapsed,
                    recovery_attempts=recovery_attempts,
                )

            # Find path
            path = self.find_path(current_screen, target)
            if path is None:
                return NavigationResult(
                    status=NavigationStatus.NO_PATH,
                    start_screen=start_screen,
                    target_screen=target,
                    final_screen=current_screen,
                    path_taken=all_steps_taken,
                    steps_completed=len(all_steps_taken),
                    total_time_seconds=time.time() - start_time,
                    error_message=f"No path from {current_screen} to {target}",
                    recovery_attempts=recovery_attempts,
                )

            logger.info(
                f"Path found: {len(path)} steps, "
                f"reliability={path.estimated_reliability:.1%}"
            )

            # Execute path
            for i, step in enumerate(path.steps, 1):
                logger.info(f"  Step {i}/{len(path)}: {step.from_screen} → {step.to_screen}")

                if not self._execute_step(step):
                    logger.warning(f"Step execution failed")
                    recovery_attempts += 1
                    break

                all_steps_taken.append(step)
                self._total_steps_executed += 1

                # Verify (unless last step, which we'll verify below)
                if verify_each_step:
                    time.sleep(0.5)
                    verify_result = self.detector.detect_screen(
                        app_id=self.app_id, force_refresh=True
                    )
                    actual = verify_result.screen_id

                    if actual != step.to_screen:
                        logger.warning(
                            f"Deviated: expected {step.to_screen}, got {actual}"
                        )
                        recovery_attempts += 1
                        break

                # Success on final step
                if i == len(path.steps):
                    self._successful_navigations += 1
                    elapsed = time.time() - start_time
                    self._total_navigation_time += elapsed
                    return NavigationResult(
                        status=NavigationStatus.SUCCESS,
                        start_screen=start_screen,
                        target_screen=target,
                        final_screen=step.to_screen,
                        path_taken=all_steps_taken,
                        steps_completed=len(all_steps_taken),
                        total_time_seconds=elapsed,
                        recovery_attempts=recovery_attempts,
                    )

        # Max attempts exhausted
        final_detection = self.detector.detect_screen(app_id=self.app_id, force_refresh=True)
        return NavigationResult(
            status=NavigationStatus.FAILED,
            start_screen=start_screen,
            target_screen=target,
            final_screen=final_detection.screen_id,
            path_taken=all_steps_taken,
            steps_completed=len(all_steps_taken),
            total_time_seconds=time.time() - start_time,
            error_message=f"Failed after {max_attempts} attempts",
            recovery_attempts=recovery_attempts,
        )

    def recover_to_safe_state(self, context: str = "warmup") -> NavigationResult:
        """
        Navigate to a safe state based on context.

        Args:
            context: "warmup", "login", or "browse"

        Returns:
            NavigationResult indicating recovery status
        """
        if context == "warmup":
            targets = WARMUP_SAFE_STATES
            preferred = "explore_grid"
        elif context == "login":
            targets = LOGIN_SAFE_STATES
            preferred = "home_feed"
        else:
            targets = WARMUP_SAFE_STATES
            preferred = "explore_grid"

        logger.info(f"Recovering to safe state (context: {context})")

        # Check if already safe
        detection = self.detector.detect_screen(app_id=self.app_id, force_refresh=True)
        if detection.screen_id in targets:
            logger.info(f"Already in safe state: {detection.screen_id}")
            return NavigationResult(
                status=NavigationStatus.ALREADY_THERE,
                start_screen=detection.screen_id,
                target_screen=detection.screen_id,
                final_screen=detection.screen_id,
                steps_completed=0,
                total_time_seconds=0.0,
            )

        # Try preferred first
        result = self.navigate_to(preferred, max_attempts=2)
        if result.success:
            return result

        # Try any safe state
        logger.info(f"Preferred target failed, trying any safe state")
        path = self.find_path_to_any(detection.screen_id, targets)
        if path and path.steps:
            target = path.steps[-1].to_screen
            return self.navigate_to(target, max_attempts=2)

        return NavigationResult(
            status=NavigationStatus.NO_PATH,
            start_screen=detection.screen_id,
            target_screen=preferred,
            final_screen=detection.screen_id,
            error_message="No path to any safe state",
        )

    def _execute_step(self, step: NavigationStep) -> bool:
        """Execute a single navigation step."""
        try:
            for action in step.edge.actions:
                if not self._execute_action(action):
                    return False
            return True
        except Exception as e:
            logger.error(f"Step execution error: {e}")
            return False

    def _execute_action(self, action: NavigationAction) -> bool:
        """Execute a single navigation action."""
        try:
            if action.action_type == ActionType.PRESS_BACK:
                self.device.press("back")
                time.sleep(action.wait_after)
                return True

            elif action.action_type == ActionType.CLICK_TAB:
                if action.target:
                    elem = self.device(description=action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    logger.warning(f"Tab not found: {action.target}")
                return False

            elif action.action_type == ActionType.CLICK_TEXT:
                if action.target:
                    elem = self.device(text=action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    # Try textContains as fallback
                    elem = self.device(textContains=action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    logger.warning(f"Text not found: {action.target}")
                return False

            elif action.action_type == ActionType.CLICK_CONTENT_DESC:
                if action.target:
                    elem = self.device(description=action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    # Try descriptionContains
                    elem = self.device(descriptionContains=action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    logger.warning(f"Content desc not found: {action.target}")
                return False

            elif action.action_type == ActionType.CLICK_ELEMENT:
                if action.target:
                    elem = self.device.xpath(action.target)
                    if elem.exists:
                        elem.click()
                        time.sleep(action.wait_after)
                        return True
                    logger.warning(f"Element not found: {action.target}")
                return False

            elif action.action_type == ActionType.SWIPE_DOWN:
                self.device.swipe(0.5, 0.3, 0.5, 0.7)
                time.sleep(action.wait_after)
                return True

            elif action.action_type == ActionType.SWIPE_UP:
                self.device.swipe(0.5, 0.7, 0.5, 0.3)
                time.sleep(action.wait_after)
                return True

            elif action.action_type == ActionType.WAIT:
                time.sleep(action.wait_after)
                return True

            elif action.action_type == ActionType.LAUNCH_APP:
                if action.target:
                    self.device.app_start(action.target)
                    time.sleep(action.wait_after)
                    return True
                return False

            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False

        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get navigation statistics."""
        success_rate = (
            self._successful_navigations / self._total_navigations
            if self._total_navigations > 0
            else 0.0
        )
        avg_time = (
            self._total_navigation_time / self._successful_navigations
            if self._successful_navigations > 0
            else 0.0
        )

        return {
            "total_navigations": self._total_navigations,
            "successful_navigations": self._successful_navigations,
            "success_rate": round(success_rate, 3),
            "total_steps_executed": self._total_steps_executed,
            "average_navigation_time_seconds": round(avg_time, 2),
            "graph_screens": len(self._graph),
        }
