"""
Celery tasks for venue scraping and food/music/photographer/gift scraping.
"""

import logging
import time
from scraper import scrape_venue_page
from llm_extractor import extract_venue_data, extract_food_data, extract_music_data, extract_photographer_data, extract_gift_data
from db import (
    find_pending_tasks, update_task_status, check_cancel_flag, create_venue_item, get_db_connection,
    find_task, update_task, check_cancel_flag_generic, TASK_CONFIG
)
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


def _scrape_typed_task_impl(task_id: str, task_type: str, url_key: str, extractor_fn):
    """
    Generic implementation for food/music/photographer/gift scraping.
    Loads task, scrapes URL, extracts data, updates task with *_data and status='ready'.
    """
    try:
        logger.info(f"Starting {task_type} scraping task: {task_id}")
        if check_cancel_flag_generic(task_id, task_type):
            logger.info(f"Task {task_id} was canceled before processing")
            update_task(task_id, task_type, 'canceled')
            return
        update_task(task_id, task_type, 'processing')
        task = find_task(task_id, task_type)
        if not task:
            logger.error(f"Task {task_id} not found")
            update_task(task_id, task_type, 'failed', error_message="Task not found in database")
            return
        url = task.get(url_key)
        if not url:
            update_task(task_id, task_type, 'failed', error_message=f"Missing {url_key} in task")
            return
        if check_cancel_flag_generic(task_id, task_type):
            update_task(task_id, task_type, 'canceled')
            return
        logger.info(f"Scraping URL: {url}")
        scraped_content = scrape_venue_page(url)
        if check_cancel_flag_generic(task_id, task_type):
            update_task(task_id, task_type, 'canceled')
            return
        logger.info(f"Extracting {task_type} data for task {task_id}")
        data = extractor_fn(scraped_content)
        if not data:
            logger.error(f"Failed to extract {task_type} data for task {task_id}")
            update_task(task_id, task_type, 'failed', error_message=f"Failed to extract {task_type} data from webpage")
            return
        if check_cancel_flag_generic(task_id, task_type):
            update_task(task_id, task_type, 'canceled')
            return
        update_task(task_id, task_type, 'ready', data=data)
        logger.info(f"Successfully completed {task_type} task {task_id}")
    except Exception as e:
        logger.error(f"Error processing {task_type} task {task_id}: {str(e)}")
        update_task(task_id, task_type, 'failed', error_message=str(e))


def _scrape_food_task_impl(task_id: str):
    _scrape_typed_task_impl(task_id, 'food', 'food_url', extract_food_data)


def _scrape_music_task_impl(task_id: str):
    _scrape_typed_task_impl(task_id, 'music', 'music_url', extract_music_data)


def _scrape_photographer_task_impl(task_id: str):
    _scrape_typed_task_impl(task_id, 'photographer', 'photographer_url', extract_photographer_data)


def _scrape_gift_task_impl(task_id: str):
    """Gift scraping: runs scrape+extract and URL-only LLM in parallel, uses whichever succeeds (prefers scrape)."""
    from llm_extractor import _extract_gift_from_url
    import concurrent.futures
    try:
        logger.info(f"Starting gift scraping task: {task_id}")
        if check_cancel_flag_generic(task_id, 'gift'):
            update_task(task_id, 'gift', 'canceled')
            return
        update_task(task_id, 'gift', 'processing')
        task = find_task(task_id, 'gift')
        if not task:
            update_task(task_id, 'gift', 'failed', error_message="Task not found in database")
            return
        url = task.get('gift_url')
        if not url:
            update_task(task_id, 'gift', 'failed', error_message="Missing gift_url in task")
            return
        if check_cancel_flag_generic(task_id, 'gift'):
            update_task(task_id, 'gift', 'canceled')
            return

        def scrape_path():
            """Path A: scrape page then extract with LLM."""
            try:
                scraped = scrape_venue_page(url)
                result = extract_gift_data(scraped)
                if result:
                    logger.info(f"Scrape path succeeded for {url}")
                return result
            except Exception as e:
                logger.warning(f"Scrape path failed for {url}: {e}")
                return None

        def url_only_path():
            """Path B: send URL directly to LLM."""
            try:
                result = _extract_gift_from_url(url)
                if result:
                    result['product_url'] = result.get('product_url') or url
                    logger.info(f"URL-only path succeeded for {url}")
                return result
            except Exception as e:
                logger.warning(f"URL-only path failed for {url}: {e}")
                return None

        # Run both in parallel
        scrape_result = None
        url_result = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            scrape_future = executor.submit(scrape_path)
            url_future = executor.submit(url_only_path)
            try:
                scrape_result = scrape_future.result(timeout=60)
            except Exception as e:
                logger.warning(f"Scrape future error: {e}")
            try:
                url_result = url_future.result(timeout=60)
            except Exception as e:
                logger.warning(f"URL-only future error: {e}")

        # Prefer scrape result (richer data with images), fall back to URL-only
        data = scrape_result or url_result

        if check_cancel_flag_generic(task_id, 'gift'):
            update_task(task_id, 'gift', 'canceled')
            return

        if not data:
            update_task(task_id, 'gift', 'failed', error_message="Failed to extract gift data from URL")
            return

        update_task(task_id, 'gift', 'ready', data=data)
        logger.info(f"Successfully completed gift task {task_id}")
    except Exception as e:
        logger.error(f"Error processing gift task {task_id}: {str(e)}")
        update_task(task_id, 'gift', 'failed', error_message=str(e))


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

