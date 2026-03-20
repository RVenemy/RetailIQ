import logging
import os

from flask import current_app

from .shelf_analyzer import ShelfAnalyzer

logger = logging.getLogger(__name__)

# Cache analyzer instance to avoid reloading YOLO weights for every request
_analyzer = None


def get_analyzer():
    global _analyzer
    if _analyzer is None:
        model_path = os.path.join(current_app.root_path, "..", "yolov8n.pt")
        _analyzer = ShelfAnalyzer(model_path=model_path)
    return _analyzer


def process_shelf_scan(image_url: str) -> dict:
    """Analyse shelf image and detect products / gaps."""
    logger.info("Shelf scan requested for: %s", image_url)

    analyzer = get_analyzer()

    # Simple logic to handle remote vs local
    # If it's a URL (http), we might need to download it first.
    # For now, we assume local path or that YOLO/PIL can handle it.

    result = analyzer.analyze_image(image_url)

    if "error" in result:
        return {
            "status": "error",
            "message": result["error"],
            "image_url": image_url,
            "detected_products": [],
            "out_of_stock_slots": [],
            "compliance_score": 0,
        }

    return {
        "status": "success",
        "message": "Shelf analysis complete.",
        "image_url": image_url,
        "detected_products": result["detected_products"],
        "out_of_stock_slots": result["out_of_stock_slots"],
        "compliance_score": result["compliance_score"],
        "model_info": result.get("model_info"),
    }
