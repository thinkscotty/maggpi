"""
REST API routes for external access.
"""

from flask import Blueprint, jsonify, request
from app.models import Topic, Source, Summary, ContentItem

api_bp = Blueprint('api', __name__)


@api_bp.route('/topics')
def list_topics():
    """List all topics."""
    topics = Topic.query.filter_by(enabled=True).all()
    return jsonify({
        'topics': [t.to_dict() for t in topics]
    })


@api_bp.route('/sources')
def list_sources():
    """List all sources."""
    sources = Source.query.filter_by(enabled=True).all()
    return jsonify({
        'sources': [s.to_dict() for s in sources]
    })


@api_bp.route('/content')
def all_content():
    """Get all current summaries."""
    topics = Topic.query.filter_by(enabled=True).all()

    content = []
    for topic in topics:
        latest_summary = Summary.query.filter_by(topic_id=topic.id) \
            .order_by(Summary.created_at.desc()).first()

        if latest_summary:
            content.append(latest_summary.to_dict())

    return jsonify({
        'content': content
    })


@api_bp.route('/content/<string:topic_name>')
def topic_content(topic_name):
    """Get summary for a specific topic."""
    topic = Topic.query.filter_by(name=topic_name).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    latest_summary = Summary.query.filter_by(topic_id=topic.id) \
        .order_by(Summary.created_at.desc()).first()

    if not latest_summary:
        return jsonify({'error': 'No content available for this topic'}), 404

    return jsonify(latest_summary.to_dict())


@api_bp.route('/raw/<string:topic_name>')
def raw_content(topic_name):
    """Get raw scraped data for a topic (pre-summary)."""
    topic = Topic.query.filter_by(name=topic_name).first()

    if not topic:
        return jsonify({'error': 'Topic not found'}), 404

    # Get recent content items
    limit = request.args.get('limit', 20, type=int)
    items = ContentItem.query.filter_by(topic_id=topic.id) \
        .order_by(ContentItem.scraped_at.desc()).limit(limit).all()

    return jsonify({
        'topic': topic.to_dict(),
        'items': [item.to_dict() for item in items]
    })


@api_bp.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'pi-content-aggregator'
    })


@api_bp.route('/status')
def status():
    """Get application status."""
    from app.models import ScrapingLog
    from datetime import datetime, timedelta

    # Get recent scraping activity
    recent_time = datetime.utcnow() - timedelta(hours=24)
    recent_logs = ScrapingLog.query.filter(ScrapingLog.created_at > recent_time).all()

    success_count = sum(1 for log in recent_logs if log.status == 'success')
    error_count = sum(1 for log in recent_logs if log.status == 'error')

    topic_count = Topic.query.filter_by(enabled=True).count()
    source_count = Source.query.filter_by(enabled=True).count()

    return jsonify({
        'topics_active': topic_count,
        'sources_active': source_count,
        'scrapes_24h': {
            'success': success_count,
            'error': error_count
        }
    })
