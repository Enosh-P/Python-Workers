# Testing Guide - Venue Scraping Feature

This guide will help you test the venue scraping feature end-to-end.

## Prerequisites Checklist

- [ ] Database migration `024_add_venue_data_jsonb.sql` has been run
- [ ] Database migration `023_add_venue_scraping_tasks.sql` has been run
- [ ] Redis is running (or Docker Compose will start it)
- [ ] Environment variables are configured in `.env`
- [ ] Groq API key is valid
- [ ] PostgreSQL database is accessible

## Step 1: Run Database Migrations

```bash
# Connect to your database
psql -U postgres -d onlycouples

# Or if using Supabase/remote database:
# psql "your_connection_string"

# Run migrations
\i database/migrations/023_add_venue_scraping_tasks.sql
\i database/migrations/024_add_venue_data_jsonb.sql
```

**Verify migrations:**
```sql
-- Check if tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('venue_scraping_tasks', 'venue_items');

-- Check if venue_data column exists
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'venue_items' AND column_name = 'venue_data';
```

## Step 2: Start Services

### Option A: Using Docker Compose (Recommended)

```bash
cd python-worker

# Start all services (Redis, Worker, Beat, API)
docker-compose up

# Or in background:
docker-compose up -d
```

### Option B: Manual Setup

**Terminal 1 - Start Redis:**
```bash
redis-server
# Or if using Docker:
docker run -d -p 6379:6379 redis:7-alpine
```

**Terminal 2 - Start Celery Worker:**
```bash
cd python-worker
source venv/bin/activate  # If using virtualenv
celery -A worker worker --loglevel=info
```

**Terminal 3 - Start Celery Beat:**
```bash
cd python-worker
source venv/bin/activate
celery -A worker beat --loglevel=info
```

**Terminal 4 - Start Next.js (if not already running):**
```bash
npm run dev
```

## Step 3: Verify Services Are Running

### Check Redis
```bash
redis-cli ping
# Should return: PONG
```

### Check Celery Worker
Look for this in the worker logs:
```
[tasks]
  . scrape_venue_task
  . process_pending_tasks
```

### Check Database Connection
```python
# In Python shell
cd python-worker
python
>>> from db import get_db_connection
>>> conn = get_db_connection()
>>> print("✅ Database connected!")
```

### Check Groq API
```python
# In Python shell
import os
from groq import Groq

api_key = os.getenv('GROQ_API_KEY')
if api_key:
    client = Groq(api_key=api_key)
    print("✅ Groq API key configured!")
else:
    print("❌ GROQ_API_KEY not set")
```

## Step 4: Test the Full Flow

### 4.1 Create a Scraping Task via API

**Using curl:**
```bash
curl -X POST http://localhost:3000/api/spaces/YOUR_SPACE_SLUG/venues/scrape \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"url": "https://example-venue-website.com"}'
```

**Expected Response:**
```json
{
  "taskId": "venue_scrape_1234567890_abc123",
  "status": "pending",
  "message": "Venue scraping task created successfully."
}
```

### 4.2 Check Task Status

```bash
curl http://localhost:3000/api/spaces/YOUR_SPACE_SLUG/venues/scrape/TASK_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Status Progression:**
1. `pending` - Task created, waiting for worker
2. `processing` - Worker is scraping and extracting
3. `ready` - Success! Venue data extracted
4. `failed` - Error occurred (check error_message)
5. `canceled` - User canceled the task

### 4.3 Test via Next.js UI

1. **Navigate to a space with venue section:**
   ```
   http://localhost:3000/space/YOUR_SPACE_ID/venue
   ```

2. **Click "Add via Link" button**

3. **Paste a venue URL** (try these test URLs):
   - A real venue website
   - Any website with venue information

4. **Click "Start Processing"**

5. **Watch the processing card:**
   - Should show "Processing your venue link..."
   - Then "Scraping venue information..."
   - Finally "Venue information extracted successfully!"

6. **Check the venue card appears** with extracted data

## Step 5: Monitor Logs

### Docker Compose Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f worker
docker-compose logs -f beat
```

### Manual Setup Logs
Check the terminal outputs for:
- **Worker:** Task execution, scraping progress, LLM calls
- **Beat:** Periodic task discovery
- **Next.js:** API requests, polling

### What to Look For

**✅ Success Indicators:**
```
[INFO] Starting venue scraping task: venue_scrape_...
[INFO] Scraping URL: https://...
[INFO] Extracted 5000 characters of text and 10 images
[INFO] Calling Groq LLM for venue data extraction
[INFO] Successfully extracted venue data: Venue Name
[INFO] Updated task ... to status: ready
[INFO] Created venue item ... for space ...
```

