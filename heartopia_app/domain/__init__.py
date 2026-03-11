from .palette import (
    CANVAS_BACKGROUND_COLORS,
    COLOR_GROUPS,
    COLOR_ID_MAP,
    FLAT_COLORS,
    GROUP_SIZES,
    HEX_TO_GROUP,
    PALETTE_RGB,
    TOTAL_GROUPS,
    find_closest_color,
    get_closest_color_group,
    hex_to_rgb,
)
from .pixel_data import Pixel, PixelData
from .conversion import ConversionRequest, ConversionResult, GRID_DIMENSIONS, PixelArtConverter
from .calibration import (
    CanvasCalibration,
    PaletteCalibration,
    ToolbarCalibration,
)
from .paint_plan import PaintGroup, PaintPlan, build_paint_plan
from .paint_algorithms import (
    snake_sort,
    find_connected_components,
    classify_boundary_interior,
    find_4connected_subregions,
    build_border_points,
    detect_canvas_markers,
)
