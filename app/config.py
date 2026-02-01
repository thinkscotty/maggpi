"""
Application configuration for Pi Content Aggregator.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Application configuration class."""

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'data' / 'aggregator.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    NEWSAPI_KEY = os.getenv('NEWSAPI_KEY', '')
    OPENWEATHERMAP_KEY = os.getenv('OPENWEATHERMAP_KEY', '')

    # Configuration file paths
    TOPICS_CONFIG = BASE_DIR / 'config' / 'topics.yaml'
    SOURCES_CONFIG = BASE_DIR / 'config' / 'sources.yaml'

    # Scraping settings
    REQUEST_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RATE_LIMIT_DELAY = 1  # seconds between requests

    # Content settings
    CONTENT_RETENTION_DAYS = 7  # How long to keep old content
    MAX_ITEMS_PER_SOURCE = 10  # Max items to fetch per source
    MAX_ITEMS_PER_TOPIC = 20  # Max items to display per topic

    # Weather location (user should configure this)
    WEATHER_LOCATION = os.getenv('WEATHER_LOCATION', 'New York,US')
