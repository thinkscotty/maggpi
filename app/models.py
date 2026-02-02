"""
Database models for Maggpi.
"""

from datetime import datetime
from app import db


class Topic(db.Model):
    """A content topic (e.g., Tech News, Science)."""

    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    enabled = db.Column(db.Boolean, default=True)
    refresh_hours = db.Column(db.Integer, default=4)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    content_items = db.relationship('ContentItem', backref='topic', lazy='dynamic')
    summaries = db.relationship('Summary', backref='topic', lazy='dynamic')

    def __repr__(self):
        return f'<Topic {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'enabled': self.enabled,
            'refresh_hours': self.refresh_hours
        }


class Source(db.Model):
    """A content source (e.g., Hacker News, BBC RSS)."""

    __tablename__ = 'sources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    source_type = db.Column(db.String(20), nullable=False)  # api, rss, html
    url = db.Column(db.String(500), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    weight = db.Column(db.Float, default=1.0)  # For source selection ranking
    config = db.Column(db.JSON)  # Additional source-specific configuration
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    content_items = db.relationship('ContentItem', backref='source', lazy='dynamic')
    topics = db.relationship('SourceTopic', backref='source', lazy='dynamic')

    def __repr__(self):
        return f'<Source {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'source_type': self.source_type,
            'url': self.url,
            'enabled': self.enabled,
            'weight': self.weight,
            'topics': [st.topic.name for st in self.topics if st.topic]
        }


class SourceTopic(db.Model):
    """Association between sources and topics."""

    __tablename__ = 'source_topics'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)

    topic = db.relationship('Topic')

    def __repr__(self):
        return f'<SourceTopic {self.source_id}-{self.topic_id}>'


class ContentItem(db.Model):
    """A scraped content item from a source."""

    __tablename__ = 'content_items'
    __table_args__ = (
        db.Index('idx_content_items_topic_id', 'topic_id'),
        db.Index('idx_content_items_source_id', 'source_id'),
        db.Index('idx_content_items_scraped_at', 'scraped_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    external_id = db.Column(db.String(200))  # ID from the source (e.g., article ID)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    author = db.Column(db.String(200))
    published_at = db.Column(db.DateTime)
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    extra_data = db.Column(db.JSON)  # Additional data (e.g., score, comments)

    def __repr__(self):
        return f'<ContentItem {self.id}: {self.title[:50] if self.title else "No title"}>'

    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source.name if self.source else None,
            'topic': self.topic.name if self.topic else None,
            'title': self.title,
            'content': self.content,
            'url': self.url,
            'author': self.author,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None
        }


class Summary(db.Model):
    """An AI-generated summary for a topic."""

    __tablename__ = 'summaries'
    __table_args__ = (
        db.Index('idx_summaries_topic_id', 'topic_id'),
        db.Index('idx_summaries_created_at', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sources_used = db.Column(db.JSON)  # List of source names used
    item_count = db.Column(db.Integer)  # Number of items summarized
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Summary {self.id} for topic {self.topic_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'topic': self.topic.name if self.topic else None,
            'topic_display_name': self.topic.display_name if self.topic else None,
            'content': self.content,
            'sources_used': self.sources_used,
            'item_count': self.item_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ScrapingLog(db.Model):
    """Log of scraping operations for monitoring."""

    __tablename__ = 'scraping_logs'
    __table_args__ = (
        db.Index('idx_scraping_logs_source_id', 'source_id'),
        db.Index('idx_scraping_logs_topic_id', 'topic_id'),
        db.Index('idx_scraping_logs_created_at', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'))
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'))
    status = db.Column(db.String(20))  # success, error, skipped
    message = db.Column(db.Text)
    items_fetched = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    source = db.relationship('Source')
    topic = db.relationship('Topic')

    def __repr__(self):
        return f'<ScrapingLog {self.id}: {self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'source': self.source.name if self.source else None,
            'topic': self.topic.name if self.topic else None,
            'status': self.status,
            'message': self.message,
            'items_fetched': self.items_fetched,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
