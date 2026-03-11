from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import List, Sequence, Tuple

from PIL import Image, ImageDraw

from heartopia_app.domain.calibration import CanvasCalibration
from heartopia_app.domain.paint_plan import PaintPlan
from heartopia_app.domain.palette import CANVAS_BACKGROUND_COLORS, COLOR_GROUPS, find_closest_color, hex_to_rgb
from heartopia_app.domain.pixel_data import PixelData


RGB = Tuple[int, int, int]
Coord = Tuple[int, int]
BACKGROUND_HEX = "#a8978e"


def _group_key_to_hex(group_key: str) -> str:
    if "-" not in group_key:
        return BACKGROUND_HEX
    group_idx_str, color_idx_str = group_key.split("-", 1)
    group_idx = int(group_idx_str)
    color_idx = int(color_idx_str)
    return COLOR_GROUPS[group_idx][1][color_idx].lower()


def _color_distance_sq(rgb_a: RGB, rgb_b: RGB) -> int:
    dr = rgb_a[0] - rgb_b[0]
    dg = rgb_a[1] - rgb_b[1]
    db = rgb_a[2] - rgb_b[2]
    return dr * dr + dg * dg + db * db


def _is_light_color(hex_color: str) -> bool:
    if hex_color in CANVAS_BACKGROUND_COLORS:
        return True
    r, g, b = hex_to_rgb(hex_color)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return luminance >= 220


@dataclass(frozen=True)
class CellObservation:
    coord: Coord
    screenshot_pos: Coord
    sampled_rgbs: List[RGB]
    median_rgb: RGB
    observed_hex: str
    observed_color_id: str
    observed_vote_count: int
    observed_vote_ratio: float
    min_palette_distance_sq: int
    background_like: bool
    stable: bool


@dataclass(frozen=True)
class VerificationMismatch:
    coord: Coord
    target_group_key: str
    target_hex: str
    observed_hex: str
    observed_color_id: str
    classification: str
    reason: str
    screenshot_pos: Coord


@dataclass
class VerificationResult:
    observed_pixel_data: PixelData
    total_target_pixels: int
    matched_count: int
    mismatch_count: int
    missing_background_like_count: int
    wrong_palette_color_count: int
    uncertain_count: int
    mismatches: List[VerificationMismatch] = field(default_factory=list)

    @property
    def repair_candidates(self) -> List[VerificationMismatch]:
        return [
            mismatch
            for mismatch in self.mismatches
            if mismatch.classification == "missing_background_like"
        ]

    def summary_text(self) -> str:
        return (
            f"总目标像素 {self.total_target_pixels}，匹配 {self.matched_count}，"
            f"mismatch {self.mismatch_count}，漏白点候选 {self.missing_background_like_count}，"
            f"疑似错色 {self.wrong_palette_color_count}，不确定 {self.uncertain_count}"
        )


