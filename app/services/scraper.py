"""
Web scraping engine with support for multiple source types.
"""

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
import feedparser
from bs4 import BeautifulSoup

from app import db
from app.config import Config
from app.models import Source, ContentItem, ScrapingLog

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers."""

    def __init__(self, source: Source, topic_id: int):
        self.source = source
        self.topic_id = topic_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PiContentAggregator/1.0 (Educational Project)'
        })

    def __del__(self):
        """Cleanup: Close the requests session."""
        if hasattr(self, 'session') and self.session:
            self.session.close()

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch content from the source. Returns list of content items."""
        pass

    def save_items(self, items: List[Dict[str, Any]]) -> int:
        """Save fetched items to the database."""
        saved_count = 0
        for item in items[:Config.MAX_ITEMS_PER_SOURCE]:
            # Check for duplicates by external_id or URL
            existing = None
            if item.get('external_id'):
                existing = ContentItem.query.filter_by(
                    source_id=self.source.id,
                    external_id=item['external_id']
                ).first()
            elif item.get('url'):
                existing = ContentItem.query.filter_by(
                    source_id=self.source.id,
                    url=item['url']
                ).first()

            if existing:
                continue

            content_item = ContentItem(
                source_id=self.source.id,
                topic_id=self.topic_id,
                external_id=item.get('external_id'),
                title=item.get('title', '')[:500],
                content=item.get('content', ''),
                url=item.get('url', '')[:1000],
                author=item.get('author', '')[:200] if item.get('author') else None,
                published_at=item.get('published_at'),
                extra_data=item.get('metadata', {})
            )
            db.session.add(content_item)
            saved_count += 1

        db.session.commit()
        return saved_count

    def log_result(self, status: str, message: str, items_fetched: int = 0):
        """Log the scraping result."""
        log = ScrapingLog(
            source_id=self.source.id,
            topic_id=self.topic_id,
            status=status,
            message=message,
            items_fetched=items_fetched
        )
        db.session.add(log)
        db.session.commit()

    def run(self) -> int:
        """Run the scraper and return number of items saved."""
        try:
            items = self.fetch()
            saved = self.save_items(items)
            self.log_result('success', f'Fetched {len(items)} items, saved {saved} new', saved)
            return saved
        except requests.RequestException as e:
            self.log_result('error', f'Request failed: {str(e)}')
            logger.error(f'Scraper error for {self.source.name}: {e}')
            return 0
        except Exception as e:
            self.log_result('error', f'Unexpected error: {str(e)}')
            logger.error(f'Scraper error for {self.source.name}: {e}')
            return 0


class APIScraper(BaseScraper):
    """Scraper for JSON API endpoints."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch content from a JSON API."""
        config = self.source.config or {}
        method = config.get('method', 'GET')
        params = config.get('params', {})
        headers = config.get('headers', {})

        response = self.session.request(
            method,
            self.source.url,
            params=params,
            headers=headers,
            timeout=Config.REQUEST_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()

        # Extract items based on configured path
        items_path = config.get('items_path', '')
        if items_path:
            for key in items_path.split('.'):
                data = data.get(key, [])

        if not isinstance(data, list):
            data = [data]

        # Map fields based on configuration
        field_map = config.get('field_map', {
            'title': 'title',
            'content': 'content',
            'url': 'url',
            'external_id': 'id',
            'author': 'author'
        })

        items = []
        for raw_item in data:
            item = {}
            for our_field, their_field in field_map.items():
                if their_field and their_field in raw_item:
                    item[our_field] = raw_item[their_field]
            item['metadata'] = raw_item
            items.append(item)

        time.sleep(Config.RATE_LIMIT_DELAY)
        return items


class RSSScraper(BaseScraper):
    """Scraper for RSS/Atom feeds."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch content from an RSS feed."""
        feed = feedparser.parse(self.source.url)

        items = []
        for entry in feed.entries:
            # Parse published date
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_at = datetime(*entry.updated_parsed[:6])

            # Get content
            content = ''
            if hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'content'):
                content = entry.content[0].value if entry.content else ''

            # Clean HTML from content
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                content = soup.get_text(separator=' ', strip=True)

            items.append({
                'external_id': getattr(entry, 'id', None) or getattr(entry, 'link', None),
                'title': getattr(entry, 'title', 'No title'),
                'content': content[:2000],  # Limit content length
                'url': getattr(entry, 'link', ''),
                'author': getattr(entry, 'author', None),
                'published_at': published_at,
                'metadata': {
                    'feed_title': feed.feed.get('title', ''),
                    'tags': [tag.term for tag in getattr(entry, 'tags', [])]
                }
            })

        time.sleep(Config.RATE_LIMIT_DELAY)
        return items


