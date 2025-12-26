# Railway Deployment Guide - Python Worker

This guide walks you through deploying the venue scraping Python worker to Railway.

## Prerequisites

- Railway account (sign up at https://railway.app)
- GitHub account (for connecting your repository)
- Your production database connection string
- Groq API key

## Step 1: Set Up Redis on Railway

### Option A: Use Railway's Redis Plugin (Recommended)

1. **Create a new project** in Railway dashboard
2. **Click "New"** → **"Database"** → **"Add Redis"**
3. Railway will automatically create a Redis instance
4. **Copy the connection URL** from the Redis service variables (you'll need this later)

### Option B: Use External Redis Service

- **Upstash Redis** (free tier): https://upstash.com/
- **Redis Cloud** (free tier): https://redis.com/cloud/
- Get the connection URL from your chosen service

## Step 2: Deploy the Python Worker

### Method 1: Deploy from GitHub (Recommended)

1. **Push your code to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Add Python worker for venue scraping"
   git push origin main
   ```

2. **In Railway Dashboard:**
   - Click **"New Project"**
   - Select **"Deploy from GitHub repo"**
   - Choose your repository
   - Railway will auto-detect it's a Python project

3. **Configure the service:**
   - Railway should detect the `python-worker` directory
   - If not, set **Root Directory** to `python-worker`
   - Set **Start Command** to: `celery -A worker worker --loglevel=info`

### Method 2: Deploy from Local Directory

1. **Install Railway CLI:**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway:**
   ```bash
   railway login
   ```

3. **Initialize Railway in your project:**
   ```bash
   cd python-worker
   railway init
   ```

4. **Link to existing project or create new:**
   ```bash
   railway link  # Link to existing project
   # OR
   railway new  # Create new project
   ```

5. **Deploy:**
   ```bash
   railway up
   ```

## Step 3: Configure Environment Variables

In Railway dashboard, go to your service → **Variables** tab and add:

### Required Variables

```env
# Database Connection
DATABASE_URL=postgresql://user:password@host:port/database
# OR use individual parameters:
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=onlycouples
DB_USER=your-db-user
DB_PASSWORD=your-db-password

# Groq API Key
GROQ_API_KEY=your_groq_api_key_here

# Redis Connection (from Step 1)
CELERY_BROKER_URL=redis://default:password@redis-host:6379
CELERY_RESULT_BACKEND=redis://default:password@redis-host:6379

# Optional
PORT=8001
LOG_LEVEL=INFO
```

### Getting Your Database URL

If using **Supabase**:
- Go to Project Settings → Database
- Copy the connection string (use "Connection pooling" for better performance)

If using **Railway PostgreSQL**:
- Add PostgreSQL database service
- Copy the connection URL from service variables

## Step 4: Set Up Celery Beat (Task Scheduler)

You need a separate service for Celery Beat to periodically check for pending tasks.

### Option A: Separate Railway Service (Recommended)

1. **Duplicate your worker service:**
   - In Railway, click on your worker service
   - Click **"..."** → **"Duplicate"**
   - Rename it to "venue-worker-beat"

2. **Change the start command:**
   - Go to **Settings** → **Deploy**
   - Set **Start Command** to: `celery -A worker beat --loglevel=info`

3. **Use the same environment variables** (they're shared across services in a project)

### Option B: Single Service with Both Worker and Beat

Create a `Procfile` in `python-worker/`:

```procfile
worker: celery -A worker worker --loglevel=info
beat: celery -A worker beat --loglevel=info
```

Then set Railway start command to use a process manager, or use a startup script.

**Recommended: Use separate services** for better reliability and scaling.

## Step 5: Configure Railway Settings

### Service Settings

1. **Root Directory:** `python-worker` (if deploying from monorepo)
2. **Start Command:** 
   - Worker: `celery -A worker worker --loglevel=info`
   - Beat: `celery -A worker beat --loglevel=info`
3. **Health Check:** 
   - **Option A (Recommended):** Leave Health Check Path **empty/blank** - Railway will monitor process status
   - **Option B:** If you need HTTP health checks, use `python start_with_health.py` for Worker service and set:
     - Health Check Path: `/health`
     - Health Check Port: `8001`
   - **Note:** Beat service doesn't need health checks - leave it blank

**Important:** Celery workers don't expose HTTP endpoints by default. Railway's process monitoring is sufficient for health checks.

### Build Settings

Railway auto-detects Python, but you can specify:

1. **Python Version:** Set in `runtime.txt`:
   ```
   python-3.11.0
   ```

2. **Build Command:** Railway will automatically run `pip install -r requirements.txt`

## Step 6: Deploy and Verify

1. **Deploy:**
   - If using GitHub: Push to trigger deployment
   - If using CLI: Run `railway up`

2. **Check Logs:**
   - Go to your service → **Deployments** → Click on latest deployment → **View Logs**
   - Look for:
     ```
     [INFO] Connected to redis://...
     [INFO] celery@... ready
     [tasks]
       . scrape_venue_task
       . process_pending_tasks
     ```

3. **Test the Health Check** (if using FastAPI):
   ```bash
   curl https://your-service.railway.app/health
   ```

## Step 7: Update Next.js Environment Variables

In your Next.js app (Vercel or wherever it's deployed), ensure your API routes can connect to the same database that the worker uses.

The worker and Next.js should use the **same database** so they can share the `venue_scraping_tasks` table.

## Step 8: Monitor and Troubleshoot

### View Logs

```bash
# Using Railway CLI
railway logs

# Or in Railway Dashboard
# Go to service → Deployments → View Logs
```

### Common Issues

**1. Worker not connecting to Redis:**
- Check `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are correct
- Ensure Redis service is running
- Check Redis connection string format

**2. Worker not connecting to database:**
- Verify `DATABASE_URL` is correct
- Check database allows connections from Railway IPs
- For Supabase: Use connection pooling URL

**3. Tasks not being processed:**
- Ensure Celery Beat service is running
- Check Beat logs for errors
- Verify `process_pending_tasks` is scheduled in `worker.py`

**4. Import errors:**
- Check all dependencies are in `requirements.txt`
- Verify Python version matches `runtime.txt`

### Scaling

Railway allows you to:
- **Scale horizontally:** Add more worker instances
- **Scale vertically:** Increase resources per service
- **Auto-scaling:** Configure based on metrics (requires Railway Pro)

## Step 9: Production Best Practices

### 1. Use Railway Secrets

For sensitive values, use Railway's **Secrets** feature instead of plain environment variables.

### 2. Set Resource Limits

In Railway service settings:
- **Memory:** At least 512MB for worker
- **CPU:** 0.5 vCPU minimum

### 3. Enable Health Checks

If using FastAPI, expose health endpoint:
```python
# In main.py
@app.get("/health")
def health():
    return {"status": "ok"}
```

### 4. Set Up Monitoring

- Use Railway's built-in metrics
- Set up alerts for service failures
- Monitor Redis and database connections

### 5. Database Connection Pooling

For production, use connection pooling:
- **Supabase:** Use "Connection pooling" mode
- **Railway PostgreSQL:** Connection pooling is automatic

## Step 10: Update Your Next.js App

Ensure your Next.js app (on Vercel) can access the same database. The worker and Next.js should share:
- Same `DATABASE_URL`
- Same `venue_scraping_tasks` table
- Same `venue_items` table

## Quick Reference: Railway CLI Commands

```bash
# Login
railway login

# Link to project
railway link

# View logs
railway logs

# Open service in browser
railway open

# Run command in service
railway run python test_health.py

# View variables
railway variables

# Set variable
railway variables set GROQ_API_KEY=your_key

# Deploy
railway up
```

## Cost Estimation

**Railway Free Tier:**
- $5 credit/month
- Good for testing/small projects

**Railway Hobby ($5/month):**
- 512MB RAM per service
- 1 vCPU per service
- Suitable for small production

**Railway Pro ($20/month):**
- More resources
- Auto-scaling
- Better for production

**Redis (if using Railway Redis):**
- Included in Railway pricing
- Or use external free tier (Upstash/Redis Cloud)

## Troubleshooting Checklist

- [ ] Redis service is running and accessible
- [ ] Database connection string is correct
- [ ] All environment variables are set
- [ ] Celery Beat service is running (for task discovery)
- [ ] Worker service is running
- [ ] Dependencies are installed (check build logs)
- [ ] Python version matches requirements
- [ ] Health check endpoint works (if using FastAPI)
- [ ] Logs show no connection errors
- [ ] Tasks are being created in database
- [ ] Worker is picking up pending tasks

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check Railway status: https://status.railway.app

