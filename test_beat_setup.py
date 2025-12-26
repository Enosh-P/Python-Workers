#!/usr/bin/env python3
"""
Test script to verify Beat service can find and process pending tasks.
Run this in Railway Beat service shell to diagnose issues.
"""

import os
import sys

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def test_env_vars():
    """Test if required environment variables are set."""
    print("=" * 60)
    print("Environment Variables Check")
    print("=" * 60)
    
    required = {
        'DATABASE_URL': 'Required for Beat to find pending tasks',
        'CELERY_BROKER_URL': 'Required for Beat to send tasks',
        'CELERY_RESULT_BACKEND': 'Required for task results',
    }
    
    all_set = True
    for var, desc in required.items():
        value = os.getenv(var)
        if value:
            # Mask password in URL
            if '://' in value:
                parts = value.split('@')
                if len(parts) > 1:
                    masked = parts[0].split('://')[0] + '://***@' + '@'.join(parts[1:])
                else:
                    masked = value
            else:
                masked = '***' if len(value) > 10 else value
            print(f"✅ {var}: SET ({masked[:50]}...)")
        else:
            print(f"❌ {var}: MISSING - {desc}")
            all_set = False
    
    print()
    return all_set

def test_database():
    """Test database connection and query."""
    print("=" * 60)
    print("Database Connection Test")
    print("=" * 60)
    
    try:
        from db import get_db_connection, find_pending_tasks
        
        # Test connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        print("✅ Database connection: OK")
        
        # Test finding pending tasks
        tasks = find_pending_tasks(limit=10)
        print(f"✅ Found {len(tasks)} pending task(s) in database")
        
        if tasks:
            print("\nPending tasks:")
            for task in tasks:
                print(f"  - ID: {task['id']}")
                print(f"    URL: {task['venue_url']}")
                print(f"    Status: {task['status']}")
                print(f"    Created: {task['created_at']}")
                print()
        else:
            print("ℹ️  No pending tasks found (this is OK if you haven't created any)")
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_redis():
    """Test Redis connection."""
    print("=" * 60)
    print("Redis Connection Test")
    print("=" * 60)
    
    try:
        import redis
        broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(broker_url)
        r.ping()
        print(f"✅ Redis connection: OK")
        print(f"   Broker URL: {broker_url.split('@')[-1] if '@' in broker_url else broker_url}")
        return True
    except Exception as e:
        print(f"❌ Redis error: {str(e)}")
        return False

def test_celery_beat():
    """Test if Celery Beat can start."""
    print("=" * 60)
    print("Celery Beat Test")
    print("=" * 60)
    
    try:
        from worker import celery_app
        print("✅ Celery app loaded: OK")
        
        # Check beat schedule
        schedule = celery_app.conf.beat_schedule
        if 'process-pending-venue-tasks' in schedule:
            task_schedule = schedule['process-pending-venue-tasks']
            print(f"✅ Beat schedule configured:")
            print(f"   Task: {task_schedule['task']}")
            print(f"   Schedule: Every {task_schedule['schedule']} seconds")
        else:
            print("❌ Beat schedule not found!")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Celery Beat error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n🔍 Beat Service Setup Diagnostic")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Environment Variables", test_env_vars()))
    print()
    results.append(("Database", test_database()))
    print()
    results.append(("Redis", test_redis()))
    print()
    results.append(("Celery Beat", test_celery_beat()))
    print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ All checks passed! Beat should be able to process tasks.")
        print("\nNext steps:")
        print("1. Check Beat logs - should see 'Scheduler: Sending due task' every 10 seconds")
        print("2. Create a test task from Next.js")
        print("3. Watch Worker logs - should see task being processed")
    else:
        print("❌ Some checks failed. Fix the issues above.")
        print("\nMost common issues:")
        print("- Missing DATABASE_URL (Beat needs this to find pending tasks!)")
        print("- Missing CELERY_BROKER_URL (Beat needs this to send tasks)")
        print("- Database connection errors (check DATABASE_URL format)")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

