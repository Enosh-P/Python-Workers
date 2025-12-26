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
from worker import celery_app


@celery_app.task(name='scrape_venue_task')
def scrape_venue_task(task_id: str):
    """
    Celery task to scrape a venue URL and extract structured data.
    
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
        venue_item_id = create_venue_item(space_id, venue_data)
        
        logger.info(f"Successfully completed task {task_id}, created venue item {venue_item_id}")
        
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}")
        update_task_status(task_id, 'failed', error_message=str(e))


@celery_app.task(name='process_pending_tasks')
def process_pending_tasks():
    """
    Periodic task to check for pending scraping tasks and process them.
    This should be called by Celery Beat on a schedule (e.g., every 10 seconds).
    """
    try:
        logger.info("Checking for pending venue scraping tasks")
        
        # Find pending tasks
        pending_tasks = find_pending_tasks(limit=5)  # Process up to 5 at a time
        
        if not pending_tasks:
            logger.debug("No pending tasks found")
            return
        
        logger.info(f"Found {len(pending_tasks)} pending tasks")
        
        # Process each task
        for task in pending_tasks:
            task_id = task['id']
            # Dispatch the scraping task
            scrape_venue_task.delay(task_id)
            logger.info(f"Dispatched scraping task: {task_id}")
            
    except Exception as e:
        logger.error(f"Error processing pending tasks: {str(e)}")

