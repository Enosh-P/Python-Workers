# PowerShell script to start worker without Docker
# Make sure Redis is running first!

Write-Host "Starting Venue Scraping Worker..." -ForegroundColor Cyan
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found. Copy from env.example and configure it." -ForegroundColor Yellow
    Write-Host ""
}

# Check if Redis is accessible
Write-Host "Checking Redis connection..." -ForegroundColor Yellow
try {
    python -c "import redis; r = redis.from_url('redis://localhost:6379/0'); r.ping(); print('Redis: OK')" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Redis is not running or not accessible!" -ForegroundColor Red
        Write-Host "Please start Redis first:" -ForegroundColor Yellow
        Write-Host "  - Docker: docker run -d -p 6379:6379 redis:7-alpine" -ForegroundColor Gray
        Write-Host "  - Or install Redis locally" -ForegroundColor Gray
        exit 1
    }
} catch {
    Write-Host "[ERROR] Redis check failed. Make sure Redis is running." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting Celery Worker..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Start worker
python -m celery -A worker worker --loglevel=info

