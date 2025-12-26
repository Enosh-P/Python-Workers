# Venue Scraping Worker Deployment Script (PowerShell)
# This script helps deploy the Python worker to a server on Windows

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "stop", "restart", "logs", "status")]
    [string]$Action = "deploy"
)

Write-Host "🚀 Venue Scraping Worker Deployment Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is installed
try {
    docker --version | Out-Null
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
try {
    docker-compose --version | Out-Null
} catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if .env.production exists
if (-not (Test-Path ".env.production")) {
    Write-Host "⚠️  .env.production not found. Creating from .env.example..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env.production"
        Write-Host "⚠️  Please edit .env.production with your production credentials!" -ForegroundColor Yellow
    } else {
        Write-Host "❌ .env.example not found. Please create .env.production manually." -ForegroundColor Red
        exit 1
    }
}

# Function to deploy
function Deploy-Services {
    Write-Host "📦 Building Docker images..." -ForegroundColor Green
    docker-compose -f docker-compose.prod.yml build

    Write-Host "🔄 Starting services..." -ForegroundColor Green
    docker-compose -f docker-compose.prod.yml up -d

    Write-Host "✅ Deployment complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Services running:"
    Write-Host "  - Worker: Processing venue scraping tasks"
    Write-Host "  - Beat: Scheduling periodic tasks"
    Write-Host "  - API: Health check endpoint on port 8001"
    Write-Host "  - Redis: Message broker"
    Write-Host ""
    Write-Host "Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
}

# Function to stop services
function Stop-Services {
    Write-Host "🛑 Stopping services..." -ForegroundColor Yellow
    docker-compose -f docker-compose.prod.yml down
    Write-Host "✅ Services stopped" -ForegroundColor Green
}

# Function to restart services
function Restart-Services {
    Write-Host "🔄 Restarting services..." -ForegroundColor Yellow
    docker-compose -f docker-compose.prod.yml restart
    Write-Host "✅ Services restarted" -ForegroundColor Green
}

# Function to view logs
function Show-Logs {
    docker-compose -f docker-compose.prod.yml logs -f
}

# Function to show status
function Show-Status {
    Write-Host "📊 Service Status:" -ForegroundColor Green
    docker-compose -f docker-compose.prod.yml ps
}

# Execute action
switch ($Action) {
    "deploy" {
        Deploy-Services
    }
    "stop" {
        Stop-Services
    }
    "restart" {
        Restart-Services
    }
    "logs" {
        Show-Logs
    }
    "status" {
        Show-Status
    }
    default {
        Write-Host "Usage: .\deploy.ps1 {deploy|stop|restart|logs|status}" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  deploy   - Build and start all services (default)"
        Write-Host "  stop     - Stop all services"
        Write-Host "  restart  - Restart all services"
        Write-Host "  logs     - View logs from all services"
        Write-Host "  status   - Show status of all services"
    }
}

