from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Tuple

from .paint_algorithms import snake_sort
from .palette import CANVAS_BACKGROUND_COLORS, get_closest_color_group

if TYPE_CHECKING:
    from .pixel_data import PixelData


@dataclass
class PaintGroup:
    group_key: str
    coords: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class PaintPlan:
    total_pixels: int
    grid_width: int
    grid_height: int
    groups: List[PaintGroup] = field(default_factory=list)
    pixel_color_map: Dict[Tuple[int, int], str] = field(default_factory=dict)

    @property
    def sorted_group_keys(self) -> List[str]:
        return [group.group_key for group in self.groups]

    def group_lookup(self) -> Dict[str, PaintGroup]:
        return {group.group_key: group for group in self.groups}


def build_paint_plan(pixel_data: PixelData) -> PaintPlan:
    """Build a :class:`PaintPlan` from *pixel_data*.

    This is the pure-function equivalent of the old
    ``PaintEngine.load_pixel_data()`` method.
    """
    color_groups: Dict[str, List[Tuple[int, int]]] = {}
    pixel_color_map: Dict[Tuple[int, int], str] = {}
    total_pixels = 0

    for p in pixel_data.pixels:
        hex_color = p.color
        color_id = p.color_id

        # skip background
        if hex_color in CANVAS_BACKGROUND_COLORS or hex_color == "transparent":
            continue

        if color_id:
            group_key = color_id
        else:
            g_idx, c_idx = get_closest_color_group(hex_color)
            group_key = f"{g_idx}-{c_idx}"

        color_groups.setdefault(group_key, []).append((p.x, p.y))
        pixel_color_map[(p.x, p.y)] = group_key
        total_pixels += 1

    # snake-sort each group
    for key in color_groups:
        color_groups[key] = snake_sort(color_groups[key])

    # sort groups by group index to minimise page-flipping
    def _sort_key(g_key: str) -> int:
        if "-" in g_key:
            return int(g_key.split("-")[0])
        return 999

    sorted_keys = sorted(color_groups.keys(), key=_sort_key)

    groups = [
        PaintGroup(group_key=key, coords=color_groups[key])
        for key in sorted_keys
    ]

    return PaintPlan(
        total_pixels=total_pixels,
        grid_width=pixel_data.grid_width,
        grid_height=pixel_data.grid_height,
        groups=groups,
        pixel_color_map=pixel_color_map,
    )
