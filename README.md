# Webhook Catcher & Request Inspector

A lightweight, zero-dependency local webhook catcher and HTTP request inspector built in Python 3. Perfect alternative to `webhook.site` for local API debugging, webhook verification, and third-party callback inspection.

## Features
- **Zero External Dependencies**: Pure Python 3 standard library (`http.server`, `sqlite3`, `json`).
- **Real-Time Streaming**: Live request inspection powered by Server-Sent Events (SSE).
- **SQLite Persistence**: Automatically logs headers, body payloads, query parameters, client IP, and timestamps.
- **Request Replay**: One-click request replay to any custom destination URL directly from the browser.
- **cURL Exporter**: Instantly copy any captured request as an exact `curl` command.
- **Filter & Search**: Quick search through captured methods, endpoints, headers, and payloads.
- **Dark Tech UI**: Clean, responsive developer-oriented interface.

## Quick Start (Fish Shell / Bash)

```fish
cd /home/kiiyuu/Projects/project-web/webhook-catcher
./run.fish
```

Or run directly with Python:
```bash
python3 app.py 4040
```

Open the dashboard in your browser:
`http://localhost:4040`

Send webhooks or requests to:
`http://localhost:4040/hook/<your-endpoint-name>`
