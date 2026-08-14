import logging
import time

from app.db import SessionLocal
from app.outbox import process_pending_outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    while True:
        with SessionLocal() as db:
            processed = process_pending_outbox(db)
        if processed:
            logger.info("Procesados %s emails de outbox", processed)
        time.sleep(5)


if __name__ == "__main__":
    main()
