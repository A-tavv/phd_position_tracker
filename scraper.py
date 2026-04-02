from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

import config


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BaseScraper(ABC):
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                )
            }
        )

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _build_keyword_pattern(self, keyword: str) -> re.Pattern[str]:
        normalized = keyword.strip().lower()
        parts = [part for part in re.split(r"[\s/-]+", normalized) if part]

        if not parts:
            return re.compile(r"$^")

        if len(parts) == 1 and parts[0].isalpha() and len(parts[0]) <= 3:
            return re.compile(rf"(?<![a-z]){re.escape(parts[0])}(?![a-z])", re.IGNORECASE)

        token_patterns = []
        for part in parts:
            escaped = re.escape(part)
            if part.isalpha():
                token_patterns.append(rf"{escaped}\w*")
            else:
                token_patterns.append(escaped)

        joiner = r"[\s/-]+"
        return re.compile(rf"\b{joiner.join(token_patterns)}\b", re.IGNORECASE)

    def _matches_any_keyword(self, text: str, keywords: List[str]) -> bool:
        return any(self._build_keyword_pattern(keyword).search(text) for keyword in keywords)

    def _is_relevant_job(self, title: str, context: str) -> bool:
        if not title:
            return False

        title_text = title.strip()
        context_text = context.strip() if context else title_text

        if self._matches_any_keyword(context_text, config.EXCLUDED_KEYWORDS):
            return False

        if not re.search(r"\bphd\b", context_text, re.IGNORECASE):
            return False

        combined = f"{title_text} {context_text}"
        return self._matches_any_keyword(combined, config.KEYWORDS)

    @abstractmethod
    def scrape(self) -> List[Dict]:
        pass


class AcademicTransferScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen_urls = set()
        seen_page_signatures = set()

        for page in range(config.ACADEMICTRANSFER_MAX_PAGES):
            page_url = self._page_url(config.ACADEMICTRANSFER_URL, page)
            logging.info("Scanning AcademicTransfer page %s: %s", page + 1, page_url)
            try:
                soup = self._get_soup(page_url)
            except requests.RequestException as exc:
                logging.error("AcademicTransfer request failed on page %s: %s", page + 1, exc)
                break

            cards = soup.select("article.text-aqua-500")

            if not cards:
                break

            first_link = cards[0].select_one('a[href^="/en/jobs/"], a[href*="/en/jobs/"]')
            signature = first_link.get("href", "").strip() if first_link else f"page-{page}"
            if signature in seen_page_signatures:
                break
            seen_page_signatures.add(signature)

            for card in cards:
                link = card.select_one('a[href^="/en/jobs/"], a[href*="/en/jobs/"]')
                title_node = card.select_one("h3")
                if not link or not title_node:
                    continue

                href = urljoin("https://www.academictransfer.com", link.get("href", "").strip())
                title = title_node.get_text(" ", strip=True)
                context = card.get_text(" ", strip=True)

                if href in seen_urls or not self._is_relevant_job(title, context):
                    continue

                seen_urls.add(href)
                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "employer": self._extract_employer(card),
                        "location": "Netherlands",
                        "id": href,
                        "source": "AcademicTransfer",
                    }
                )

            time.sleep(config.REQUEST_DELAY_SECONDS)

        return jobs

    def _page_url(self, base_url: str, page: int) -> str:
        parsed = urlparse(base_url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if page:
            query["page"] = [str(page)]
        else:
            query.pop("page", None)
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    def _extract_employer(self, card: BeautifulSoup) -> str:
        text = card.get_text("\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[1]
        return "AcademicTransfer"

class EuraxessScraper(BaseScraper):
    def scrape(self) -> List[Dict]:
        jobs: List[Dict] = []
        seen_urls = set()
        max_pages = config.EURAXESS_MAX_PAGES

        for page in range(max_pages):
            page_url = self._page_url(page)
            logging.info("Scanning EURAXESS page %s: %s", page + 1, page_url)
            try:
                soup = self._get_soup(page_url)
            except requests.RequestException as exc:
                logging.error("EURAXESS request failed on page %s: %s", page + 1, exc)
                break

            cards = soup.select("article.ecl-content-item")

            if not cards:
                break

            if page == 0:
                max_pages = min(max_pages, self._get_total_pages(soup))

            for card in cards:
                title_link = card.select_one("h3.ecl-content-block__title a")
                if not title_link:
                    continue

                href = urljoin("https://euraxess.ec.europa.eu", title_link.get("href", "").strip())
                title = title_link.get_text(" ", strip=True)
                context = card.get_text(" ", strip=True)

                if href in seen_urls or not self._is_relevant_job(title, context):
                    continue

                seen_urls.add(href)
                employer_node = card.select_one(".ecl-content-block__primary-meta-item a")
                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "employer": employer_node.get_text(" ", strip=True) if employer_node else "EURAXESS",
                        "location": "Netherlands",
                        "id": href,
                        "source": "EURAXESS",
                    }
                )

            if not self._has_next_page(soup):
                break

            time.sleep(config.REQUEST_DELAY_SECONDS)

        return jobs

    def _page_url(self, page: int) -> str:
        parsed = urlparse(config.EURAXESS_URL)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["page"] = [str(page)]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        return bool(soup.select_one('.ecl-pagination__item--next a[href]'))

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        page_numbers = []
        for node in soup.select(".ecl-pagination__item a, .ecl-pagination__item span"):
            text = node.get_text(" ", strip=True)
            if text.isdigit():
                page_numbers.append(int(text))
        return max(page_numbers) if page_numbers else config.EURAXESS_MAX_PAGES
