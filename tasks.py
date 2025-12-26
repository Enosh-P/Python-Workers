"""
Celery tasks for venue scraping.
"""

import logging
import time
from scraper import scrape_venue_page
from llm_extractor import extract_venue_data
from db import find_pending_tasks, update_task_status, check_cancel_flag, create_venue_item, get_db_connection
import psycopg2.extras

logger = logging.getLogger(__name__)

# Import Celery app from worker module
# Note: This import is safe now that worker.py no longer imports tasks (breaking the circular dependency)
# The celery_app will always exist in worker.py, even if Celery is disabled
from worker import celery_app


def _scrape_venue_task_impl(task_id: str):
    """
    Core implementation of venue scraping task.
    This is the actual work - can be called directly or via Celery wrapper.
    
    Args:
        task_id: The ID of the scraping task
    """
    try:
        logger.info(f"Starting venue scraping task: {task_id}")
        
        # Check cancel flag before starting
        if check_cancel_flag(task_id):
            logger.info(f"Task {task_id} was canceled before processing")
            update_task_status(task_id, 'canceled')
            return
        
        # Update status to processing
        update_task_status(task_id, 'processing')
        
        # Get task details from database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM venue_scraping_tasks WHERE id = %s", (task_id,))
        task = cur.fetchone()
        cur.close()
        conn.close()
        
        if not task:
            logger.error(f"Task {task_id} not found")
            update_task_status(task_id, 'failed', error_message="Task not found in database")
            return
        
        venue_url = task['venue_url']
        space_id = task['space_id']
        
        # Check cancel flag again
        if check_cancel_flag(task_id):
            logger.info(f"Task {task_id} was canceled")
            update_task_status(task_id, 'canceled')
            return
        
        # Step 1: Scrape the webpage
        logger.info(f"Scraping URL: {venue_url}")
        scraped_content = scrape_venue_page(venue_url)
        
        # Check cancel flag after scraping
        if check_cancel_flag(task_id):
            logger.info(f"Task {task_id} was canceled after scraping")
            update_task_status(task_id, 'canceled')
            return
        
        # Step 2: Extract structured data using LLM
        logger.info(f"Extracting structured data for task {task_id}")
        venue_data = extract_venue_data(scraped_content)
        
        if not venue_data:
            logger.error(f"Failed to extract venue data for task {task_id}")
            update_task_status(task_id, 'failed', error_message="Failed to extract venue data from webpage")
            return
        
        # Check cancel flag after extraction
        if check_cancel_flag(task_id):
            logger.info(f"Task {task_id} was canceled after extraction")
            update_task_status(task_id, 'canceled')
            return
        
        # Step 3: Update task with extracted data
        update_task_status(task_id, 'ready', venue_data=venue_data)
        
        # Step 4: Create venue_item in database
        logger.info(f"Creating venue item for space {space_id}")
        venue_item_id = create_venue_item(space_id, venue_data, venue_url)
        
        logger.info(f"Successfully completed task {task_id}, created venue item {venue_item_id}")
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        update_task_status(task_id, 'failed', error_message=str(e))


@celery_app.task(name='scrape_venue_task')
def scrape_venue_task(task_id: str):
    """
    Celery task wrapper for venue scraping.
    
    This is the Celery-decorated version that gets called when using .delay()
    It simply calls the implementation function.
    
    When Celery is disabled, call _scrape_venue_task_impl() directly instead.
    """
    return _scrape_venue_task_impl(task_id)


@celery_app.task(name='process_pending_tasks')
def process_pending_tasks():
    """
    DEPRECATED: Periodic task removed in favor of HTTP-triggered execution.
    
    This function is no longer used. Jobs are now triggered immediately via HTTP POST
    to the FastAPI /scrape-venue endpoint when a user submits a venue URL.
    
    This change eliminates the need for Celery Beat polling, reducing infrastructure costs.
    The worker now only runs when jobs are submitted, rather than running 24/7.
    
    Kept for backwards compatibility, but should not be called.
    """
    logger.warning("process_pending_tasks is deprecated - jobs are now HTTP-triggered")
    # Function body removed - this should never be called
    pass

