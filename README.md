# Maggpi

**M**ini **AGG**regator for **PI** - A Python-based web application that scrapes, summarizes, and displays curated content from multiple internet sources. Designed to run on systems with limited resources.

## Features

- **Multi-source scraping**: Pulls content from APIs, RSS feeds, and HTML pages
- **AI-powered summaries**: Uses Google Gemini to create intelligent summaries
- **Configurable topics**: Add/remove topics and sources via web UI or YAML files
- **REST API**: Serve content to other devices on your local network (specifically designed to serve "news ticker" devices)
- **Lightweight**: Optimized for Raspberry Pi's limited resources
- **Resource-efficient**: WAL mode SQLite, memory-optimized HTML parsing, automatic cleanup

## Prerequisites

Before starting, ensure you have:

- **Raspberry Pi 3B+** (or newer) with **Raspberry Pi OS Lite (64-bit)** based on Debian 13.2 installed
- **Internet connection** on your Pi
- **SSH access** to your Pi (or direct keyboard/monitor access)
- **GitHub account** (for cloning and receiving updates)
- **Gemini API key** (free) from Google

## Installation

### Step 1: Connect to Your Raspberry Pi

Open a terminal on your computer and SSH into your Pi:

```bash
ssh pi@<your-pi-ip-address>
```

Replace `<your-pi-ip-address>` with your Pi's IP (e.g., `192.168.1.100`).

If you don't know your Pi's IP address, you can find it by running `hostname -I` on the Pi directly.

### Step 2: Install System Dependencies

Update your system packages and install required dependencies:

```bash
sudo apt update
sudo apt upgrade -y
```

Install Python development tools and libraries:

```bash
sudo apt install -y git python3-pip python3-venv python3-dev build-essential
```

**Note:** This project uses Python's built-in `html.parser` instead of `lxml` to minimize memory usage on the Raspberry Pi.

### Step 3: Clone the Repository

Navigate to your home directory and clone the project from GitHub:

```bash
cd ~
git clone https://github.com/thinkscotty/maggpi.git
```

Move into the project directory:

```bash
cd maggpi
```

### Step 4: Create a Virtual Environment

Create an isolated Python environment for the project:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

You should see `(venv)` at the beginning of your terminal prompt, indicating the virtual environment is active.

### Step 5: Install Python Dependencies

Install all required Python packages:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This may take a few minutes on a Raspberry Pi.

### Step 6: Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Open the file for editing:

```bash
nano .env
```

Add your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

To get a free Gemini API key:
1. Go to https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the key and paste it into your `.env` file

Save and exit nano by pressing `Ctrl+X`, then `Y`, then `Enter`.

### Step 7: Initialize the Database

The database will be created automatically when you first run the application. No manual setup required.

### Step 8: Run the Application

For production use on the Pi, use gunicorn (automatically installed with requirements.txt):

```bash
gunicorn -w 1 -b 0.0.0.0:5000 --timeout 120 "app:create_app()"
```

**Explanation of flags:**
- `-w 1`: Single worker process (Pi 3B+ has limited RAM)
- `-b 0.0.0.0:5000`: Bind to all network interfaces on port 5000
- `--timeout 120`: Allow 2 minutes for AI summarization requests

For development/testing only, you can use:

```bash
python run.py
```

You should see output indicating the server is running.

### Step 9: Access the Web Interface

Open a web browser on any device connected to your network and navigate to:

```
http://<your-pi-ip-address>:5000
```

You should see the Maggpi home page.

## Updating the Application

When updates are available on GitHub, follow these steps to update your Pi:

### Step 1: Connect to Your Pi

```bash
ssh pi@<your-pi-ip-address>
```

### Step 2: Navigate to the Project Directory

```bash
cd ~/maggpi
```

### Step 3: Stop the Running Application

If running as a service:

```bash
sudo systemctl stop maggpi
```

Or if running manually, press `Ctrl+C` in the terminal where it's running.

### Step 4: Pull the Latest Changes

```bash
git pull origin main
```

### Step 5: Activate the Virtual Environment

```bash
source venv/bin/activate
```

### Step 6: Update Dependencies (if changed)

```bash
pip install -r requirements.txt
```

### Step 7: Restart the Application

If running as a service:

```bash
sudo systemctl start maggpi
```

Or manually:

```bash
python run.py
```

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

Access content from other devices on your network:

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

To run the application automatically on boot:

### Step 1: Copy the Service File

```bash
sudo cp maggpi.service /etc/systemd/system/
```

### Step 2: Reload systemd

```bash
sudo systemctl daemon-reload
```

### Step 3: Enable the Service

```bash
sudo systemctl enable maggpi
```

### Step 4: Start the Service

```bash
sudo systemctl start maggpi
```

### Managing the Service

Check status:

```bash
sudo systemctl status maggpi
```

View logs:

```bash
journalctl -u maggpi -f
```

Stop the service:

```bash
sudo systemctl stop maggpi
```

Restart the service:

```bash
sudo systemctl restart maggpi
```

## Web Interface

- **Home** (`/`): View all topic summaries
- **Topic Detail** (`/topic/{name}`): Detailed view with all items
- **Admin** (`/admin`): Dashboard, manage topics/sources, view logs

## Troubleshooting

### Application won't start?

1. Ensure the virtual environment is activated:
   ```bash
   source ~/maggpi/venv/bin/activate
   ```

2. Check that all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify your `.env` file exists and contains a valid API key:
   ```bash
   cat .env
   ```

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

The Pi 3B+ has limited RAM (1GB). This project is optimized for low memory usage:
- Uses lightweight `html.parser` instead of `lxml`
- Single gunicorn worker
- SQLite WAL mode for better concurrency
- Automatic cleanup of old content (runs daily)

If you still see issues:
- Reduce `MAX_ITEMS_PER_SOURCE` in `app/config.py`
- Reduce `MAX_ITEMS_PER_TOPIC`
- Reduce `CONTENT_RETENTION_DAYS` (default: 7 days)
- Disable some topics/sources

### Permission errors?

If you see permission denied errors:

```bash
sudo chown -R $USER:$USER ~/maggpi
```

### Git pull conflicts?

If `git pull` fails due to local changes:

```bash
git stash
git pull origin main
git stash pop
```

## Project Structure

```
maggpi/
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
├── .env.example            # Example environment file
├── requirements.txt        # Python dependencies
├── maggpi.service   # systemd service file
└── run.py                  # Entry point
```

## License

MIT License - Feel free to modify and share!
