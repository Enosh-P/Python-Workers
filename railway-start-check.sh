#!/bin/bash
# Quick script to verify Railway setup before deployment
# Run this locally to check if everything is configured correctly

echo "🔍 Railway Deployment Pre-Check"
echo "================================"
echo ""

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ ERROR: requirements.txt not found"
    echo "   Make sure you're in the python-worker directory"
    exit 1
fi

echo "✅ Found requirements.txt"

# Check if worker.py exists
if [ ! -f "worker.py" ]; then
    echo "❌ ERROR: worker.py not found"
    exit 1
fi

echo "✅ Found worker.py"

# Check if tasks.py exists
if [ ! -f "tasks.py" ]; then
    echo "❌ ERROR: tasks.py not found"
    exit 1
fi

echo "✅ Found tasks.py"

# Check Python version
echo ""
echo "Python version:"
python3 --version

# Check if dependencies can be imported (if virtualenv is active)
if command -v python3 &> /dev/null; then
    echo ""
    echo "Testing imports..."
    python3 -c "import celery; print('✅ Celery')" 2>/dev/null || echo "⚠️  Celery not installed (will install in Railway)"
    python3 -c "import redis; print('✅ Redis')" 2>/dev/null || echo "⚠️  Redis not installed (will install in Railway)"
    python3 -c "import psycopg2; print('✅ PostgreSQL')" 2>/dev/null || echo "⚠️  psycopg2 not installed (will install in Railway)"
fi

echo ""
echo "================================"
echo "✅ Pre-check complete!"
echo ""
echo "Next steps for Railway:"
echo "1. Set Root Directory: python-worker"
echo "2. Set Start Command: celery -A worker worker --loglevel=info"
echo "3. Set environment variables"
echo "4. Deploy!"

