"""
Celery worker configuration and startup.
"""

from celery import Celery
import os

# Initialize Celery app
celery_app = Celery('venue_scraper')

# Configure Celery from environment variables
celery_app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    beat_schedule={
        'process-pending-venue-tasks': {
            'task': 'process_pending_tasks',
            'schedule': 10.0,  # Every 10 seconds
        },
    },
)

# Import tasks to register them
from tasks import scrape_venue_task, process_pending_tasks

if __name__ == '__main__':
    celery_app.start()

