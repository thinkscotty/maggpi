"""
Main routes for content display.
"""

from flask import Blueprint, render_template
from app.models import Topic, Summary

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Display the main content page with all topic summaries."""
    topics = Topic.query.filter_by(enabled=True).all()

    # Get the latest summary for each topic
    topic_data = []
    for topic in topics:
        latest_summary = Summary.query.filter_by(topic_id=topic.id) \
            .order_by(Summary.created_at.desc()).first()

        topic_data.append({
            'topic': topic,
            'summary': latest_summary
        })

    return render_template('index.html', topic_data=topic_data)


@main_bp.route('/topic/<string:topic_name>')
def topic_detail(topic_name):
    """Display detailed view of a specific topic."""
    topic = Topic.query.filter_by(name=topic_name).first_or_404()
    latest_summary = Summary.query.filter_by(topic_id=topic.id) \
        .order_by(Summary.created_at.desc()).first()

    # Get recent content items for this topic
    from app.models import ContentItem
    recent_items = ContentItem.query.filter_by(topic_id=topic.id) \
        .order_by(ContentItem.scraped_at.desc()).limit(20).all()

    return render_template('topic.html',
                           topic=topic,
                           summary=latest_summary,
                           items=recent_items)
