"""RetailIQ NLP Assistant."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app import db

from .router import resolve_intent
from .templates import TEMPLATES, format_currency, format_percentage, format_unit

logger = logging.getLogger(__name__)


def _compose_response(headline: str, detail: str, action: str) -> str:
    parts = [headline.strip() if headline else "Retail Intelligence"]
    if detail:
        parts.append(detail.strip())
    if action:
        parts.append(action.strip())
    return " ".join(part for part in parts if part)


def _fetch_row(sql: str, params: dict) -> object | None:
    return db.session.execute(text(sql), params).fetchone()


def handle_assistant_query(query_text: str, store_id: int) -> str:
    """Handle natural language query about store data using deterministic retail analytics."""
    logger.info("NLP query from store %s: %s", store_id, query_text)

    intent = resolve_intent(query_text)
    tmpl = TEMPLATES.get(intent, TEMPLATES["default"])
    headline = tmpl.get("headline", "Retail Intelligence")
    action = tmpl.get("action", tmpl.get("action_template", ""))
    detail = ""

    if intent == "forecast":
        row = _fetch_row(
            """
            SELECT SUM(forecast_value) AS fc, MAX(regime) AS reg
            FROM forecast_cache
            WHERE store_id = :sid AND forecast_date >= :start_date AND forecast_date < :end_date
            """,
            {
                "sid": store_id,
                "start_date": datetime.now(timezone.utc).date(),
                "end_date": datetime.now(timezone.utc).date() + timedelta(days=7),
            },
        )
        forecast_value = float(getattr(row, "fc", 0) or 0) if row else 0.0
        regime = getattr(row, "reg", "Stable") if row else "Stable"
        detail = tmpl["detail_template"].format(forecast=format_unit(forecast_value), regime=regime)
        action = tmpl.get("action", "").format(lead_time="standard") if tmpl.get("action") else ""

    elif intent == "inventory":
        row = _fetch_row(
            """
            SELECT p.product_id, p.name, p.current_stock, p.reorder_level,
                   (p.reorder_level - p.current_stock) AS deficit
            FROM products p
            WHERE p.store_id = :sid AND p.is_active = TRUE
              AND p.current_stock <= p.reorder_level
            ORDER BY deficit DESC
            LIMIT 1
            """,
            {"sid": store_id},
        )
        if row:
            detail = tmpl["detail_template"].format(
                stock=format_unit(float(getattr(row, "current_stock", 0) or 0)),
                reorder=format_unit(float(getattr(row, "reorder_level", 0) or 0)),
                deficit=format_unit(float(getattr(row, "deficit", 0) or 0)),
            )
        else:
            detail = "All products are above their reorder levels."
            action = "No restocking action required."

    elif intent == "revenue":
        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=7)
        rows = db.session.execute(
            text(
                """
                SELECT date, revenue FROM daily_store_summary
                WHERE store_id = :sid AND date >= :start_date AND date <= :today
                ORDER BY date ASC
                """
            ),
            {"sid": store_id, "start_date": start_date, "today": today},
        ).fetchall()
        today_rev = 0.0
        past_values = []
        for row in rows:
            if row.date == today:
                today_rev = float(row.revenue or 0)
            else:
                past_values.append(float(row.revenue or 0))
        ma_7d = sum(past_values) / len(past_values) if past_values else 0.0
        delta = ((today_rev - ma_7d) / ma_7d * 100) if ma_7d > 0 else 0.0
        detail = tmpl["detail_template"].format(revenue=format_currency(today_rev), ma_7d=format_currency(ma_7d))
        action = tmpl.get("action_template", "").format(delta_pct=format_percentage(delta))

    elif intent == "profit":
        row = _fetch_row(
            """
            SELECT AVG(CASE WHEN selling_price > 0
                        THEN (selling_price - cost_price) / selling_price * 100
                        ELSE 0 END) AS avg_margin,
                   COUNT(*) AS product_count
            FROM products
            WHERE store_id = :sid AND is_active = TRUE AND cost_price IS NOT NULL AND selling_price IS NOT NULL
            """,
            {"sid": store_id},
        )
        avg_margin = float(getattr(row, "avg_margin", 0) or 0) if row else 0.0
        detail = tmpl["detail_template"].format(margin=format_percentage(avg_margin))

    elif intent == "top_products":
        rows = db.session.execute(
            text(
                """
                SELECT d.product_id, p.name, SUM(d.revenue) AS total_rev, SUM(d.units_sold) AS total_units
                FROM daily_sku_summary d
                JOIN products p ON p.product_id = d.product_id
                WHERE d.store_id = :sid AND d.date >= :start_date
                GROUP BY d.product_id, p.name
                ORDER BY total_rev DESC, d.product_id ASC
                LIMIT 5
                """
            ),
            {"sid": store_id, "start_date": datetime.now(timezone.utc).date() - timedelta(days=30)},
        ).fetchall()
        if rows:
            detail = tmpl["detail_template"].format(
                value=", ".join(f"{row.name} ({format_currency(float(row.total_rev or 0))})" for row in rows)
            )
        else:
            detail = "No sales data available for the last 30 days."

    elif intent == "loyalty_summary":
        start_date = datetime.now(timezone.utc).replace(day=1)
        row = _fetch_row(
            """
            SELECT
                (SELECT COUNT(*) FROM customer_loyalty_accounts WHERE store_id = :sid) AS enrolled,
                (SELECT COALESCE(SUM(points), 0) FROM loyalty_transactions lt
                 JOIN customer_loyalty_accounts c ON c.id = lt.account_id
                 WHERE c.store_id = :sid AND lt.type = 'EARN' AND lt.created_at >= :start_date) AS issued,
                (SELECT COALESCE(SUM(points), 0) FROM loyalty_transactions lt
                 JOIN customer_loyalty_accounts c ON c.id = lt.account_id
                 WHERE c.store_id = :sid AND lt.type = 'REDEEM' AND lt.created_at >= :start_date) AS redeemed
            """,
            {"sid": store_id, "start_date": start_date},
        )
        enrolled = int(getattr(row, "enrolled", 0) or 0) if row else 0
        issued = float(getattr(row, "issued", 0) or 0) if row else 0.0
        redeemed = abs(float(getattr(row, "redeemed", 0) or 0)) if row else 0.0
        detail = tmpl["detail_template"].format(
            enrolled=enrolled, issued=format_unit(issued, "point"), redeemed=format_unit(redeemed, "point")
        )

    elif intent == "credit_overdue":
        row = _fetch_row(
            """
            SELECT COUNT(*) AS overdue_count, COALESCE(SUM(balance), 0) AS total_overdue
            FROM credit_ledger
            WHERE store_id = :sid AND balance > 0 AND updated_at < :cutoff
            """,
            {"sid": store_id, "cutoff": datetime.now(timezone.utc) - timedelta(days=30)},
        )
        count = int(getattr(row, "overdue_count", 0) or 0) if row else 0
        total_overdue = float(getattr(row, "total_overdue", 0) or 0) if row else 0.0
        detail = tmpl["detail_template"].format(count=count, total_overdue=format_currency(total_overdue))

    elif intent == "market_intelligence":
        try:
            from app.market_intelligence.engine import IntelligenceEngine

            summary = IntelligenceEngine.get_market_summary()
            alerts = summary.get("active_alerts", 0)
            status = "Elevated volatility" if alerts else "Stable conditions"
            detail = tmpl["detail_template"].format(status=status, active_alerts=alerts)
        except Exception:
            detail = "Unable to fetch real-time market intelligence at this moment."
            action = "Review pricing strategies based on current market trends."

    else:
        detail = tmpl["detail_template"].format(value="system baseline")

    return _compose_response(headline, detail, action)
