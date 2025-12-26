# Venue Scraping Worker

Python worker service for scraping venue websites and extracting structured data using Groq LLM.

## Quick Start

### Option 1: Using Docker (Recommended)

**Prerequisites:** Docker Desktop must be running

### Prerequisites
- Docker and Docker Compose installed
- PostgreSQL database accessible
- Groq API key

### Local Development

1. **Navigate to the worker directory:**
```bash
cd python-worker
```

2. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start all services with Docker Compose:**
```bash
docker-compose up
```

This will start:
- Redis (message broker)
- Celery Worker (processes scraping tasks)
- Celery Beat (schedules periodic tasks)
- FastAPI (health check API on port 8001)

4. **View logs:**
```bash
docker-compose logs -f
```

5. **Stop services:**
```bash
docker-compose down
```

### Production Deployment

1. **Create production environment file:**
```bash
cp .env.example .env.production
# Edit .env.production with production credentials
```

2. **Deploy using the deployment script:**

**Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh deploy
```

**Windows (PowerShell):**
```powershell
.\deploy.ps1 deploy
```

3. **Check status:**
```bash
./deploy.sh status    # Linux/Mac
.\deploy.ps1 status   # Windows
```

4. **View logs:**
```bash
./deploy.sh logs      # Linux/Mac
.\deploy.ps1 logs     # Windows
```

5. **Restart services:**
```bash
./deploy.sh restart   # Linux/Mac
.\deploy.ps1 restart  # Windows
```

### Option 2: Manual Setup (Without Docker)

**Prerequisites:** Redis must be installed and running

See [SETUP_WITHOUT_DOCKER.md](./SETUP_WITHOUT_DOCKER.md) for detailed instructions.

**Quick Start:**
1. Install and start Redis (see SETUP_WITHOUT_DOCKER.md)
2. Configure `.env` file
3. Start worker: `.\start_worker.ps1` (Windows) or `python -m celery -A worker worker --loglevel=info`
4. Start beat: `.\start_beat.ps1` (Windows) or `python -m celery -A worker beat --loglevel=info`

## Manual Setup (Alternative)

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in your database connection details
   - Add your Groq API key
   - Configure Redis connection for Celery

3. **Start Redis (if not already running):**
```bash
redis-server
```

4. **Start Celery worker:**
```bash
celery -A worker worker --loglevel=info
```

5. **Start Celery Beat (for periodic task processing):**
```bash
celery -A worker beat --loglevel=info
```

6. **(Optional) Start FastAPI server for health checks:**
```bash
python main.py
```

## How It Works

1. Next.js creates a scraping task in the database with status='pending'
2. Celery Beat periodically calls `process_pending_tasks()` (every 10 seconds)
3. `process_pending_tasks()` finds pending tasks and dispatches `scrape_venue_task` for each
4. `scrape_venue_task`:
   - Checks for cancel flag
   - Updates status to 'processing'
   - Scrapes the webpage
   - Extracts structured data using Groq LLM
   - Updates task with status='ready' and venue_data
   - Creates a venue_item in the venue_items table
5. Next.js polls the task status and displays the result

## Docker Commands Reference

### Development
```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Rebuild images
docker-compose build

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Production
```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Stop services
docker-compose -f docker-compose.prod.yml down
```

## Environment Variables

Required environment variables (set in `.env` or `.env.production`):

- `DATABASE_URL`: PostgreSQL connection string (or use DB_HOST, DB_PORT, etc.)
  - Example: `postgresql://user:password@localhost:5432/onlycouples`
- `GROQ_API_KEY`: Your Groq API key (required)
- `CELERY_BROKER_URL`: Redis URL for Celery broker
  - Local: `redis://localhost:6379/0`
  - With password: `redis://:password@localhost:6379/0`
  - Managed service: `redis://default:password@host:6379`
- `CELERY_RESULT_BACKEND`: Redis URL for Celery results (same as broker)
- `PORT`: FastAPI server port (optional, default: 8001)

See [REDIS_SETUP.md](./REDIS_SETUP.md) for detailed Redis configuration instructions.

## Testing

See [TESTING.md](./TESTING.md) for comprehensive testing guide.

## Production Deployment

See [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for detailed Railway deployment instructions.

**Quick Health Check:**
```bash
python test_health.py
```

This will verify:
- Database connection
- Redis connection
- Groq API configuration
- Pending tasks query

## Task Cancellation

Tasks can be canceled by setting `cancel_flag = TRUE` in the database. The worker checks this flag at multiple points:
- Before starting processing
- After scraping
- After LLM extraction

If canceled, the task status is set to 'canceled' and processing stops.

