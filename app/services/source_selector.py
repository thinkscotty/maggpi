"""
Intelligent source selection for content diversity and relevance.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from app import db
from app.models import Source, SourceTopic, ContentItem, ScrapingLog

logger = logging.getLogger(__name__)


class SourceSelector:
    """
    Selects and ranks sources for a topic based on various factors.
    Ensures diversity and quality in content selection.
    """

    def __init__(self, topic_id: int):
        self.topic_id = topic_id

    def get_sources_for_topic(self) -> List[Source]:
        """Get all enabled sources associated with a topic."""
        source_topics = SourceTopic.query.filter_by(topic_id=self.topic_id).all()
        sources = [st.source for st in source_topics if st.source and st.source.enabled]
        return sources

    def rank_sources(self, sources: List[Source]) -> List[Source]:
        """
        Rank sources by reliability and recent performance.
        Returns sources sorted by score (highest first).
        """
        scored_sources = []

        for source in sources:
            score = self._calculate_source_score(source)
            scored_sources.append((source, score))

        # Sort by score descending
        scored_sources.sort(key=lambda x: x[1], reverse=True)

        return [s[0] for s in scored_sources]

    def _calculate_source_score(self, source: Source) -> float:
        """
        Calculate a score for a source based on multiple factors.
        """
        score = source.weight * 100  # Base score from configured weight

        # Check recent scraping success rate
        recent_time = datetime.utcnow() - timedelta(days=7)
        recent_logs = ScrapingLog.query.filter(
            ScrapingLog.source_id == source.id,
            ScrapingLog.created_at > recent_time
        ).all()

        if recent_logs:
            success_count = sum(1 for log in recent_logs if log.status == 'success')
            success_rate = success_count / len(recent_logs)
            score += success_rate * 30  # Up to 30 points for reliability

        # Check content freshness
        latest_content = ContentItem.query.filter_by(source_id=source.id) \
            .order_by(ContentItem.scraped_at.desc()).first()

        if latest_content and latest_content.scraped_at:
            hours_since_update = (datetime.utcnow() - latest_content.scraped_at).total_seconds() / 3600
            if hours_since_update < 6:
                score += 20  # Bonus for recently active sources
            elif hours_since_update > 48:
                score -= 10  # Penalty for stale sources

        return score

    def select_diverse_sources(self, sources: List[Source], max_count: int = 5) -> List[Source]:
        """
        Select a diverse set of sources, avoiding over-reliance on any single source.
        """
        if len(sources) <= max_count:
            return sources

        ranked = self.rank_sources(sources)
        selected = []

        # Always include top-ranked source
        if ranked:
            selected.append(ranked[0])

        # Add sources with different types for diversity
        source_types_included = {ranked[0].source_type} if ranked else set()

        for source in ranked[1:]:
            if len(selected) >= max_count:
                break

            # Prefer sources of different types for diversity
            if source.source_type not in source_types_included:
                selected.append(source)
                source_types_included.add(source.source_type)
            elif len(selected) < max_count - 1:
                # Fill remaining slots with best remaining sources
                selected.append(source)

        return selected


def suggest_sources_for_topic(topic_name: str) -> List[Dict[str, Any]]:
    """
    Suggest potential sources for a new topic based on common patterns.
    Returns a list of suggested source configurations.
    """
    topic_lower = topic_name.lower()

    # Common source patterns for different topic types
    suggestions = []

    # News-related topics
    if any(word in topic_lower for word in ['news', 'headlines', 'current']):
        suggestions.extend([
            {
                'name': f'{topic_name.lower().replace(" ", "_")}_reddit',
                'display_name': f'Reddit {topic_name}',
                'type': 'rss',
                'url': f'https://www.reddit.com/r/{topic_lower.replace(" ", "")}.rss',
                'weight': 0.8
            },
            {
                'name': f'{topic_name.lower().replace(" ", "_")}_google_news',
                'display_name': f'Google News - {topic_name}',
                'type': 'rss',
                'url': f'https://news.google.com/rss/search?q={topic_lower.replace(" ", "+")}',
                'weight': 0.9
            }
        ])

    # Tech topics
    if any(word in topic_lower for word in ['tech', 'technology', 'programming', 'software']):
        suggestions.extend([
            {
                'name': 'hackernews',
                'display_name': 'Hacker News',
                'type': 'api',
                'url': 'https://hacker-news.firebaseio.com/v0/',
                'weight': 0.9
            },
            {
                'name': 'reddit_technology',
                'display_name': 'Reddit Technology',
                'type': 'rss',
                'url': 'https://www.reddit.com/r/technology.rss',
                'weight': 0.7
            }
        ])

    # Science topics
    if any(word in topic_lower for word in ['science', 'research', 'discovery']):
        suggestions.extend([
            {
                'name': 'reddit_science',
                'display_name': 'Reddit Science',
                'type': 'rss',
                'url': 'https://www.reddit.com/r/science.rss',
                'weight': 0.8
            },
            {
                'name': 'sciencedaily',
                'display_name': 'Science Daily',
                'type': 'rss',
                'url': 'https://www.sciencedaily.com/rss/all.xml',
                'weight': 0.9
            }
        ])

    # Quote topics
    if any(word in topic_lower for word in ['quote', 'inspiration', 'motivation']):
        suggestions.extend([
            {
                'name': 'quotable',
                'display_name': 'Quotable API',
                'type': 'api',
                'url': 'https://api.quotable.io/',
                'weight': 1.0
            },
            {
                'name': 'zenquotes',
                'display_name': 'ZenQuotes',
                'type': 'api',
                'url': 'https://zenquotes.io/api/',
                'weight': 0.9
            }
        ])

    # Default suggestions if nothing matches
    if not suggestions:
        suggestions.append({
            'name': f'{topic_name.lower().replace(" ", "_")}_reddit',
            'display_name': f'Reddit {topic_name}',
            'type': 'rss',
            'url': f'https://www.reddit.com/r/{topic_lower.replace(" ", "")}.rss',
            'weight': 0.7
        })

    return suggestions
