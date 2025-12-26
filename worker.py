"""
Celery worker configuration (optional).

Celery is now optional - jobs are triggered via HTTP POST instead of Celery Beat polling.
This reduces infrastructure costs since the worker only runs when jobs are submitted.

Set ENABLE_CELERY=true to use Celery for concurrent task processing.
If disabled, tasks run directly in FastAPI (suitable for low traffic <5 users).
"""

from celery import Celery
import os

# Initialize Celery app
celery_app = Celery('venue_scraper')

# Configure Celery from environment variables
# Note: Beat schedule removed - jobs are now triggered via HTTP POST to FastAPI
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
    worker_concurrency=1,  # Low concurrency for cost efficiency (1-2 jobs at a time)
    # Beat schedule removed - replaced by HTTP-triggered execution
    # Jobs are triggered immediately when user submits URL via FastAPI endpoint
)

# Tasks are imported when needed to avoid circular imports
# The @celery_app.task decorator in tasks.py will register them automatically
# No need to import here since we're not using Celery Beat

if __name__ == '__main__':
    celery_app.start()