**❌ Error Indicators:**
```
[ERROR] Error fetching URL: Connection timeout
[ERROR] Failed to parse JSON from LLM response
[ERROR] Error extracting venue data with LLM
[ERROR] Task ... not found in database
```

## Step 6: Verify Database Records

### Check Scraping Task
```sql
SELECT id, status, venue_url, venue_data, error_message, created_at, processed_at
FROM venue_scraping_tasks
ORDER BY created_at DESC
LIMIT 5;
```

### Check Created Venue
```sql
SELECT id, name, address, price, category, venue_data, images
FROM venue_items
WHERE venue_data IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

### Check venue_data JSONB
```sql
SELECT 
  name,
  venue_data->>'name' as scraped_name,
  venue_data->'location'->>'city' as city,
  venue_data->'guest_capacity'->>'seated' as seated_capacity,
  venue_data->'price_per_plate_starting'->>'non_veg' as non_veg_price
FROM venue_items
WHERE venue_data IS NOT NULL;
```

## Step 7: Test Error Scenarios

### Invalid URL
```bash
# Should return 400 error
curl -X POST http://localhost:3000/api/spaces/SLUG/venues/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-valid-url"}'
```

### Unreachable URL
```bash
# Should eventually fail with error_message
curl -X POST http://localhost:3000/api/spaces/SLUG/venues/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://this-domain-does-not-exist-12345.com"}'
```

### Cancel Task
```bash
# Start a task, then cancel it
curl -X PUT http://localhost:3000/api/spaces/SLUG/venues/scrape/TASK_ID/cancel \
  -H "Authorization: Bearer TOKEN"
```

## Step 8: Performance Testing

### Test Multiple Tasks
Create multiple scraping tasks simultaneously:
```bash
for i in {1..5}; do
  curl -X POST http://localhost:3000/api/spaces/SLUG/venues/scrape \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"https://example-venue-$i.com\"}"
done
```

### Monitor Worker Performance
- Check how many tasks are processed per minute
- Monitor Redis queue size
- Check database connection pool

## Troubleshooting

### Task Stuck in "pending"
- **Check:** Is Celery Beat running?
- **Check:** Are there any errors in Beat logs?
- **Fix:** Restart Beat service

### Task Fails Immediately
- **Check:** Database connection in worker logs
- **Check:** Redis connection
- **Fix:** Verify environment variables

### LLM Extraction Fails
- **Check:** Groq API key is valid
- **Check:** API rate limits
- **Check:** Scraped content quality (maybe website is empty)

### Venue Card Not Appearing
- **Check:** Task status is "ready"
- **Check:** venue_data is not null in database
- **Check:** Next.js polling is working (check browser console)
- **Check:** Venue was actually created in venue_items table

### Redis Connection Issues
```bash
# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check Redis is accepting connections
netstat -an | grep 6379  # Linux/Mac
netstat -an | findstr 6379  # Windows
```

## Quick Health Check Script

Create `test_health.py`:
```python
import os
from db import get_db_connection, find_pending_tasks
from groq import Groq
import redis

print("🔍 Health Check...")

# Database
try:
    conn = get_db_connection()
    print("✅ Database: Connected")
except Exception as e:
    print(f"❌ Database: {e}")

# Redis
try:
    r = redis.from_url(os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
    r.ping()
    print("✅ Redis: Connected")
except Exception as e:
    print(f"❌ Redis: {e}")

# Groq
try:
    api_key = os.getenv('GROQ_API_KEY')
    if api_key:
        client = Groq(api_key=api_key)
        print("✅ Groq API: Configured")
    else:
        print("❌ Groq API: Key not set")
except Exception as e:
    print(f"❌ Groq API: {e}")

# Pending Tasks
try:
    tasks = find_pending_tasks(limit=1)
    print(f"✅ Pending Tasks: {len(tasks)} found")
except Exception as e:
    print(f"❌ Pending Tasks: {e}")
```

Run it:
```bash
cd python-worker
python test_health.py
```

## Expected Test Results

✅ **All tests passing:**
- Task created successfully
- Status changes: pending → processing → ready
- Venue appears in UI with all VENUE_SCHEMA fields
- Database has venue_data JSONB populated
- No errors in logs

❌ **If tests fail:**
- Check logs for specific error messages
- Verify all services are running
- Check environment variables
- Ensure database migrations are applied

