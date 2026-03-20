"""RetailIQ Marketplace Logistics."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _tracking_seed(tracking_number: str) -> int:
    digest = hashlib.sha256(tracking_number.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def get_tracking_events(tracking_number: str) -> list[dict]:
    """Return deterministic tracking milestones for a shipment."""
    if not tracking_number:
        return []

    logger.info("Tracking lookup for %s", tracking_number)
    seed = _tracking_seed(tracking_number)
    now = datetime.now(timezone.utc)

    providers = ["DHL", "FedEx", "BlueDart", "UPS", "Aramex"]
    hubs = ["Origin Hub", "Sort Center", "Regional Hub", "Last-Mile Depot", "Destination Hub"]
    statuses = [
        "Shipment created",
        "Picked up by carrier",
        "In transit",
        "Out for delivery",
        "Delivered",
    ]

    provider = providers[seed % len(providers)]
    progress = min(len(statuses), 2 + seed % len(statuses))

    events = []
    for idx in range(progress):
        timestamp = now - timedelta(hours=(progress - idx) * 6 + (seed % 3))
        event = {
            "status": statuses[idx],
            "location": hubs[idx],
            "timestamp": timestamp.isoformat(),
            "provider": provider,
        }
        if idx == progress - 1 and statuses[idx] == "Delivered":
            event["delivered"] = True
        events.append(event)

    if progress < len(statuses):
        events.append(
            {
                "status": statuses[progress],
                "location": hubs[progress],
                "timestamp": (now + timedelta(hours=6)).isoformat(),
                "provider": provider,
                "eta": (now + timedelta(days=1 + seed % 3)).date().isoformat(),
            }
        )

    return events
