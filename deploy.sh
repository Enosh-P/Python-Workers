#!/bin/bash

# Venue Scraping Worker Deployment Script
# This script helps deploy the Python worker to a server

set -e

echo "🚀 Venue Scraping Worker Deployment Script"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if .env.production exists
if [ ! -f .env.production ]; then
    echo -e "${YELLOW}⚠️  .env.production not found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env.production
        echo -e "${YELLOW}⚠️  Please edit .env.production with your production credentials!${NC}"
    else
        echo -e "${RED}❌ .env.example not found. Please create .env.production manually.${NC}"
        exit 1
    fi
fi

# Function to deploy
deploy() {
    echo -e "${GREEN}📦 Building Docker images...${NC}"
    docker-compose -f docker-compose.prod.yml build

    echo -e "${GREEN}🔄 Starting services...${NC}"
    docker-compose -f docker-compose.prod.yml up -d

    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo "Services running:"
    echo "  - Worker: Processing venue scraping tasks"
    echo "  - Beat: Scheduling periodic tasks"
    echo "  - API: Health check endpoint on port 8001"
    echo "  - Redis: Message broker"
    echo ""
    echo "Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
}

# Function to stop services
stop() {
    echo -e "${YELLOW}🛑 Stopping services...${NC}"
    docker-compose -f docker-compose.prod.yml down
    echo -e "${GREEN}✅ Services stopped${NC}"
}

# Function to restart services
restart() {
    echo -e "${YELLOW}🔄 Restarting services...${NC}"
    docker-compose -f docker-compose.prod.yml restart
    echo -e "${GREEN}✅ Services restarted${NC}"
}

# Function to view logs
logs() {
    docker-compose -f docker-compose.prod.yml logs -f
}

# Function to show status
status() {
    echo -e "${GREEN}📊 Service Status:${NC}"
    docker-compose -f docker-compose.prod.yml ps
}

# Main menu
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|logs|status}"
        echo ""
        echo "Commands:"
        echo "  deploy   - Build and start all services (default)"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - View logs from all services"
        echo "  status   - Show status of all services"
        exit 1
        ;;
esac