class HTMLScraper(BaseScraper):
    """Scraper for HTML pages using BeautifulSoup."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch content from an HTML page."""
        config = self.source.config or {}

        response = self.session.get(
            self.source.url,
            timeout=Config.REQUEST_TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Get selectors from config
        item_selector = config.get('item_selector', 'article')
        title_selector = config.get('title_selector', 'h2')
        content_selector = config.get('content_selector', 'p')
        link_selector = config.get('link_selector', 'a')

        items = []
        for article in soup.select(item_selector)[:Config.MAX_ITEMS_PER_SOURCE]:
            title_elem = article.select_one(title_selector)
            content_elem = article.select_one(content_selector)
            link_elem = article.select_one(link_selector)

            title = title_elem.get_text(strip=True) if title_elem else ''
            content = content_elem.get_text(strip=True) if content_elem else ''
            url = ''
            if link_elem:
                url = link_elem.get('href', '')
                # Handle relative URLs
                if url and not url.startswith('http'):
                    from urllib.parse import urljoin
                    url = urljoin(self.source.url, url)

            if title:  # Only add items with titles
                items.append({
                    'title': title[:500],
                    'content': content[:2000],
                    'url': url[:1000],
                    'external_id': url or title
                })

        time.sleep(Config.RATE_LIMIT_DELAY)
        return items


# Specialized scrapers for known APIs

class HackerNewsScraper(APIScraper):
    """Specialized scraper for Hacker News API."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch top stories from Hacker News."""
        # Get top story IDs
        response = self.session.get(
            'https://hacker-news.firebaseio.com/v0/topstories.json',
            timeout=Config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        story_ids = response.json()[:Config.MAX_ITEMS_PER_SOURCE]

        items = []
        for story_id in story_ids:
            try:
                story_response = self.session.get(
                    f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
                    timeout=Config.REQUEST_TIMEOUT
                )
                story = story_response.json()

                if story and story.get('type') == 'story':
                    items.append({
                        'external_id': str(story_id),
                        'title': story.get('title', ''),
                        'content': story.get('text', ''),
                        'url': story.get('url', f'https://news.ycombinator.com/item?id={story_id}'),
                        'author': story.get('by'),
                        'published_at': datetime.fromtimestamp(story.get('time', 0)),
                        'metadata': {
                            'score': story.get('score', 0),
                            'comments': story.get('descendants', 0)
                        }
                    })

                time.sleep(0.1)  # Small delay between requests
            except Exception as e:
                logger.warning(f'Failed to fetch HN story {story_id}: {e}')
                continue

        return items


class QuotableScraper(APIScraper):
    """Specialized scraper for Quotable API."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch random quotes from Quotable API."""
        items = []

        for _ in range(5):  # Get 5 quotes
            try:
                response = self.session.get(
                    'https://api.quotable.io/random',
                    timeout=Config.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                quote = response.json()

                items.append({
                    'external_id': quote.get('_id'),
                    'title': quote.get('content', '')[:100],
                    'content': quote.get('content', ''),
                    'author': quote.get('author'),
                    'metadata': {
                        'tags': quote.get('tags', []),
                        'length': quote.get('length', 0)
                    }
                })

                time.sleep(0.2)
            except Exception as e:
                logger.warning(f'Failed to fetch quote: {e}')
                continue

        return items


def get_scraper(source: Source, topic_id: int) -> BaseScraper:
    """
    Get the appropriate scraper for a source.
    Returns specialized scraper if available, otherwise generic one.
    """
    # Specialized scrapers for known sources
    specialized_scrapers = {
        'hackernews': HackerNewsScraper,
        'hacker_news': HackerNewsScraper,
        'quotable': QuotableScraper,
    }

    scraper_class = specialized_scrapers.get(source.name.lower())

    if not scraper_class:
        # Use generic scraper based on source type
        type_scrapers = {
            'api': APIScraper,
            'rss': RSSScraper,
            'html': HTMLScraper,
        }
        scraper_class = type_scrapers.get(source.source_type, APIScraper)

    return scraper_class(source, topic_id)


def scrape_source(source: Source, topic_id: int) -> int:
    """Scrape a single source for a topic."""
    scraper = get_scraper(source, topic_id)
    return scraper.run()


def scrape_topic(topic_id: int) -> int:
    """Scrape all sources for a topic."""
    from app.models import Topic, SourceTopic

    topic = Topic.query.get(topic_id)
    if not topic or not topic.enabled:
        return 0

    total_items = 0
    source_topics = SourceTopic.query.filter_by(topic_id=topic_id).all()

    for st in source_topics:
        source = st.source
        if source and source.enabled:
            items = scrape_source(source, topic_id)
            total_items += items

    return total_items
