"""RetailIQ NLP Recommender."""

import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app import db

logger = logging.getLogger(__name__)


def _rows(sql: str, params: dict):
    return db.session.execute(text(sql), params).fetchall()


def get_ai_recommendations(user_id, store_id: int) -> list:
    """Return deterministic retail recommendations derived from store data."""
    logger.info("Recommendations requested for user %s store %s", user_id, store_id)

    recommendations: list[dict] = []
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)

    low_stock_rows = _rows(
        """
        SELECT product_id, name, current_stock, reorder_level
        FROM products
        WHERE store_id = :sid AND is_active = TRUE AND current_stock <= reorder_level
        ORDER BY (reorder_level - current_stock) DESC, product_id ASC
        LIMIT 5
        """,
        {"sid": store_id},
    )
    for row in low_stock_rows:
        recommendations.append(
            {
                "type": "restock",
                "priority": "high",
                "product_id": row.product_id,
                "title": f"Restock {row.name}",
                "description": (
                    f"Current stock is {float(row.current_stock or 0):.0f}; "
                    f"reorder level is {float(row.reorder_level or 0):.0f}."
                ),
                "confidence": 0.95,
            }
        )

    top_products = _rows(
        """
        SELECT d.product_id, p.name, SUM(d.revenue) AS total_rev, SUM(d.units_sold) AS total_units
        FROM daily_sku_summary d
        JOIN products p ON p.product_id = d.product_id
        WHERE d.store_id = :sid AND d.date >= :month_start
        GROUP BY d.product_id, p.name
        ORDER BY total_rev DESC, d.product_id ASC
        LIMIT 5
        """,
        {"sid": store_id, "month_start": month_start},
    )
    for row in top_products:
        recommendations.append(
            {
                "type": "promote",
                "priority": "medium",
                "product_id": row.product_id,
                "title": f"Promote {row.name}",
                "description": (
                    f"This SKU generated ₹{float(row.total_rev or 0):,.2f} revenue this month "
                    f"across {float(row.total_units or 0):.0f} units."
                ),
                "confidence": 0.9,
            }
        )

    pricing_rows = _rows(
        """
        SELECT product_id, name, cost_price, selling_price
        FROM products
        WHERE store_id = :sid AND is_active = TRUE AND cost_price IS NOT NULL AND selling_price IS NOT NULL
        ORDER BY product_id ASC
        """,
        {"sid": store_id},
    )
    for row in pricing_rows:
        cost = float(row.cost_price or 0)
        price = float(row.selling_price or 0)
        if not price:
            continue
        margin_pct = ((price - cost) / price) * 100 if price else 0
        if margin_pct < 15:
            recommendations.append(
                {
                    "type": "price_review",
                    "priority": "medium",
                    "product_id": row.product_id,
                    "title": f"Review pricing for {row.name}",
                    "description": f"Margin is only {margin_pct:.1f}%; consider a price increase.",
                    "confidence": 0.82,
                }
            )
            break

    if not recommendations:
        recommendations.append(
            {
                "type": "status",
                "priority": "low",
                "product_id": None,
                "title": "No urgent recommendations",
                "description": "Inventory, sales, and pricing signals are currently balanced.",
                "confidence": 0.6,
            }
        )

    return recommendations
