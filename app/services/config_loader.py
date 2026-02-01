"""
Configuration loader for topics and sources from YAML files.
"""

import yaml
from pathlib import Path
from app.config import Config


def load_yaml_file(filepath):
    """Load a YAML file and return its contents."""
    path = Path(filepath)
    if not path.exists():
        return None

    with open(path, 'r') as f:
        return yaml.safe_load(f)


def save_yaml_file(filepath, data):
    """Save data to a YAML file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_topics_config():
    """Load topics configuration from YAML file."""
    data = load_yaml_file(Config.TOPICS_CONFIG)
    return data.get('topics', []) if data else []


def load_sources_config():
    """Load sources configuration from YAML file."""
    data = load_yaml_file(Config.SOURCES_CONFIG)
    return data.get('sources', []) if data else []


def save_topics_config():
    """Save current topics from database to YAML file."""
    from app.models import Topic

    topics = Topic.query.all()
    data = {
        'topics': [
            {
                'name': t.name,
                'display_name': t.display_name,
                'description': t.description,
                'enabled': t.enabled,
                'refresh_hours': t.refresh_hours
            }
            for t in topics
        ]
    }
    save_yaml_file(Config.TOPICS_CONFIG, data)


def save_sources_config():
    """Save current sources from database to YAML file."""
    from app.models import Source

    sources = Source.query.all()
    data = {
        'sources': [
            {
                'name': s.name,
                'display_name': s.display_name,
                'type': s.source_type,
                'url': s.url,
                'enabled': s.enabled,
                'weight': s.weight,
                'topics': [st.topic.name for st in s.topics if st.topic],
                'config': s.config
            }
            for s in sources
        ]
    }
    save_yaml_file(Config.SOURCES_CONFIG, data)


def sync_config_to_database():
    """
    Sync YAML configuration files to the database.
    Creates missing topics/sources, updates existing ones.
    """
    from app import db
    from app.models import Topic, Source, SourceTopic

    # Sync topics
    topics_config = load_topics_config()
    for topic_data in topics_config:
        topic = Topic.query.filter_by(name=topic_data['name']).first()
        if not topic:
            topic = Topic(name=topic_data['name'])
            db.session.add(topic)

        topic.display_name = topic_data.get('display_name', topic_data['name'])
        topic.description = topic_data.get('description', '')
        topic.enabled = topic_data.get('enabled', True)
        topic.refresh_hours = topic_data.get('refresh_hours', 4)

    db.session.commit()

    # Sync sources
    sources_config = load_sources_config()
    for source_data in sources_config:
        source = Source.query.filter_by(name=source_data['name']).first()
        if not source:
            source = Source(name=source_data['name'])
            db.session.add(source)
            db.session.flush()

        source.display_name = source_data.get('display_name', source_data['name'])
        source.source_type = source_data.get('type', 'api')
        source.url = source_data.get('url', '')
        source.enabled = source_data.get('enabled', True)
        source.weight = source_data.get('weight', 1.0)
        source.config = source_data.get('config', {})

        # Update topic associations
        SourceTopic.query.filter_by(source_id=source.id).delete()
        for topic_name in source_data.get('topics', []):
            topic = Topic.query.filter_by(name=topic_name).first()
            if topic:
                st = SourceTopic(source_id=source.id, topic_id=topic.id)
                db.session.add(st)

    db.session.commit()
