#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick health check script for venue scraping worker.
Tests database, Redis, and Groq API connections.
"""

import os
import sys

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_database():
    """Test database connection."""
    try:
        from db import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True, "Connected"
    except Exception as e:
        return False, str(e)

def test_redis():
    """Test Redis connection."""
    try:
        import redis
        broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(broker_url)
        r.ping()
        return True, "Connected"
    except Exception as e:
        return False, str(e)

def test_groq():
    """Test Groq API configuration."""
    try:
        from groq import Groq
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            return False, "API key not set"
        client = Groq(api_key=api_key)
        # Just check if client is created (don't make actual API call)
        return True, "Configured"
    except Exception as e:
        return False, str(e)

def test_pending_tasks():
    """Test finding pending tasks."""
    try:
        from db import find_pending_tasks
        tasks = find_pending_tasks(limit=1)
        return True, f"{len(tasks)} pending task(s)"
    except Exception as e:
        return False, str(e)

def main():
    """Run all health checks."""
    print("Venue Scraping Worker Health Check")
    print("=" * 50)
    
    checks = [
        ("Database", test_database),
        ("Redis", test_redis),
        ("Groq API", test_groq),
        ("Pending Tasks", test_pending_tasks),
    ]
    
    all_passed = True
    for name, test_func in checks:
        passed, message = test_func()
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {name}: {message}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("[OK] All checks passed! Worker is ready.")
        return 0
    else:
        print("[FAIL] Some checks failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

