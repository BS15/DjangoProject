#!/bin/bash

# Exit on error
set -e

echo "🔧 Setting up development environment..."

# Update package lists
sudo apt-get update

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get install -y --no-install-recommends \
  build-essential \
  libpq-dev \
  postgresql-client \
  git \
  curl \
  wget \
  vim \
  nano \
  bubblewrap \
  socat

# Upgrade pip, setuptools, and wheel
echo "⬆️  Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel

# Install Python dependencies
echo "📚 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
fi

# Install development dependencies (pytest, black, etc.)
echo "🧪 Installing development dependencies..."
pip install \
  pytest>=7.0.0 \
  pytest-django>=4.5.0 \
  pytest-cov>=4.0.0 \
  black>=23.0.0 \
  ruff>=0.1.0 \
  ipython>=8.0.0 \
  django-extensions>=3.2.0

# Create Django superuser prompt
echo ""
echo "✨ Development environment setup complete!"
echo ""
echo "📝 Quick start:"
echo "  - Run migrations: python manage.py migrate"
echo "  - Create superuser: python manage.py createsuperuser"
echo "  - Start dev server: python manage.py runserver"
echo "  - Run tests: pytest"
echo ""
