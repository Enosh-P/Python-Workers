"""
FastAPI app for HTTP-triggered venue scraping.
Jobs are triggered via HTTP POST instead of Celery Beat polling, reducing costs.

Architecture:
- Next.js creates task in DB, then calls this endpoint via HTTP
- This endpoint immediately processes the task (directly or via optional Celery)
- No polling loops or schedulers needed - worker only runs when jobs are submitted
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import uvicorn
import logging
import sys

# Configure logging to output to stdout/stderr (visible in Docker logs)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Venue Scraper Worker", version="2.0.0")

# Check if Celery is enabled (optional for cost efficiency)
ENABLE_CELERY = os.getenv('ENABLE_CELERY', 'false').lower() == 'true'

# Import task functions - circular import is broken since worker.py no longer imports tasks
# Import both the Celery-wrapped version and the direct implementation
try:
    from tasks import scrape_venue_task, _scrape_venue_task_impl
except Exception as e:
    # If import fails (e.g., Celery/Redis not available), we can't process tasks
    logger.error(f"Failed to import tasks module: {e}")
    scrape_venue_task = None
    _scrape_venue_task_impl = None
    ENABLE_CELERY = False

# Import Celery app only if enabled (for .delay() method)
celery_app = None
if ENABLE_CELERY:
    try:
        from worker import celery_app
        # Verify Celery is actually working
        if celery_app is None:
            ENABLE_CELERY = False
    except Exception as e:
        logger.warning(f"Celery enabled but failed to import: {e}. Falling back to direct execution.")
        ENABLE_CELERY = False

# Import DB functions for validation
from db import get_db_connection
import psycopg2.extras


class ScrapeVenueRequest(BaseModel):
    task_id: str


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return JSONResponse({
        "status": "ok",
        "service": "venue-scraper-worker",
        "version": "2.0.0",
        "celery_enabled": ENABLE_CELERY
    })


@app.get("/health")
async def health():
    """
    Health check endpoint.
    Checks required environment variables and Celery status (if enabled).
    """
    # Required vars (Celery vars only required if Celery is enabled)
    required_vars = ['DATABASE_URL', 'GROQ_API_KEY']
    if ENABLE_CELERY:
        required_vars.extend(['CELERY_BROKER_URL'])
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        return JSONResponse(
            {
                "status": "unhealthy",
                "missing_environment_variables": missing_vars
            },
            status_code=503
        )
    
    health_data = {
        "status": "healthy",
        "database": "configured",
        "groq_api": "configured",
        "celery_enabled": ENABLE_CELERY
    }
    
    if ENABLE_CELERY:
        health_data["celery_broker"] = "configured"
    
    return JSONResponse(health_data)


@app.post("/scrape-venue")
async def scrape_venue(request: ScrapeVenueRequest):
    """
    Trigger venue scraping for a task.
    
    This endpoint replaces Celery Beat polling - jobs are triggered immediately
    via HTTP when a user submits a venue URL, reducing infrastructure costs.
    
    Cost Efficiency:
    - No Celery Beat scheduler running 24/7 (saves ~$X/month)
    - Worker only processes jobs when users submit URLs (idle = no cost)
    - Celery is optional - can run directly without Redis for even lower costs
    - Suitable for low-traffic hobby projects (<5 users)
    
    Args:
        request: Contains task_id of the scraping task to process
        
    Returns:
        Success message if task was queued/started
    """
    task_id = request.task_id
    
    try:
        logger.info(f"Received scrape-venue request for task_id: {task_id}")
        
        if _scrape_venue_task_impl is None:
            logger.error("_scrape_venue_task_impl is None - tasks module not loaded properly")
            raise HTTPException(status_code=503, detail="Scraping service unavailable - tasks module not loaded")
        
        # Validate task exists in database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM venue_scraping_tasks WHERE id = %s", (task_id,))
        task = cur.fetchone()
        cur.close()
        conn.close()
        
        if not task:
            logger.warning(f"Task {task_id} not found in database")
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        logger.info(f"Task {task_id} found in database, status: {task.get('status')}")
        
        # Trigger scraping task
        if ENABLE_CELERY and celery_app:
            # Use Celery queue if enabled (for concurrency if needed)
            # Celery allows multiple tasks to run in parallel, useful if traffic grows
            scrape_venue_task.delay(task_id)
            logger.info(f"Queued scraping task {task_id} via Celery")
            message = "Task queued via Celery"
        else:
            # Run directly in background thread - simpler and more cost-effective for low traffic
            # This avoids blocking the HTTP response while processing
            # Call the implementation function directly (not the Celery wrapper)
            import threading
            
            def run_task_with_logging(task_id: str):
                """Wrapper to ensure exceptions are logged"""
                try:
                    logger.info(f"Background thread starting task {task_id}")
                    _scrape_venue_task_impl(task_id)
                    logger.info(f"Background thread completed task {task_id}")
                except Exception as e:
                    logger.error(f"Background thread error for task {task_id}: {str(e)}", exc_info=True)
            
            thread = threading.Thread(target=run_task_with_logging, args=(task_id,))
            thread.daemon = True
            thread.start()
            logger.info(f"Started scraping task {task_id} directly (Celery disabled) in background thread")
            message = "Task started directly"
        
        return JSONResponse({
            "success": True,
            "message": message,
            "task_id": task_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering scraping task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")


@app.post("/process-pending")
async def process_pending():
    """
    Fallback endpoint to process any pending tasks that weren't triggered automatically.
    
    This can be called periodically (e.g., every 2-5 seconds) as a safety net
    in case the HTTP trigger from Next.js fails or is delayed.
    
    Only processes tasks that are still 'pending' and older than 2 seconds
    to avoid processing tasks that are currently being triggered.
    """
    try:
        from db import find_pending_tasks
        import threading
        from datetime import datetime, timedelta
        
        # Find pending tasks older than 2 seconds (to avoid race conditions)
        cutoff_time = datetime.now() - timedelta(seconds=2)
        
        # Get pending tasks
        pending_tasks = find_pending_tasks(limit=10)
        
        processed = 0
        for task in pending_tasks:
            task_id = task['id']
            # Only process tasks older than 2 seconds
            created_at = task.get('created_at')
            if created_at and isinstance(created_at, str):
                try:
                    task_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if task_time.tzinfo:
                        task_time = task_time.replace(tzinfo=None)
                except:
                    # If we can't parse the time, process it anyway (fallback)
                    task_time = cutoff_time - timedelta(seconds=1)
            else:
                # If no timestamp, process it
                task_time = cutoff_time - timedelta(seconds=1)
            
            if task_time < cutoff_time:
                logger.info(f"Processing stale pending task {task_id} (fallback trigger)")
                
                def run_task_with_logging(task_id: str):
                    """Wrapper to ensure exceptions are logged"""
                    try:
                        logger.info(f"Background thread starting task {task_id} (fallback)")
                        _scrape_venue_task_impl(task_id)
                        logger.info(f"Background thread completed task {task_id} (fallback)")
                    except Exception as e:
                        logger.error(f"Background thread error for task {task_id}: {str(e)}", exc_info=True)
                
                thread = threading.Thread(target=run_task_with_logging, args=(task_id,))
                thread.daemon = True
                thread.start()
                processed += 1
        
        return JSONResponse({
            "success": True,
            "pending_tasks_found": len(pending_tasks),
            "tasks_processed": processed
        })
        
    except Exception as e:
        logger.error(f"Error processing pending tasks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process pending tasks: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

