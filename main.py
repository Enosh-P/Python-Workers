"""
FastAPI app for health checks and optional API endpoints.
This is optional - the main functionality is in the Celery worker.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import uvicorn

app = FastAPI(title="Venue Scraper Worker", version="1.0.0")


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return JSONResponse({
        "status": "ok",
        "service": "venue-scraper-worker",
        "version": "1.0.0"
    })


@app.get("/health")
async def health():
    """Health check endpoint"""
    # Check if required environment variables are set
    required_vars = ['DATABASE_URL', 'GROQ_API_KEY', 'CELERY_BROKER_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        return JSONResponse(
            {
                "status": "unhealthy",
                "missing_environment_variables": missing_vars
            },
            status_code=503
        )
    
    return JSONResponse({
        "status": "healthy",
        "database": "configured",
        "groq_api": "configured",
        "celery_broker": "configured"
    })


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)

