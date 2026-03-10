from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from heartopia_app.infrastructure.constants import BUCKET_FILL_MIN_AREA, SPEED_PRESETS

if TYPE_CHECKING:
    from heartopia_app.domain.calibration import (
        CanvasCalibration,
        PaletteCalibration,
        ToolbarCalibration,
    )
    from heartopia_app.domain.paint_plan import PaintGroup, PaintPlan
    from heartopia_app.infrastructure.input_backend import InputBackend


@dataclass
class PaintProgress:
    """Serializable painting progress for checkpoint resume."""

    drawn_pixels: int = 0
    completed_groups: List[str] = field(default_factory=list)
    current_group_offset: int = 0
    current_color: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drawn_pixels": self.drawn_pixels,
            "completed_groups": list(self.completed_groups),
            "current_group_offset": self.current_group_offset,
            "current_color": self.current_color,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PaintProgress:
        return cls(
            drawn_pixels=data.get("drawn_pixels", 0),
            completed_groups=data.get("completed_groups", []),
            current_group_offset=data.get("current_group_offset", 0),
            current_color=data.get("current_color", ""),
        )

    @classmethod
    def from_pixel_offset(cls, plan: "PaintPlan", pixel_offset: int) -> "PaintProgress":
        """Construct a PaintProgress that resumes from the given pixel offset.

        Iterates through plan.groups to determine which groups are completed
        and the offset within the current group.
        """
        completed: List[str] = []
        remaining = pixel_offset
        current_color = ""
        current_group_offset = 0

        for group in plan.groups:
            group_size = len(group.coords)
            if remaining >= group_size:
                completed.append(group.group_key)
                remaining -= group_size
            else:
                current_color = group.group_key
                current_group_offset = remaining
                break

        return cls(
            drawn_pixels=pixel_offset,
            completed_groups=completed,
            current_group_offset=current_group_offset,
            current_color=current_color,
        )


