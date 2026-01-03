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

async def run_check():
    """Run a single notification check."""
    try:
        summary = await notification_service.notify_users_about_due_cards()
        if summary["users_notified"] > 0 or summary["errors"] > 0:
            logger.info(f"Notification check: {summary}")
        else:
            logger.info("No users with due cards found.")
    except Exception as e:
        logger.error(f"Check failed: {str(e)}", exc_info=True)

async def main():
    """Run notification checks daily at 9 AM."""
    from datetime import datetime, time, timedelta
    
    TARGET_HOUR = 9  # 9 AM
    TARGET_MINUTE = 0
    
    logger.info(f"Starting notification cron job (daily at {TARGET_HOUR}:00)...")
    logger.info("Press Ctrl+C to stop.")
    
    while True:
        now = datetime.now()
        target_time = now.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
        
        # If it's past 9 AM today, schedule for tomorrow
        if now >= target_time:
            target_time = target_time + timedelta(days=1)
        
        wait_seconds = (target_time - now).total_seconds()
        logger.info(f"Next notification check scheduled for {target_time.strftime('%Y-%m-%d %H:%M:%S')} (in {wait_seconds/3600:.1f} hours)")
        
        await asyncio.sleep(wait_seconds)
        
        logger.info("Running scheduled notification check...")
        await run_check()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Cron job stopped by user.")


