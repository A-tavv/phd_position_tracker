import logging
import sys
import time

import schedule

import config
from notifier import TelegramNotifier
from scraper import AcademicTransferScraper, EuraxessScraper
from storage import get_seen_jobs_store


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def job():
    logging.info("Starting scheduled job check...")

    notifier = TelegramNotifier(token=config.TELEGRAM_BOT_TOKEN, chat_id=config.TELEGRAM_CHAT_ID)
    scrapers = [AcademicTransferScraper(), EuraxessScraper()]
    seen_jobs_store = get_seen_jobs_store()

    all_jobs = []
    for scraper in scrapers:
        try:
            all_jobs.extend(scraper.scrape())
        except Exception as exc:
            logging.error("Scraper failed: %s", exc)

    deduped_jobs = []
    seen_keys = set()
    for job_item in all_jobs:
        dedupe_key = (
            job_item["title"].strip().lower(),
            job_item["employer"].strip().lower(),
            job_item["location"].strip().lower(),
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_jobs.append(job_item)

    logging.info("Found %s unique vacancies in total matching criteria.", len(deduped_jobs))

    new_jobs = [job_item for job_item in deduped_jobs if seen_jobs_store.mark_if_new(job_item["id"])]
    logging.info("Found %s unseen vacancies to send.", len(new_jobs))

    sent_jobs = 0
    for job_item in new_jobs:
        logging.info("Sending job: %s", job_item["title"])
        notifier.send_message(notifier.format_job_message(job_item))
        sent_jobs += 1
        time.sleep(0.5)

    if sent_jobs == 0:
        logging.info("No new matching vacancies found.")
        notifier.send_message(
            f"Scan finished.\nChecked {len(config.SOURCES)} sources.\nFound {len(deduped_jobs)} matches total.\n0 new jobs sent."
        )
    else:
        logging.info("Sent notifications for %s vacancies.", sent_jobs)
        notifier.send_message(
            f"Scan finished.\nFound {len(deduped_jobs)} matches total.\nSent {sent_jobs} new jobs."
        )


def main():
    logging.info("PhD Position Tracker started.")
    logging.info("Tracking %s sources", len(config.SOURCES))
    logging.info("Keywords: %s", config.KEYWORDS)

    job()

    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(job)
    logging.info("Scheduler set to run every %s hours.", config.CHECK_INTERVAL_HOURS)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    if "--once" in sys.argv:
        logging.info("Running in Single-Execution mode (CI/Cron).")
        job()
    else:
        main()