class PaintSession:
    """Painting runtime that drives canvas drawing via calibrated screen coordinates."""

    def __init__(
        self,
        canvas: CanvasCalibration,
        palette: PaletteCalibration,
        toolbar: ToolbarCalibration,
        backend: InputBackend,
    ) -> None:
        self.canvas = canvas
        self.palette = palette
        self.toolbar = toolbar
        self.backend = backend

        self.plan: Optional[PaintPlan] = None
        self.is_running = False
        self.is_paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially

        # Progress tracking
        self._progress = PaintProgress()
        self.delay_ms = SPEED_PRESETS["normal"]

        # Callbacks (called from worker thread)
        self.on_progress: Optional[Callable[[int, int], None]] = None
        self.on_color_change: Optional[Callable[[str, int, int], None]] = None
        self.on_finished: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def load_plan(self, plan: PaintPlan) -> None:
        self.plan = plan

    def set_speed(self, preset_name: str) -> None:
        if preset_name in SPEED_PRESETS:
            self.delay_ms = SPEED_PRESETS[preset_name]

    def start(self, resume_progress: Optional[PaintProgress] = None) -> None:
        if self.is_running:
            return
        if not self.canvas.calibrated:
            if self.on_error:
                self.on_error("画布尚未标定！")
            return
        if not self.palette.calibrated:
            if self.on_error:
                self.on_error("调色板尚未标定！")
            return
        if not self.plan or self.plan.total_pixels == 0:
            if self.on_error:
                self.on_error("像素数据为空！")
            return

        self.is_running = True
        self.is_paused = False
        self._stop_event.clear()
        self._pause_event.set()

        if resume_progress:
            self._progress = resume_progress
        else:
            self._progress = PaintProgress()

        threading.Thread(target=self._paint_loop, daemon=True).start()

    def pause(self) -> None:
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self._pause_event.clear()

    def resume(self) -> None:
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._pause_event.set()

    def stop(self) -> PaintProgress:
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused
        self.is_running = False
        self.is_paused = False
        return PaintProgress(
            drawn_pixels=self._progress.drawn_pixels,
            completed_groups=list(self._progress.completed_groups),
            current_group_offset=self._progress.current_group_offset,
            current_color=self._progress.current_color,
        )

    def get_progress(self) -> PaintProgress:
        return PaintProgress(
            drawn_pixels=self._progress.drawn_pixels,
            completed_groups=list(self._progress.completed_groups),
            current_group_offset=self._progress.current_group_offset,
            current_color=self._progress.current_color,
        )

    # ------------------------------------------------------------------ #
    #  Private helpers                                                    #
    # ------------------------------------------------------------------ #

    def _wait_if_paused(self) -> None:
        self._pause_event.wait()

    @staticmethod
    def _jittered_delay(base_sec: float) -> None:
        jitter = base_sec * random.uniform(-0.25, 0.25)
        time.sleep(max(0.005, base_sec + jitter))

    def _navigate_to_color(self, group_key: str) -> None:
        """Select color by *group_key* (format ``"group_idx-color_idx"``)."""
        if "-" not in group_key:
            return
        g_idx_s, c_idx_s = group_key.split("-")
        g_idx, c_idx = int(g_idx_s), int(c_idx_s)

        # Switch group
        self._switch_to_group(g_idx)

        # Click color block
        if c_idx in self.palette.color_blocks:
            bx, by = self.palette.color_blocks[c_idx]
            self.backend.click(bx, by)
            time.sleep(0.35)

    def _reset_palette(self) -> None:
        """Reset palette to group 0 by clicking *left_tab* 13 times."""
        if not self.palette.left_tab:
            return
        for _ in range(13):
            self.backend.click(self.palette.left_tab[0], self.palette.left_tab[1])
            time.sleep(0.1)
        self.palette.current_group_idx = 0
        time.sleep(0.5)

    def _switch_to_group(self, target_idx: int) -> None:
        """Switch palette to *target_idx* via relative page flipping."""
        if target_idx == self.palette.current_group_idx:
            return
        diff = target_idx - self.palette.current_group_idx
        if diff > 0 and self.palette.right_tab:
            for _ in range(diff):
                self.backend.click(self.palette.right_tab[0], self.palette.right_tab[1])
                time.sleep(0.3)
        elif diff < 0 and self.palette.left_tab:
            for _ in range(abs(diff)):
                self.backend.click(self.palette.left_tab[0], self.palette.left_tab[1])
                time.sleep(0.3)
        self.palette.current_group_idx = target_idx
        time.sleep(0.2)

    def _switch_tool(self, tool: str) -> None:
        """Switch to ``'brush'`` or ``'bucket'`` tool."""
        if tool == "brush" and self.toolbar.brush:
            self.backend.click(self.toolbar.brush[0], self.toolbar.brush[1], press_duration=0.02)
            time.sleep(0.15)
        elif tool == "bucket" and self.toolbar.bucket:
            self.backend.click(self.toolbar.bucket[0], self.toolbar.bucket[1], press_duration=0.02)
            time.sleep(0.15)

    def _click_points(
        self,
        points: List[Tuple[int, int]],
        delay_sec: float,
    ) -> Tuple[bool, int]:
        painted_count = 0
        for px, py in points:
            self._wait_if_paused()
            if self._stop_event.is_set():
                return True, painted_count

            screen_x, screen_y = self.canvas.get_screen_pos(px, py)
            self.backend.click(screen_x, screen_y, press_duration=0.015)
            painted_count += 1

            self._progress.drawn_pixels += 1
            if self.on_progress:
                self.on_progress(self._progress.drawn_pixels, self.plan.total_pixels)

            self._jittered_delay(delay_sec)

        return False, painted_count

    def _click_points_with_left_bias(
        self,
        points: List[Tuple[int, int]],
        delay_sec: float,
    ) -> bool:
        for px, py in points:
            self._wait_if_paused()
            if self._stop_event.is_set():
                return True
            screen_x, screen_y = self.canvas.get_screen_pos(px, py)
            self.backend.click(screen_x - 1, screen_y, press_duration=0.015)
            self._jittered_delay(delay_sec)
            self._wait_if_paused()
            if self._stop_event.is_set():
                return True
            self.backend.click(screen_x, screen_y, press_duration=0.015)
            self._progress.drawn_pixels += 1
            if self.on_progress:
                self.on_progress(self._progress.drawn_pixels, self.plan.total_pixels)
            self._jittered_delay(delay_sec)
        return False

    def _paint_points_with_segments(
        self,
        points: List[Tuple[int, int]],
        delay_sec: float,
        *,
        click_startpoint: bool,
        click_endpoint: bool,
    ) -> Tuple[bool, int]:
        """Paint points without dragging.

        Drag-based painting has been disabled. We keep this method for call-site
        compatibility, but it simply clicks points sequentially.
        """
        _ = (click_startpoint, click_endpoint)
        return self._click_points(points, delay_sec)

    # ------------------------------------------------------------------ #
    #  Painting strategies                                                #
    # ------------------------------------------------------------------ #

    def _paint_group_sequential(
        self,
        group: PaintGroup,
        start_offset: int,
        delay_sec: float,
    ) -> bool:
        """Paint a group by clicking points sequentially. Returns ``True`` if stopped."""
        remaining_points = group.coords[start_offset:]
        if not remaining_points:
            return False

        stopped, painted_count = self._click_points(remaining_points, delay_sec)
        if stopped:
            self._progress.current_group_offset = start_offset + painted_count
            return True
        return False

    def _paint_group_with_bucket(
        self,
        group: PaintGroup,
        delay_sec: float,
    ) -> bool:
        """Paint using bucket-fill optimisation.  Returns ``True`` if stopped."""
        from heartopia_app.domain.paint_algorithms import (
            classify_boundary_interior,
            find_4connected_subregions,
            find_connected_components,
            shrink_interior_away_from_boundary,
            snake_sort,
        )

        components = find_connected_components(group.coords)
        current_tool = "brush"
        self._switch_tool("brush")

        for component in components:
            if self._stop_event.is_set():
                return True

            if len(component) < BUCKET_FILL_MIN_AREA:
                # Small component — brush only
                if current_tool != "brush":
                    self._switch_tool("brush")
                    current_tool = "brush"
                sorted_comp = snake_sort(component)
                stopped, _ = self._click_points(sorted_comp, delay_sec)
                if stopped:
                    return True
            else:
                # Large component — boundary brush + interior bucket
                boundary, interior = classify_boundary_interior(
                    component,
                    group.group_key,
                    self.plan.pixel_color_map,
                    self.plan.grid_width,
                    self.plan.grid_height,
                )
                safe_interior = shrink_interior_away_from_boundary(boundary, interior)

                # Draw boundary with brush
                if current_tool != "brush":
                    self._switch_tool("brush")
                    current_tool = "brush"
                stopped, _ = self._click_points(boundary, delay_sec)
                if stopped:
                    return True

                # Paint ring pixels (between boundary and safe_interior) with brush
                safe_set = set(safe_interior)
                ring = [p for p in interior if p not in safe_set]
                if ring:
                    stopped, _ = self._click_points(ring, delay_sec)
                    if stopped:
                        return True

                # Fill interior with bucket (large sub-regions) or brush (small ones)
                if safe_interior:
                    interior_regions = find_4connected_subregions(safe_interior)

                    # Small sub-regions: brush click (bucket unreliable on tiny areas)
                    small = [r for r in interior_regions if len(r) < 4]
                    large = [r for r in interior_regions if len(r) >= 4]

                    if small:
                        if current_tool != "brush":
                            self._switch_tool("brush")
                            current_tool = "brush"
                        for region in small:
                            stopped, _ = self._click_points(region, delay_sec)
                            if stopped:
                                return True

                    # Large sub-regions: bucket fill with left-bias double click
                    if large:
                        self._switch_tool("bucket")
                        current_tool = "bucket"
                        for region in large:
                            self._wait_if_paused()
                            if self._stop_event.is_set():
                                return True
                            fill_px, fill_py = region[0]
                            screen_x, screen_y = self.canvas.get_screen_pos(fill_px, fill_py)
                            self.backend.click(screen_x - 1, screen_y, press_duration=0.015)
                            self._jittered_delay(delay_sec)
                            self._wait_if_paused()
                            if self._stop_event.is_set():
                                return True
                            self.backend.click(screen_x, screen_y, press_duration=0.015)
                            self._progress.drawn_pixels += len(region)
                            if self.on_progress:
                                self.on_progress(self._progress.drawn_pixels, self.plan.total_pixels)
                            self._jittered_delay(delay_sec * 2)

        # Restore brush before leaving
        if current_tool != "brush":
            self._switch_tool("brush")
        return False

    # ------------------------------------------------------------------ #
    #  Main loop                                                          #
    # ------------------------------------------------------------------ #

    def _paint_loop(self) -> None:
        """Main paint loop running in worker thread."""
        try:
            time.sleep(1)  # buffer for user to switch to game window
            self._reset_palette()
            delay_sec = self.delay_ms / 1000.0

            # Determine bucket mode availability
            bucket_mode = self.toolbar.calibrated

            for color_idx, group in enumerate(self.plan.groups):
                group_key = group.group_key

                # Skip completed groups (for resume)
                if group_key in self._progress.completed_groups:
                    continue

                self._wait_if_paused()
                if self._stop_event.is_set():
                    break

                self._progress.current_color = group_key
                if self.on_color_change:
                    self.on_color_change(group_key, color_idx + 1, len(self.plan.groups))

                # Select color
                self._navigate_to_color(group_key)
                time.sleep(0.15)

                start_offset = (
                    self._progress.current_group_offset
                    if group_key not in self._progress.completed_groups
                    else 0
                )
                self._progress.current_group_offset = 0  # only first incomplete group uses offset

                if bucket_mode and start_offset == 0:
                    stopped = self._paint_group_with_bucket(group, delay_sec)
                else:
                    stopped = self._paint_group_sequential(group, start_offset, delay_sec)

                if stopped:
                    break

                self._progress.completed_groups.append(group_key)

        except Exception as e:
            if self.on_error:
                self.on_error(f"绘画过程中出错: {e}")
        finally:
            self.is_running = False
            if not self._stop_event.is_set() and self.on_finished:
                self.on_finished()
