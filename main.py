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

# Configure logging
logger = logging.getLogger(__name__)

app = FastAPI(title="Venue Scraper Worker", version="2.0.0")

# Check if Celery is enabled (optional for cost efficiency)
ENABLE_CELERY = os.getenv('ENABLE_CELERY', 'false').lower() == 'true'

# Import task function - circular import is broken since worker.py no longer imports tasks
# Note: scrape_venue_task can be called directly even if it's a Celery task
try:
    from tasks import scrape_venue_task
except Exception as e:
    # If import fails (e.g., Celery/Redis not available), we can't process tasks
    logger.error(f"Failed to import tasks module: {e}")
    scrape_venue_task = None
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
        if scrape_venue_task is None:
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
            # Note: Even though scrape_venue_task is a Celery task, we can call it directly
            # This path requires no Redis/Celery infrastructure, reducing costs
            import threading
            thread = threading.Thread(target=scrape_venue_task, args=(task_id,))
            thread.daemon = True
            thread.start()
            logger.info(f"Started scraping task {task_id} directly (Celery disabled)")
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


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

