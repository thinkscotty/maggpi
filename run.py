#!/usr/bin/env python3
"""
Pi Content Aggregator - Entry Point
A web application that scrapes, summarizes, and displays curated content.
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Run on all interfaces so other devices on network can access
    app.run(host='0.0.0.0', port=5000, debug=False)
