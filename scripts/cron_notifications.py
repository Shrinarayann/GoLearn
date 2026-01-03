"""
Standalone script to be run as a cron job.
Checks for due cards and sends push notifications to users.
"""

import sys
import os
import asyncio
import logging

# Add the project root to the beginning of sys.path to ensure we import the local 'app' package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.notification_service import notification_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/cron_notifications.log")
    ]
)
logger = logging.getLogger("cron_notifications")

async def main():
    logger.info("Starting notification cron job...")
    try:
        summary = await notification_service.notify_users_about_due_cards()
        logger.info(f"Cron job completed: {summary}")
    except Exception as e:
        logger.error(f"Cron job failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