def sample_canvas_cell(
    image: Image.Image,
    window_rect: Tuple[int, int, int, int],
    canvas: CanvasCalibration,
    x: int,
    y: int,
    *,
    sample_radius: int = 1,
) -> CellObservation:
    screen_x, screen_y = canvas.get_screen_pos(x, y)
    local_x = screen_x - window_rect[0]
    local_y = screen_y - window_rect[1]

    width, height = image.size
    rgb_image = image.convert("RGB")
    pixels = rgb_image.load()

    sampled_rgbs: List[RGB] = []
    quantized_ids: List[str] = []
    quantized_hexes: List[str] = []
    min_palette_distance_sq = 10 ** 9

    for dy in range(-sample_radius, sample_radius + 1):
        for dx in range(-sample_radius, sample_radius + 1):
            sx = min(max(local_x + dx, 0), width - 1)
            sy = min(max(local_y + dy, 0), height - 1)
            rgb = tuple(int(v) for v in pixels[sx, sy])
            sampled_rgbs.append(rgb)
            closest_hex, closest_id = find_closest_color(*rgb)
            quantized_hexes.append(closest_hex)
            quantized_ids.append(closest_id)
            palette_rgb = hex_to_rgb(closest_hex)
            min_palette_distance_sq = min(min_palette_distance_sq, _color_distance_sq(rgb, palette_rgb))

    median_rgb = (
        int(median([rgb[0] for rgb in sampled_rgbs])),
        int(median([rgb[1] for rgb in sampled_rgbs])),
        int(median([rgb[2] for rgb in sampled_rgbs])),
    )
    median_hex, median_color_id = find_closest_color(*median_rgb)

    vote_counter = Counter(quantized_ids)
    observed_color_id, observed_vote_count = vote_counter.most_common(1)[0]
    observed_hex = median_hex
    for idx, qid in enumerate(quantized_ids):
        if qid == observed_color_id:
            observed_hex = quantized_hexes[idx]
            break

    dominant_ratio = observed_vote_count / len(sampled_rgbs)
    channel_ranges = [max(channel) - min(channel) for channel in zip(*sampled_rgbs)]
    stable = dominant_ratio >= 0.55 and max(channel_ranges) <= 72

    background_refs = [hex_to_rgb(color) for color in CANVAS_BACKGROUND_COLORS if color.startswith("#")]
    background_dist_sq = min((_color_distance_sq(median_rgb, ref) for ref in background_refs), default=10 ** 9)
    brightness = sum(median_rgb) / 3
    chroma = max(median_rgb) - min(median_rgb)
    background_like = background_dist_sq <= 45 * 45 or (brightness >= 244 and chroma <= 18)

    return CellObservation(
        coord=(x, y),
        screenshot_pos=(local_x, local_y),
        sampled_rgbs=sampled_rgbs,
        median_rgb=median_rgb,
        observed_hex=observed_hex,
        observed_color_id=observed_color_id,
        observed_vote_count=observed_vote_count,
        observed_vote_ratio=dominant_ratio,
        min_palette_distance_sq=min_palette_distance_sq,
        background_like=background_like,
        stable=stable,
    )


def verify_painted_canvas(
    image: Image.Image,
    window_rect: Tuple[int, int, int, int],
    canvas: CanvasCalibration,
    plan: PaintPlan,
    *,
    ratio: str = "",
    level: int = 0,
    sample_radius: int = 1,
) -> VerificationResult:
    observed_grid: List[List[str]] = [
        [BACKGROUND_HEX for _ in range(plan.grid_width)]
        for _ in range(plan.grid_height)
    ]
    mismatches: List[VerificationMismatch] = []
    matched_count = 0
    missing_background_like_count = 0
    wrong_palette_color_count = 0
    uncertain_count = 0

    total_target_pixels = len(plan.pixel_color_map)

    for y in range(plan.grid_height):
        for x in range(plan.grid_width):
            observation = sample_canvas_cell(
                image,
                window_rect,
                canvas,
                x,
                y,
                sample_radius=sample_radius,
            )
            observed_grid[y][x] = BACKGROUND_HEX if observation.background_like else observation.observed_hex

            target_group_key = plan.pixel_color_map.get((x, y))
            if target_group_key is None:
                continue

            target_hex = _group_key_to_hex(target_group_key)
            target_is_light = _is_light_color(target_hex)

            if observation.observed_color_id == target_group_key and observation.stable:
                matched_count += 1
                observed_grid[y][x] = observation.observed_hex
                continue

            if observation.background_like and not target_is_light:
                classification = "missing_background_like"
                reason = (
                    f"sample looks background-like (vote={observation.observed_vote_count}/"
                    f"{len(observation.sampled_rgbs)}, median={observation.median_rgb})"
                )
                missing_background_like_count += 1
                observed_grid[y][x] = BACKGROUND_HEX
            elif observation.stable and observation.min_palette_distance_sq <= 34 * 34:
                classification = "wrong_palette_color"
                reason = (
                    f"stable sampled color maps to {observation.observed_color_id} "
                    f"instead of {target_group_key}"
                )
                wrong_palette_color_count += 1
                observed_grid[y][x] = observation.observed_hex
            else:
                classification = "uncertain"
                reason = (
                    f"unstable sampling or palette distance too large "
                    f"(ratio={observation.observed_vote_ratio:.2f}, "
                    f"dist_sq={observation.min_palette_distance_sq})"
                )
                uncertain_count += 1
                observed_grid[y][x] = observation.observed_hex

            mismatches.append(
                VerificationMismatch(
                    coord=(x, y),
                    target_group_key=target_group_key,
                    target_hex=target_hex,
                    observed_hex=observation.observed_hex,
                    observed_color_id=observation.observed_color_id,
                    classification=classification,
                    reason=reason,
                    screenshot_pos=observation.screenshot_pos,
                )
            )

    observed_pixel_data = PixelData.from_pixel_grid(ratio=ratio, level=level, pixel_grid=observed_grid)
    mismatch_count = len(mismatches)
    return VerificationResult(
        observed_pixel_data=observed_pixel_data,
        total_target_pixels=total_target_pixels,
        matched_count=matched_count,
        mismatch_count=mismatch_count,
        missing_background_like_count=missing_background_like_count,
        wrong_palette_color_count=wrong_palette_color_count,
        uncertain_count=uncertain_count,
        mismatches=mismatches,
    )


