#!/bin/bash

# Entmoot Deployment Script
# This script automates the deployment process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed"
        return 1
    else
        print_success "$1 is installed"
        return 0
    fi
}

# Main script
print_header "Entmoot Deployment Script"

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found. Please run this script from the project root."
    exit 1
fi

# Check prerequisites
print_info "Checking prerequisites..."
check_command docker || exit 1
check_command docker || exit 1

# Check if docker compose command works
if docker compose version &> /dev/null; then
    print_success "Docker Compose v2 is available"
    COMPOSE_CMD="docker compose"
elif docker-compose version &> /dev/null; then
    print_success "Docker Compose v1 is available"
    COMPOSE_CMD="docker-compose"
else
    print_error "Docker Compose is not available"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    print_warning ".env file not found"
    print_info "Creating .env from .env.example..."

    if [ ! -f ".env.example" ]; then
        print_error ".env.example not found"
        exit 1
    fi

    cp .env.example .env

    # Generate secrets
    print_info "Generating secrets..."
    SECRET_KEY=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)
    REDIS_PASSWORD=$(openssl rand -hex 16)

    # Update .env with generated secrets
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" .env
        sed -i '' "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD}/" .env
        sed -i '' "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" .env
    else
        # Linux
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" .env
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD}/" .env
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" .env
    fi

    print_success ".env file created with generated secrets"
    print_warning "Please review and update .env file with your configuration"
    print_info "Especially update CORS_ORIGINS with your domain"

    read -p "Press Enter to continue after reviewing .env..."
fi

# Ask deployment type
print_header "Select Deployment Type"
echo "1) Local Development (with hot reload)"
echo "2) Production Build"
echo "3) Clean Rebuild (removes all data)"
echo ""
read -p "Select option [1-3]: " deploy_type

case $deploy_type in
    1)
        print_header "Starting Local Development Environment"
        COMPOSE_FILE="-f docker-compose.dev.yml"
        ;;
    2)
        print_header "Building Production Deployment"
        COMPOSE_FILE=""
        ;;
    3)
        print_header "Clean Rebuild"
        print_warning "This will remove all data including database!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            print_info "Cancelled"
            exit 0
        fi
        print_info "Stopping and removing all containers, volumes, and images..."
        $COMPOSE_CMD down -v --remove-orphans
        print_success "Clean completed"
        COMPOSE_FILE=""
        ;;
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

# Build images
print_header "Building Docker Images"
$COMPOSE_CMD $COMPOSE_FILE build

# Start services
print_header "Starting Services"
$COMPOSE_CMD $COMPOSE_FILE up -d

# Wait for services to be healthy
print_info "Waiting for services to be healthy..."
sleep 10

# Check service status
print_header "Service Status"
$COMPOSE_CMD ps

# Health checks
print_header "Running Health Checks"

check_health() {
    local url=$1
    local service=$2
    local max_attempts=30
    local attempt=0

    print_info "Checking $service..."

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf $url > /dev/null 2>&1; then
            print_success "$service is healthy"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done

    print_error "$service is not responding"
    return 1
}

# Check backend
if check_health "http://localhost:8000/health" "Backend"; then
    BACKEND_OK=true
else
    BACKEND_OK=false
fi

# Check frontend
if check_health "http://localhost:80/" "Frontend"; then
    FRONTEND_OK=true
else
    FRONTEND_OK=false
fi

# Final status
print_header "Deployment Summary"

if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
    print_success "All services are running!"
    echo ""
    print_info "Access your application:"
    echo "  Frontend: http://localhost"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo ""
    print_info "View logs:"
    echo "  $COMPOSE_CMD logs -f"
    echo ""
    print_info "Stop services:"
    echo "  $COMPOSE_CMD down"
else
    print_error "Some services failed to start"
    print_info "Check logs with: $COMPOSE_CMD logs"
    exit 1
fi

# Offer to show logs
echo ""
read -p "Show logs? (y/n): " show_logs
if [ "$show_logs" = "y" ]; then
    $COMPOSE_CMD logs -f
fi
