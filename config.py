import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "phd_tracker:seen")
SEEN_JOB_TTL_SECONDS = int(os.getenv("SEEN_JOB_TTL_SECONDS", str(60 * 60 * 24 * 30)))

# Scraping Configuration
CHECK_INTERVAL_HOURS = 96
HEADLESS_MODE = True
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_DELAY_SECONDS = 0.6
EURAXESS_REQUEST_DELAY_SECONDS = 1.5
REQUEST_RETRY_ATTEMPTS = 3
REQUEST_RETRY_BACKOFF_SECONDS = 2.0
EMPTY_PAGE_RETRY_ATTEMPTS = 2

# Search Keywords (Case Insensitive)
# The scraper will look for ANY of these in the job title/description
KEYWORDS = [
    "Artificial Intelligence", "AI", "computer vision", "CV", "machine learning", "ML",
    "deep learning", "software", "biomedical", "medical", "healthcare", "multimodal",
    "blind", "audio", "image", "detect", "detection", "neuro", "agentic",
    "researcher", "research fellow", "research", "human computer interaction", "signal",
    "EngD", "automation", "deploy", "eye", "sleep", "diagnos", "memory"
]

# Only these narrower terms may match inside the description/context.
CONTEXT_KEYWORDS = [
    "Artificial Intelligence", "AI", "computer vision", "CV", "machine learning", "ML",
    "deep learning", "biomedical", "medical", "healthcare", "multimodal", "audio",
    "image", "detect", "detection", "neuro", "agentic", "human computer interaction",
    "signal", "EngD", "automation", "deploy", "eye", "sleep", "diagnos", "memory"
]

# Negative Keywords (Skip these)
EXCLUDED_KEYWORDS = [
    "post doc", "postdoc", "post-doc", "assistant professor", "tenure", "research assistant"
]

# Main Netherlands-focused sources
ACADEMICTRANSFER_URL = "https://www.academictransfer.com/en/jobs?q=&vacancy_type=all"
EURAXESS_URL = "https://euraxess.ec.europa.eu/jobs/search?f%5B0%5D=job_country%3A798&f%5B1%5D=offer_type%3Ajob_offer&page=0"
ACADEMICTRANSFER_SEARCH_TERM = "phd"

SOURCES = [
    {"name": "AcademicTransfer", "url": ACADEMICTRANSFER_URL},
    {"name": "EURAXESS", "url": EURAXESS_URL},
]

ACADEMICTRANSFER_MAX_PAGES = 20
EURAXESS_MAX_PAGES = 15