def _estimate_marker_half_span(canvas: CanvasCalibration, plan: PaintPlan) -> int:
    step_candidates: List[int] = []

    if plan.grid_width > 1:
        left = canvas.get_screen_pos(0, 0)
        right = canvas.get_screen_pos(1, 0)
        step_candidates.append(abs(right[0] - left[0]))
        step_candidates.append(abs(right[1] - left[1]))
    if plan.grid_height > 1:
        top = canvas.get_screen_pos(0, 0)
        bottom = canvas.get_screen_pos(0, 1)
        step_candidates.append(abs(bottom[0] - top[0]))
        step_candidates.append(abs(bottom[1] - top[1]))

    step_candidates = [value for value in step_candidates if value > 0]
    if not step_candidates:
        return 5

    base_step = max(6, min(step_candidates))
    return max(4, min(12, int(base_step * 0.35)))


def build_annotated_verification_image(
    image: Image.Image,
    canvas: CanvasCalibration,
    plan: PaintPlan,
    result: VerificationResult,
) -> Image.Image:
    annotated = image.convert("RGBA")
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    marker_half_span = _estimate_marker_half_span(canvas, plan)

    styles = {
        "missing_background_like": ((255, 59, 48, 210), (255, 59, 48, 72)),
        "wrong_palette_color": ((255, 149, 0, 210), (255, 149, 0, 56)),
        "uncertain": ((255, 214, 10, 180), (255, 214, 10, 44)),
    }

    for mismatch in result.mismatches:
        center_x, center_y = mismatch.screenshot_pos
        outline_color, fill_color = styles.get(
            mismatch.classification,
            ((255, 59, 48, 210), (255, 59, 48, 72)),
        )
        left = max(0, center_x - marker_half_span)
        top = max(0, center_y - marker_half_span)
        right = min(annotated.width - 1, center_x + marker_half_span)
        bottom = min(annotated.height - 1, center_y + marker_half_span)

        draw.rectangle((left, top, right, bottom), outline=outline_color, width=2)
        draw.rectangle((left, top, right, bottom), fill=fill_color)
        draw.line((center_x - marker_half_span, center_y, center_x + marker_half_span, center_y), fill=outline_color, width=1)
        draw.line((center_x, center_y - marker_half_span, center_x, center_y + marker_half_span), fill=outline_color, width=1)

    return Image.alpha_composite(annotated, overlay).convert("RGB")


def build_repair_pixel_data(
    reference_pixel_data: PixelData,
    repair_candidates: Sequence[VerificationMismatch],
) -> PixelData:
    pixel_grid: List[List[str]] = [
        [BACKGROUND_HEX for _ in range(reference_pixel_data.grid_width)]
        for _ in range(reference_pixel_data.grid_height)
    ]
    for candidate in repair_candidates:
        x, y = candidate.coord
        pixel_grid[y][x] = candidate.target_hex
    return PixelData.from_pixel_grid(
        ratio=reference_pixel_data.ratio,
        level=reference_pixel_data.level,
        pixel_grid=pixel_grid,
    )
