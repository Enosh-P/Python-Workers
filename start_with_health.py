#!/usr/bin/env python3
"""
Start script that runs both Celery worker and FastAPI health check server.
Useful for Railway deployments that require health checks.
"""

import os
import subprocess
import multiprocessing
import signal
import sys
import time

def run_celery_worker():
    """Run Celery worker."""
    cmd = ['celery', '-A', 'worker', 'worker', '--loglevel=info']
    if os.getenv('CELERY_WORKER_CONCURRENCY'):
        cmd.extend(['--concurrency', os.getenv('CELERY_WORKER_CONCURRENCY')])
    subprocess.run(cmd)

def run_fastapi():
    """Run FastAPI health check server."""
    import uvicorn
    port = int(os.getenv('PORT', 8001))
    uvicorn.run('main:app', host='0.0.0.0', port=port, log_level='info')

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\nShutting down...")
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start Celery worker in a separate process
    celery_process = multiprocessing.Process(target=run_celery_worker, name='celery-worker')
    celery_process.start()
    
    # Small delay to let Celery start
    time.sleep(2)
    
    # Start FastAPI in main process (for health checks)
    try:
        run_fastapi()
    except KeyboardInterrupt:
        print("\nShutting down...")
        celery_process.terminate()
        celery_process.join(timeout=5)
        if celery_process.is_alive():
            celery_process.kill()

