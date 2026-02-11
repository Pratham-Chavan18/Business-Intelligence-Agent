# Monday.com Business Intelligence Agent

An AI-powered conversational agent that queries Monday.com boards (Work Orders & Deals) to answer founder-level business questions in real-time.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                     Frontend                         │
│        HTML/CSS/JS Chat UI (Dark Mode)               │
│   marked.js (Markdown) │ Fetch API │ Responsive      │
└────────────────────────┬─────────────────────────────┘
                         │ REST API
┌────────────────────────┴─────────────────────────────┐
│                 FastAPI Backend                       │
│  POST /api/chat   │ POST /api/report │ GET /api/health│
└────────┬───────────────────┬─────────────────────────┘
         │                   │
┌────────┴────────┐  ┌───────┴──────────┐
│    BI Agent     │  │ Leadership Report│
│  (agent.py)     │  │  Generator       │
│  ┌────────────┐ │  └──────────────────┘
│  │ Gemini LLM │ │
│  │ (NLQ)      │ │
│  └────────────┘ │
└────────┬────────┘
         │
┌────────┴────────┐     ┌─────────────────┐
│ Data Processor  │◄────│ Monday.com API  │
│ (Cleaning,      │     │ (GraphQL)       │
│  Normalization) │     │ Work Orders +   │
└─────────────────┘     │ Deals Boards    │
                        └─────────────────┘
```

### Key Components

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server with chat, report, and health endpoints |
| `agent.py` | LLM-powered BI agent — builds data context, manages conversations |
| `monday_client.py` | Monday.com GraphQL client with retry, pagination, board discovery |
| `data_processor.py` | Data cleaning — dates, currencies, sectors, text normalization |
| `leadership_report.py` | Generates structured executive summary reports |
| `static/` | Premium dark-mode chat frontend |

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- Monday.com account with API access
- Google Gemini API key (free tier works)

### 2. Monday.com Board Setup
1. Go to [monday.com](https://monday.com) and create two boards:
   - **Work Orders** — import the work orders CSV
   - **Deals** — import the deals CSV
2. Set appropriate column types (dates, numbers, text, status)
3. Get your API key: Profile → Developer → My Access Tokens
4. Get board IDs from the board URL: `monday.com/boards/BOARD_ID`

### 3. Local Development

```bash
# Clone/extract the project
cd vue

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and board IDs

# Run the server
python main.py
# Or: uvicorn main:app --reload --port 8000

# Open http://localhost:8000
```

### 4. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MONDAY_API_KEY` | Yes | Monday.com API token |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `WORK_ORDERS_BOARD_ID` | No* | Board ID for work orders |
| `DEALS_BOARD_ID` | No* | Board ID for deals |
| `PORT` | No | Server port (default: 8000) |

*If not provided, the agent will try to auto-discover boards by name.

### 5. Deploy to Render

1. Push code to GitHub
2. Connect repo to [Render](https://render.com)
3. Add environment variables in Render dashboard
4. Deploy — `render.yaml` handles the rest

Or use Docker:
```bash
docker build -t monday-bi-agent .
docker run -p 8000:8000 --env-file .env monday-bi-agent
```

## Features

- **Conversational BI**: Ask natural language questions about your business data
- **Cross-board queries**: Correlates Work Orders and Deals data
- **Data resilience**: Handles messy data — missing values, inconsistent formats, varied naming
- **Leadership reports**: One-click executive summary with pipeline, revenue, and operational metrics
- **Live data**: Queries Monday.com dynamically (no hardcoded CSV)
- **Data caching**: 5-minute TTL cache to minimize API calls
