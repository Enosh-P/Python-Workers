# Docker Connection Fix

## Issue
Services were trying to connect to `redis://localhost:6379/0` but in Docker Compose, services should use the service name instead of `localhost`.

## Solution
Updated `docker-compose.yml` to use `redis://redis:6379/0` (service name) instead of `localhost`.

## How to Restart

```bash
cd python-worker

# Stop any running containers
docker-compose down

# Start with fixed configuration
docker-compose up
```

## What Changed

- Worker and Beat services now use `redis://redis:6379/0` (service name)
- This allows them to connect to the Redis container within Docker network
- Environment variables override `.env` file for Docker networking

## Verify It Works

After starting, you should see:
- ✅ Redis container running
- ✅ Worker connected to Redis (no connection errors)
- ✅ Beat connected to Redis (no connection errors)
- ✅ Logs showing: `[INFO] Connected to redis://redis:6379/0`

