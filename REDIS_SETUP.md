# Redis Configuration Guide

Redis is required for Celery to work as a message broker and result backend.

## Local Development

### Option 1: Docker Compose (Recommended)
The `docker-compose.yml` includes Redis automatically. Just run:
```bash
docker-compose up
```

### Option 2: Local Redis Installation

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Download from: https://github.com/microsoftarchive/redis/releases
Or use WSL2 with Linux instructions above.

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

**Update .env:**
```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Production Deployment

### Option 1: Redis on Same Server

**Install Redis:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server

# Configure Redis for production
sudo nano /etc/redis/redis.conf
# Set: bind 127.0.0.1 (only localhost)
# Set: requirepass your_strong_password_here
# Set: maxmemory 256mb
# Set: maxmemory-policy allkeys-lru

# Restart Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

**Update .env.production:**
```env
CELERY_BROKER_URL=redis://:your_strong_password_here@localhost:6379/0
CELERY_RESULT_BACKEND=redis://:your_strong_password_here@localhost:6379/0
```

### Option 2: Managed Redis Service (Recommended for Production)

**Popular Options:**
- **Redis Cloud**: https://redis.com/cloud/
- **AWS ElastiCache**: https://aws.amazon.com/elasticache/
- **DigitalOcean Managed Redis**: https://www.digitalocean.com/products/managed-redis
- **Upstash**: https://upstash.com/

**Example with Redis Cloud:**
1. Sign up and create a database
2. Get your connection URL (e.g., `redis://default:password@redis-12345.redis.cloud:12345`)
3. Update `.env.production`:
```env
CELERY_BROKER_URL=redis://default:password@redis-12345.redis.cloud:12345
CELERY_RESULT_BACKEND=redis://default:password@redis-12345.redis.cloud:12345
```

### Option 3: Docker Redis in Production

If using Docker Compose in production, Redis is included in `docker-compose.prod.yml`:

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass your_strong_password
  volumes:
    - redis_data:/data
```

Update `.env.production`:
```env
CELERY_BROKER_URL=redis://:your_strong_password@redis:6379/0
CELERY_RESULT_BACKEND=redis://:your_strong_password@redis:6379/0
```

## Testing Redis Connection

**From Python:**
```python
import redis
r = redis.from_url('redis://localhost:6379/0')
r.ping()  # Should return True
```

**From Command Line:**
```bash
redis-cli ping
# Or with password:
redis-cli -a your_password ping
```

## Security Best Practices

1. **Use strong passwords** for production Redis
2. **Bind to localhost** if Redis is on the same server
3. **Use SSL/TLS** for remote Redis connections (Redis 6+)
4. **Limit memory** to prevent OOM issues
5. **Monitor Redis** for performance and memory usage

## Troubleshooting

**Connection refused:**
- Check if Redis is running: `redis-cli ping`
- Check firewall settings
- Verify connection URL in .env

**Authentication failed:**
- Verify password in connection URL
- Check Redis password configuration

**Memory issues:**
- Set `maxmemory` in redis.conf
- Use `maxmemory-policy allkeys-lru` to evict old keys

