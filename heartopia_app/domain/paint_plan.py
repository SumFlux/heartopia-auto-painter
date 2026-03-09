from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


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
