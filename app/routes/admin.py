"""
Admin routes for configuration and management.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models import Topic, Source, SourceTopic, ScrapingLog, ContentItem, Summary
from app.services.config_loader import save_topics_config, save_sources_config

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
def dashboard():
    """Admin dashboard overview."""
    topics = Topic.query.all()
    sources = Source.query.all()
    recent_logs = ScrapingLog.query.order_by(ScrapingLog.created_at.desc()).limit(20).all()

    return render_template('admin.html',
                           topics=topics,
                           sources=sources,
                           logs=recent_logs)


@admin_bp.route('/topics')
def topics_list():
    """List all topics."""
    topics = Topic.query.all()
    return render_template('admin_topics.html', topics=topics)


@admin_bp.route('/topics/add', methods=['POST'])
def add_topic():
    """Add a new topic."""
    name = request.form.get('name', '').strip().lower().replace(' ', '_')
    display_name = request.form.get('display_name', '').strip()
    description = request.form.get('description', '').strip()
    refresh_hours = int(request.form.get('refresh_hours', 4))

    if not name or not display_name:
        flash('Name and display name are required.', 'error')
        return redirect(url_for('admin.topics_list'))

    existing = Topic.query.filter_by(name=name).first()
    if existing:
        flash(f'Topic "{name}" already exists.', 'error')
        return redirect(url_for('admin.topics_list'))

    topic = Topic(
        name=name,
        display_name=display_name,
        description=description,
        refresh_hours=refresh_hours,
        enabled=True
    )
    db.session.add(topic)
    db.session.commit()

    # Update config file
    save_topics_config()

    # Auto-discover sources for the new topic
    from app.services.source_discovery import discover_sources_for_new_topic
    sources_created = discover_sources_for_new_topic(topic.id, count=5)
    if sources_created > 0:
        save_sources_config()
        flash(f'Topic "{display_name}" added with {sources_created} auto-discovered sources.', 'success')
    else:
        flash(f'Topic "{display_name}" added. Add sources manually or use "Discover Sources".', 'success')

    return redirect(url_for('admin.topics_list'))


@admin_bp.route('/topics/<int:topic_id>/toggle', methods=['POST'])
def toggle_topic(topic_id):
    """Enable/disable a topic."""
    topic = Topic.query.get_or_404(topic_id)
    topic.enabled = not topic.enabled
    db.session.commit()
    save_topics_config()

    status = 'enabled' if topic.enabled else 'disabled'
    flash(f'Topic "{topic.display_name}" {status}.', 'success')
    return redirect(url_for('admin.topics_list'))


@admin_bp.route('/topics/<int:topic_id>/delete', methods=['POST'])
def delete_topic(topic_id):
    """Delete a topic and all related records."""
    topic = Topic.query.get_or_404(topic_id)
    name = topic.display_name

    # Delete related records first (foreign key constraints)
    ContentItem.query.filter_by(topic_id=topic_id).delete()
    Summary.query.filter_by(topic_id=topic_id).delete()
    SourceTopic.query.filter_by(topic_id=topic_id).delete()
    ScrapingLog.query.filter_by(topic_id=topic_id).delete()

    # Now delete the topic
    db.session.delete(topic)
    db.session.commit()
    save_topics_config()

    flash(f'Topic "{name}" deleted.', 'success')
    return redirect(url_for('admin.topics_list'))


@admin_bp.route('/sources')
def sources_list():
    """List all sources."""
    sources = Source.query.all()
    topics = Topic.query.all()
    return render_template('admin_sources.html', sources=sources, topics=topics)


@admin_bp.route('/sources/add', methods=['POST'])
def add_source():
    """Add a new source."""
    name = request.form.get('name', '').strip().lower().replace(' ', '_')
    display_name = request.form.get('display_name', '').strip()
    source_type = request.form.get('source_type', 'api')
    url = request.form.get('url', '').strip()
    topic_ids = request.form.getlist('topics')
    weight = float(request.form.get('weight', 1.0))

    if not name or not display_name or not url:
        flash('Name, display name, and URL are required.', 'error')
        return redirect(url_for('admin.sources_list'))

    existing = Source.query.filter_by(name=name).first()
    if existing:
        flash(f'Source "{name}" already exists.', 'error')
        return redirect(url_for('admin.sources_list'))

    source = Source(
        name=name,
        display_name=display_name,
        source_type=source_type,
        url=url,
        weight=weight,
        enabled=True
    )
    db.session.add(source)
    db.session.flush()  # Get the source ID

    # Associate with topics
    for topic_id in topic_ids:
        st = SourceTopic(source_id=source.id, topic_id=int(topic_id))
        db.session.add(st)

    db.session.commit()
    save_sources_config()

    flash(f'Source "{display_name}" added successfully.', 'success')
    return redirect(url_for('admin.sources_list'))


@admin_bp.route('/sources/<int:source_id>/toggle', methods=['POST'])
def toggle_source(source_id):
    """Enable/disable a source."""
    source = Source.query.get_or_404(source_id)
    source.enabled = not source.enabled
    db.session.commit()
    save_sources_config()

    status = 'enabled' if source.enabled else 'disabled'
    flash(f'Source "{source.display_name}" {status}.', 'success')
    return redirect(url_for('admin.sources_list'))


@admin_bp.route('/sources/<int:source_id>/delete', methods=['POST'])
def delete_source(source_id):
    """Delete a source."""
    source = Source.query.get_or_404(source_id)
    name = source.display_name
    db.session.delete(source)
    db.session.commit()
    save_sources_config()

    flash(f'Source "{name}" deleted.', 'success')
    return redirect(url_for('admin.sources_list'))


@admin_bp.route('/logs')
def logs():
    """View scraping logs."""
    page = request.args.get('page', 1, type=int)
    logs = ScrapingLog.query.order_by(ScrapingLog.created_at.desc()) \
        .paginate(page=page, per_page=50)
    return render_template('admin_logs.html', logs=logs)


@admin_bp.route('/refresh', methods=['POST'])
def manual_refresh():
    """Trigger a manual refresh of all topics."""
    from app.services.scheduler import run_all_scrapers
    run_all_scrapers()
    flash('Refresh triggered. Content will update shortly.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/refresh/<string:topic_name>', methods=['POST'])
def refresh_topic(topic_name):
    """Trigger a manual refresh of a specific topic."""
    from app.services.scheduler import run_topic_scraper
    topic = Topic.query.filter_by(name=topic_name).first_or_404()
    run_topic_scraper(topic.id)
    flash(f'Refresh triggered for "{topic.display_name}".', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/discover-sources', methods=['POST'])
def discover_sources():
    """Use AI to discover one additional source for each topic."""
    from app.services.source_discovery import discover_additional_sources_for_all_topics

    results = discover_additional_sources_for_all_topics()
    total_added = sum(results.values())

    if total_added > 0:
        save_sources_config()
        flash(f'Discovered {total_added} new source(s) across topics.', 'success')
    else:
        flash('No new sources discovered. Topics may already have good coverage.', 'info')

    return redirect(url_for('admin.sources_list'))
