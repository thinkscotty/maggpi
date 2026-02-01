"""
AI-powered content summarization using Google Gemini API.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app import db
from app.config import Config
from app.models import Topic, ContentItem, Summary

logger = logging.getLogger(__name__)


class GeminiSummarizer:
    """Content summarizer using Google's Gemini API."""

    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.model = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of Gemini client."""
        if self._initialized:
            return True

        if not self.api_key:
            logger.warning('Gemini API key not configured')
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f'Failed to initialize Gemini: {e}')
            return False

    def summarize_content(self, items: List[ContentItem], topic: Topic) -> Optional[str]:
        """
        Summarize a list of content items for a topic.
        Returns the summary text or None if summarization fails.
        """
        if not items:
            return None

        if not self._ensure_initialized():
            # Fallback to simple extraction
            return self._simple_summary(items, topic)

        # Prepare content for summarization
        content_text = self._prepare_content(items)

        prompt = f"""You are a content curator creating a brief, engaging summary for a "{topic.display_name}" feed.

Here are the latest items collected from various sources:

{content_text}

Please create a concise summary (2-4 paragraphs) that:
1. Highlights the most interesting and relevant information
2. Connects related themes or stories where appropriate
3. Maintains source attribution (mention where key information came from)
4. Uses clear, accessible language
5. Focuses on what's most valuable or actionable for the reader

For quotes or facts, include the actual quote/fact with attribution.
For news, summarize the key developments and their significance.

Summary:"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f'Gemini summarization failed: {e}')
            return self._simple_summary(items, topic)

    def _prepare_content(self, items: List[ContentItem]) -> str:
        """Prepare content items for the summarization prompt."""
        content_parts = []

        for i, item in enumerate(items[:15], 1):  # Limit to 15 items
            source_name = item.source.display_name if item.source else 'Unknown'
            title = item.title or 'No title'
            content = item.content or ''

            # Truncate long content
            if len(content) > 500:
                content = content[:500] + '...'

            part = f"[{i}] Source: {source_name}\n"
            part += f"Title: {title}\n"
            if content:
                part += f"Content: {content}\n"
            if item.url:
                part += f"URL: {item.url}\n"

            content_parts.append(part)

        return '\n---\n'.join(content_parts)

    def _simple_summary(self, items: List[ContentItem], topic: Topic) -> str:
        """
        Create a simple summary without AI.
        Used as fallback when Gemini is unavailable.
        """
        summary_parts = [f"## {topic.display_name}\n"]
        summary_parts.append(f"*{len(items)} items collected*\n")

        # Group items by source
        by_source = {}
        for item in items:
            source_name = item.source.display_name if item.source else 'Unknown'
            if source_name not in by_source:
                by_source[source_name] = []
            by_source[source_name].append(item)

        for source_name, source_items in by_source.items():
            summary_parts.append(f"\n**From {source_name}:**")
            for item in source_items[:5]:
                title = item.title or 'Untitled'
                if item.url:
                    summary_parts.append(f"- [{title}]({item.url})")
                else:
                    summary_parts.append(f"- {title}")

        return '\n'.join(summary_parts)

    def rank_content(self, items: List[ContentItem]) -> List[ContentItem]:
        """
        Rank content items by relevance and interest.
        Uses metadata scores where available.
        """
        def score_item(item: ContentItem) -> float:
            score = 0.0

            # Source weight
            if item.source:
                score += item.source.weight * 10

            # Recency bonus (items from last 6 hours get boost)
            if item.scraped_at:
                age_hours = (datetime.utcnow() - item.scraped_at).total_seconds() / 3600
                if age_hours < 6:
                    score += (6 - age_hours) * 2

            # Metadata-based scoring (e.g., HN score)
            metadata = item.metadata or {}
            if 'score' in metadata:
                score += min(metadata['score'] / 10, 20)  # Cap at 20
            if 'comments' in metadata:
                score += min(metadata['comments'] / 20, 10)  # Cap at 10

            # Content quality indicators
            if item.title and len(item.title) > 20:
                score += 2
            if item.content and len(item.content) > 100:
                score += 3

            return score

        return sorted(items, key=score_item, reverse=True)


def summarize_topic(topic_id: int) -> Optional[Summary]:
    """
    Create a summary for a topic using recent content.
    Returns the created Summary object or None.
    """
    topic = Topic.query.get(topic_id)
    if not topic:
        return None

    # Get recent content (last 24 hours or since last summary)
    cutoff = datetime.utcnow() - timedelta(hours=24)

    items = ContentItem.query.filter(
        ContentItem.topic_id == topic_id,
        ContentItem.scraped_at > cutoff
    ).order_by(ContentItem.scraped_at.desc()).limit(Config.MAX_ITEMS_PER_TOPIC).all()

    if not items:
        logger.info(f'No recent content for topic {topic.name}')
        return None

    # Initialize summarizer and process content
    summarizer = GeminiSummarizer()

    # Rank items by relevance
    ranked_items = summarizer.rank_content(items)

    # Generate summary
    summary_text = summarizer.summarize_content(ranked_items, topic)

    if not summary_text:
        return None

    # Get sources used
    sources_used = list(set(
        item.source.name for item in ranked_items if item.source
    ))

    # Create summary record
    summary = Summary(
        topic_id=topic_id,
        content=summary_text,
        sources_used=sources_used,
        item_count=len(ranked_items)
    )
    db.session.add(summary)
    db.session.commit()

    logger.info(f'Created summary for topic {topic.name} with {len(ranked_items)} items')
    return summary


def summarize_all_topics():
    """Create summaries for all enabled topics."""
    topics = Topic.query.filter_by(enabled=True).all()

    for topic in topics:
        try:
            summarize_topic(topic.id)
        except Exception as e:
            logger.error(f'Failed to summarize topic {topic.name}: {e}')
