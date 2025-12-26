# Setup Without Docker

If you don't have Docker or prefer not to use it, follow these steps:

## Option 1: Install Redis Locally

### Windows

**Using WSL2 (Recommended):**
```bash
# In WSL2 terminal
sudo apt-get update
sudo apt-get install redis-server
sudo service redis-server start
```

**Or download Redis for Windows:**
- Download from: https://github.com/microsoftarchive/redis/releases
- Extract and run `redis-server.exe`

**Or use Chocolatey:**
```powershell
choco install redis-64
redis-server
```

### macOS
```bash
brew install redis
brew services start redis
```

### Linux
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

## Option 2: Use Managed Redis Service

Use a free managed Redis service like:
- **Upstash** (free tier): https://upstash.com/
- **Redis Cloud** (free tier): https://redis.com/cloud/

Get the connection URL and update your `.env`:
```env
CELERY_BROKER_URL=redis://default:password@your-redis-host:6379
CELERY_RESULT_BACKEND=redis://default:password@your-redis-host:6379
```

## Running the Worker

Once Redis is running:

**Terminal 1 - Celery Worker:**
```bash
cd python-worker
python -m celery -A worker worker --loglevel=info
```

**Terminal 2 - Celery Beat:**
```bash
cd python-worker
python -m celery -A worker beat --loglevel=info
```

**Terminal 3 - Next.js (if not already running):**
```bash
npm run dev
```

## Verify Redis is Running

```bash
# Test Redis connection
redis-cli ping
# Should return: PONG

# Or from Python
python
>>> import redis
>>> r = redis.from_url('redis://localhost:6379/0')
>>> r.ping()
True
```

## Troubleshooting

**Redis not found:**
- Install Redis (see above)
- Or use a managed service

**Connection refused:**
- Make sure Redis is running: `redis-cli ping`
- Check if port 6379 is available
- Verify firewall settings

**Can't connect to Redis:**
- Check Redis is listening: `netstat -an | findstr 6379` (Windows)
- Verify connection URL in `.env`

