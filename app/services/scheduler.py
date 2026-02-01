"""
Background job scheduling for periodic scraping and summarization.
"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def init_scheduler(app):
    """Initialize the scheduler with the Flask app context."""
    global scheduler

    if scheduler is not None:
        return

    scheduler = BackgroundScheduler()

    # Add jobs with app context
    @scheduler.scheduled_job(IntervalTrigger(hours=4), id='scrape_all')
    def scheduled_scrape():
        with app.app_context():
            run_all_scrapers()

    @scheduler.scheduled_job(IntervalTrigger(hours=4, minutes=30), id='summarize_all')
    def scheduled_summarize():
        with app.app_context():
            run_all_summarizers()

    # Run initial sync and scrape on startup
    with app.app_context():
        try:
            # Sync configuration
            from app.services.config_loader import sync_config_to_database
            sync_config_to_database()
            logger.info('Configuration synced to database')

            # Check if we have any summaries - if not, run initial scrape
            from app.models import Summary
            if Summary.query.count() == 0:
                logger.info('No existing summaries - running initial scrape')
                run_all_scrapers()
                run_all_summarizers()
        except Exception as e:
            logger.error(f'Startup initialization failed: {e}')

    scheduler.start()
    logger.info('Scheduler started')


def run_all_scrapers():
    """Run scrapers for all enabled topics."""
    from app.models import Topic
    from app.services.scraper import scrape_topic

    logger.info('Starting scheduled scrape for all topics')

    topics = Topic.query.filter_by(enabled=True).all()
    total_items = 0

    for topic in topics:
        try:
            items = scrape_topic(topic.id)
            total_items += items
            logger.info(f'Scraped {items} items for topic {topic.name}')
        except Exception as e:
            logger.error(f'Failed to scrape topic {topic.name}: {e}')

    logger.info(f'Completed scraping: {total_items} total items')
    return total_items


def run_all_summarizers():
    """Run summarizers for all enabled topics."""
    from app.models import Topic
    from app.services.summarizer import summarize_topic

    logger.info('Starting summarization for all topics')

    topics = Topic.query.filter_by(enabled=True).all()
    summaries_created = 0

    for topic in topics:
        try:
            summary = summarize_topic(topic.id)
            if summary:
                summaries_created += 1
                logger.info(f'Created summary for topic {topic.name}')
        except Exception as e:
            logger.error(f'Failed to summarize topic {topic.name}: {e}')

    logger.info(f'Completed summarization: {summaries_created} summaries created')
    return summaries_created


def run_topic_scraper(topic_id: int):
    """Run scraper and summarizer for a specific topic."""
    from app.services.scraper import scrape_topic
    from app.services.summarizer import summarize_topic

    try:
        items = scrape_topic(topic_id)
        logger.info(f'Manual scrape: {items} items for topic {topic_id}')

        summary = summarize_topic(topic_id)
        if summary:
            logger.info(f'Manual summary created for topic {topic_id}')
    except Exception as e:
        logger.error(f'Manual refresh failed for topic {topic_id}: {e}')


def get_scheduler_status():
    """Get the current status of scheduled jobs."""
    global scheduler

    if not scheduler:
        return {'status': 'not_initialized', 'jobs': []}

    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            'id': job.id,
            'next_run': next_run.isoformat() if next_run else None,
        })

    return {
        'status': 'running' if scheduler.running else 'stopped',
        'jobs': jobs
    }


def cleanup_old_content():
    """Remove content older than retention period."""
    from app.models import ContentItem, ScrapingLog
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=Config.CONTENT_RETENTION_DAYS)

    # Delete old content items
    old_items = ContentItem.query.filter(ContentItem.scraped_at < cutoff).delete()

    # Delete old logs (keep 30 days)
    log_cutoff = datetime.utcnow() - timedelta(days=30)
    old_logs = ScrapingLog.query.filter(ScrapingLog.created_at < log_cutoff).delete()

    from app import db
    db.session.commit()

    logger.info(f'Cleanup: removed {old_items} content items and {old_logs} logs')
