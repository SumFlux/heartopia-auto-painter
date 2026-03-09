from __future__ import annotations

from pathlib import Path

from heartopia_app.domain import ConversionRequest, ConversionResult, PixelArtConverter, PixelData


class ConversionService:
    def convert_image(self, image_path: str | Path, request: ConversionRequest) -> ConversionResult:
        converter = PixelArtConverter(ratio=request.ratio, level=request.level)
        return converter.convert(str(image_path), request)

    def load_pixel_data(self, file_path: str | Path) -> PixelData:
        return PixelData.from_json_file(file_path)

    def export_json(self, pixel_data: PixelData, output_path: str | Path) -> None:
        pixel_data.save_json(output_path)

    def export_csv(self, pixel_data: PixelData, output_path: str | Path) -> None:
        pixel_data.export_csv(output_path)
