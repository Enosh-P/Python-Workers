"""
Celery Beat schedule configuration for periodic tasks.
"""

from celery.schedules import crontab

# Schedule for processing pending venue scraping tasks
# Runs every 10 seconds
beat_schedule = {
    'process-pending-venue-tasks': {
        'task': 'process_pending_tasks',
        'schedule': 10.0,  # Every 10 seconds
    },
}

