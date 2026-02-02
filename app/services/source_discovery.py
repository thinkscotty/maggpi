"""
AI-powered source discovery using Google Gemini API.
Finds RSS feeds and APIs for topics.
"""

import json
import logging
import requests
from typing import List, Dict, Optional

from app import db
from app.config import Config
from app.models import Topic, Source, SourceTopic

logger = logging.getLogger(__name__)


class SourceDiscovery:
    """Discovers content sources for topics using Gemini AI."""

    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.client = None
        self._types = None
        self._errors = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of Gemini client."""
        if self._initialized:
            return True

        if not self.api_key:
            logger.warning('Gemini API key not configured')
            return False

        try:
            from google import genai
            from google.genai import types
            from google.genai import errors
            self.client = genai.Client(api_key=self.api_key)
            self._types = types
            self._errors = errors
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f'Failed to initialize Gemini: {e}')
            return False

    def discover_sources_for_topic(self, topic: Topic, count: int = 5) -> List[Dict]:
        """
        Use Gemini to discover RSS feeds and APIs for a topic.
        Returns a list of source dictionaries.
        """
        if not self._ensure_initialized():
            logger.warning('Cannot discover sources: Gemini not initialized')
            return []

        system_instruction = """You are an expert at finding RSS feeds and public APIs for content aggregation.

Your task is to suggest real, working RSS feeds and public APIs for a given topic.

IMPORTANT RULES:
1. Only suggest REAL, VERIFIED sources that actually exist
2. Prefer RSS feeds as they are most reliable
3. Include a mix of major news outlets, specialized sites, and Reddit communities
4. For APIs, only suggest ones that don't require authentication or have free tiers
5. Reddit RSS feeds are always available at: https://www.reddit.com/r/SUBREDDIT.rss

You MUST respond with ONLY valid JSON in this exact format:
{
    "sources": [
        {
            "name": "source_name_lowercase",
            "display_name": "Human Readable Name",
            "type": "rss",
            "url": "https://example.com/feed.xml",
            "weight": 0.8
        }
    ]
}

Types can be: "rss", "api", or "html"
Weight should be between 0.5 and 1.0 (higher = more important)"""

        user_content = f"""Find {count} RSS feeds or APIs for the topic: "{topic.display_name}"

Topic description: {topic.description or 'No description provided'}

Suggest popular, reliable sources. Include at least one Reddit community if relevant.
Respond with JSON only, no other text."""

        try:
            response = self.client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=user_content,
                config=self._types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )

            # Parse the JSON response
            response_text = response.text.strip()

            # Handle markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                # Remove first and last lines (```json and ```)
                response_text = '\n'.join(lines[1:-1])

            sources_data = json.loads(response_text)
            discovered = sources_data.get('sources', [])

            # Validate and filter sources
            validated_sources = []
            for source in discovered:
                if self._validate_source(source):
                    validated_sources.append(source)

            logger.info(f'Discovered {len(validated_sources)} sources for topic {topic.name}')
            return validated_sources

        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse Gemini response as JSON: {e}')
            return []
        except self._errors.APIError as e:
            logger.error(f'Gemini API error during source discovery: {e.code} - {e.message}')
            return []
        except Exception as e:
            logger.error(f'Source discovery failed: {e}')
            return []

    def _validate_source(self, source: Dict) -> bool:
        """Validate that a source has required fields."""
        required = ['name', 'display_name', 'type', 'url']
        for field in required:
            if field not in source or not source[field]:
                return False

        # Validate type
        if source['type'] not in ['rss', 'api', 'html']:
            return False

        # Validate URL format
        url = source['url']
        if not url.startswith(('http://', 'https://')):
            return False

        return True

    def _check_url_accessible(self, url: str) -> bool:
        """Check if a URL is accessible (optional validation)."""
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            return response.status_code < 400
        except Exception:
            return False

    def create_sources_for_topic(self, topic: Topic, count: int = 5) -> int:
        """
        Discover and create sources for a topic in the database.
        Returns the number of sources created.
        """
        discovered = self.discover_sources_for_topic(topic, count)
        created_count = 0

        for source_data in discovered:
            # Check if source already exists
            existing = Source.query.filter_by(name=source_data['name']).first()
            if existing:
                # Just link to topic if not already linked
                existing_link = SourceTopic.query.filter_by(
                    source_id=existing.id,
                    topic_id=topic.id
                ).first()
                if not existing_link:
                    st = SourceTopic(source_id=existing.id, topic_id=topic.id)
                    db.session.add(st)
                continue

            # Create new source
            source = Source(
                name=source_data['name'],
                display_name=source_data['display_name'],
                source_type=source_data['type'],
                url=source_data['url'],
                weight=source_data.get('weight', 0.7),
                enabled=True
            )
            db.session.add(source)
            db.session.flush()  # Get the ID

            # Link to topic
            st = SourceTopic(source_id=source.id, topic_id=topic.id)
            db.session.add(st)
            created_count += 1

        db.session.commit()
        logger.info(f'Created {created_count} new sources for topic {topic.name}')
        return created_count

    def discover_additional_source(self, topic: Topic) -> Optional[Dict]:
        """
        Discover one additional source for a topic that doesn't already exist.
        """
        if not self._ensure_initialized():
            return None

        # Get existing source names for this topic
        existing_sources = Source.query.join(SourceTopic).filter(
            SourceTopic.topic_id == topic.id
        ).all()
        existing_names = [s.name for s in existing_sources]
        existing_urls = [s.url for s in existing_sources]

        system_instruction = """You are an expert at finding RSS feeds and public APIs for content aggregation.

