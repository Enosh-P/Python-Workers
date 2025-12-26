# PowerShell script to start Celery Beat without Docker

Write-Host "Starting Celery Beat (Task Scheduler)..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Start beat
python -m celery -A worker beat --loglevel=info

