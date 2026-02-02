"""
Main routes for content display.
"""

from flask import Blueprint, render_template
from sqlalchemy import and_
from sqlalchemy.orm import subqueryload
from app.models import Topic, Summary
from app import db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Display the main content page with all topic summaries."""
    topics = Topic.query.filter_by(enabled=True).all()

    # Get the latest summary for each topic in a single query
    # Using a subquery to find the max created_at for each topic
    from sqlalchemy.sql import func
    subq = db.session.query(
        Summary.topic_id,
        func.max(Summary.created_at).label('max_created')
    ).group_by(Summary.topic_id).subquery()

    latest_summaries = db.session.query(Summary).join(
        subq,
        and_(
            Summary.topic_id == subq.c.topic_id,
            Summary.created_at == subq.c.max_created
        )
    ).all()

    # Create a dictionary for quick lookup
    summary_by_topic = {s.topic_id: s for s in latest_summaries}

    # Build topic data
    topic_data = []
    for topic in topics:
        topic_data.append({
            'topic': topic,
            'summary': summary_by_topic.get(topic.id)
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