Your task is to suggest ONE new, real RSS feed or API for a given topic.

IMPORTANT RULES:
1. Only suggest REAL, VERIFIED sources that actually exist
2. The source must be DIFFERENT from the ones already being used
3. Prefer RSS feeds as they are most reliable
4. Reddit RSS feeds are always available at: https://www.reddit.com/r/SUBREDDIT.rss

You MUST respond with ONLY valid JSON in this exact format:
{
    "source": {
        "name": "source_name_lowercase",
        "display_name": "Human Readable Name",
        "type": "rss",
        "url": "https://example.com/feed.xml",
        "weight": 0.8
    }
}"""

        user_content = f"""Find ONE new RSS feed or API for the topic: "{topic.display_name}"

Topic description: {topic.description or 'No description provided'}

ALREADY USING these sources (suggest something DIFFERENT):
{', '.join(existing_names)}

Suggest a popular, reliable source that is NOT in the list above.
Respond with JSON only, no other text."""

        try:
            response = self.client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=user_content,
                config=self._types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
            )

            response_text = response.text.strip()

            # Handle markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1])

            data = json.loads(response_text)
            source = data.get('source')

            if source and self._validate_source(source):
                # Check it's not a duplicate
                if source['name'] not in existing_names and source['url'] not in existing_urls:
                    return source

            return None

        except Exception as e:
            logger.error(f'Failed to discover additional source: {e}')
            return None


def discover_sources_for_new_topic(topic_id: int, count: int = 5) -> int:
    """
    Convenience function to discover sources for a newly created topic.
    Returns number of sources created.
    """
    topic = Topic.query.get(topic_id)
    if not topic:
        return 0

    discovery = SourceDiscovery()
    return discovery.create_sources_for_topic(topic, count)


def discover_additional_sources_for_all_topics() -> Dict[str, int]:
    """
    Discover one additional source for each enabled topic.
    Returns a dict of topic_name -> sources_added.
    """
    topics = Topic.query.filter_by(enabled=True).all()
    results = {}

    discovery = SourceDiscovery()

    for topic in topics:
        source_data = discovery.discover_additional_source(topic)
        if source_data:
            # Check if source already exists
            existing = Source.query.filter_by(name=source_data['name']).first()
            if not existing:
                source = Source(
                    name=source_data['name'],
                    display_name=source_data['display_name'],
                    source_type=source_data['type'],
                    url=source_data['url'],
                    weight=source_data.get('weight', 0.7),
                    enabled=True
                )
                db.session.add(source)
                db.session.flush()

                st = SourceTopic(source_id=source.id, topic_id=topic.id)
                db.session.add(st)
                results[topic.name] = 1
            else:
                results[topic.name] = 0
        else:
            results[topic.name] = 0

    db.session.commit()
    return results
