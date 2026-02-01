# Pi Content Aggregator

A Python-based web application that scrapes, summarizes, and displays curated content from multiple internet sources. Designed to run on Raspberry Pi 3B.

## Features

- **Multi-source scraping**: Pulls content from APIs, RSS feeds, and HTML pages
- **AI-powered summaries**: Uses Google Gemini to create intelligent summaries
- **Configurable topics**: Add/remove topics and sources via web UI or YAML files
- **REST API**: Serve content to other devices on your local network
- **Lightweight**: Optimized for Raspberry Pi's limited resources

## Quick Start

### 1. Clone/Copy the Project

```bash
cd ~/Code\ Projects
# Copy the pi-content-aggregator folder to your Pi
```

### 2. Set Up Python Environment

```bash
cd pi-content-aggregator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API Keys

```bash
cp .env.example .env
nano .env  # Edit with your API keys
```

Required API key:
- **Gemini API**: Get free key at https://makersuite.google.com/app/apikey

Optional API keys:
- **OpenWeatherMap**: https://openweathermap.org/api (for weather)
- **NewsAPI**: https://newsapi.org (for additional news sources)

### 4. Run the Application

```bash
python run.py
```

Access the web interface at: `http://your-pi-ip:5000`

## Configuration

### Topics (config/topics.yaml)

Edit this file to add or modify topics:

```yaml
topics:
  - name: my_topic          # Unique identifier (lowercase, underscores)
    display_name: "My Topic"  # Shown in UI
    description: "What this topic is about"
    enabled: true
    refresh_hours: 4        # How often to refresh
```

### Sources (config/sources.yaml)

Add sources that provide content for your topics:

```yaml
sources:
  - name: source_name
    display_name: "Source Name"
    type: api               # api, rss, or html
    url: "https://..."
    topics: [my_topic]      # Which topics this feeds
    weight: 0.9             # Priority (0.1-1.0)
    enabled: true
```

## API Endpoints

Access content from other devices:

| Endpoint | Description |
|----------|-------------|
| `GET /api/topics` | List all topics |
| `GET /api/content` | All current summaries |
| `GET /api/content/{topic}` | Summary for specific topic |
| `GET /api/raw/{topic}` | Raw scraped data |
| `GET /api/sources` | List configured sources |
| `GET /api/health` | Health check |
| `GET /api/status` | Application status |

## Running as a Service

To run automatically on boot:

```bash
sudo cp pi-aggregator.service /etc/systemd/system/
sudo systemctl enable pi-aggregator
sudo systemctl start pi-aggregator
```

Check status:
```bash
sudo systemctl status pi-aggregator
```

View logs:
```bash
journalctl -u pi-aggregator -f
```

## Web Interface

- **Home** (`/`): View all topic summaries
- **Topic Detail** (`/topic/{name}`): Detailed view with all items
- **Admin** (`/admin`): Dashboard, manage topics/sources, view logs

## Troubleshooting

### No content showing?

1. Check that API keys are configured in `.env`
2. Go to Admin > click "Refresh All Topics"
3. Check Admin > Logs for errors

### Scraping errors?

Some sources may block automated requests. Check the logs and consider:
- Adjusting rate limits in `app/config.py`
- Disabling problematic sources
- Using alternative sources

### High memory usage?

The Pi 3B has limited RAM. If you see issues:
- Reduce `MAX_ITEMS_PER_SOURCE` in `app/config.py`
- Reduce `MAX_ITEMS_PER_TOPIC`
- Disable some topics/sources

## Project Structure

```
pi-content-aggregator/
├── app/
│   ├── __init__.py         # Flask app factory
│   ├── config.py           # Configuration
│   ├── models.py           # Database models
│   ├── routes/             # Web routes
│   ├── services/           # Core services
│   ├── templates/          # HTML templates
│   └── static/             # CSS files
├── config/
│   ├── topics.yaml         # Topic configuration
│   └── sources.yaml        # Source configuration
├── data/
│   └── aggregator.db       # SQLite database
├── .env                    # API keys (create from .env.example)
├── requirements.txt        # Python dependencies
└── run.py                  # Entry point
```

## License

MIT License - Feel free to modify and share!
