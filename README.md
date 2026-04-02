# PhD Position Tracker

A Python automation app that monitors Netherlands-focused PhD vacancies and sends matching positions to interface every preferred days.

## What It Does
- Scrapes `AcademicTransfer` across paginated results.
- Scrapes `EURAXESS` filtered to job offers in the Netherlands.
- Applies your keyword list plus excluded-keyword filtering.
- Sends matching vacancies to Telegram.
- Deduplicates overlaps between the two sources before sending.
- Persists sent job IDs in Redis so repeated vacancies are skipped on later runs.

## Current Sources

- Academic Transfer – provides listings of PhD/Research positions (filtered in the code for relevant vacancies).  
- EURAXESS – European PhD/research jobs (filtered in the code for Netherlands-based positions).  

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Telegram
Set these environment variables before running:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
REDIS_URL=your_redis_connection_string
SEEN_JOB_TTL_SECONDS=2592000
```

### 3. Adjust filters
Edit `config.py` to change:
- `KEYWORDS`
- `EXCLUDED_KEYWORDS`
- `CHECK_INTERVAL_HOURS`

## Run

Run once:
```bash
python main.py --once
```

Run continuously with the scheduler:
```bash
python main.py
```

## Project Structure
- `main.py`: scheduler and notification flow
- `scraper.py`: source-specific scraping logic
- `notifier.py`: Telegram sending logic
- `storage.py`: Redis-based seen-job persistence
- `config.py`: filters, source URLs, and timing
