"""Background retention worker (runs in its own container).

On a daily cycle it:
  * flags recordings whose 3-month retention period has passed (G2-141), and
  * creates reminder notifications for recordings approaching deletion (G2-142).

The actual logic lives in app.services.retention_service so it stays unit
testable; this module is just the scheduling loop.
"""
import logging
import os
import time

from app.database import SessionLocal
from app.services import retention_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [retention-worker] %(levelname)s %(message)s",
)
logger = logging.getLogger("retention-worker")

# How often to run the retention sweep, in seconds (default: daily).
RUN_INTERVAL_SECONDS = int(os.getenv("WORKER_INTERVAL_SECONDS", str(24 * 60 * 60)))


def run_once() -> None:
    db = SessionLocal()
    try:
        # Order: warn (reminders) -> flag (mark expired) -> purge (delete expired).
        reminders = retention_service.create_deletion_reminders(db)
        flagged = retention_service.flag_expired_recordings(db)
        purged = retention_service.purge_expired_recordings(db)
        gen_reminders = retention_service.create_generation_retention_reminders(db)
        logger.info(
            "retention sweep: reminders=%d flagged=%d purged=%d gen_reminders=%d",
            reminders,
            flagged,
            purged,
            gen_reminders,
        )
    except Exception:  # noqa: BLE001 - keep the loop alive
        logger.exception("retention sweep failed")
    finally:
        db.close()


def main() -> None:
    logger.info("retention worker started (interval=%ss)", RUN_INTERVAL_SECONDS)
    while True:
        run_once()
        time.sleep(RUN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()