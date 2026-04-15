from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List
from urllib.parse import quote_plus
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

import config


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class BaseScraper(ABC):
    source_name = "Unknown"

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
        self._keyword_patterns: dict[str, re.Pattern[str]] = {}
        self._detail_cache: dict[str, dict[str, str]] = {}
        self._reset_report()

    def _reset_report(self) -> None:
        self.report = {
            "source": self.source_name,
            "requests": 0,
            "pages_scanned": 0,
            "raw_items": 0,
            "matched_items": 0,
            "off_country_items": 0,
            "detail_validations": 0,
            "retries": 0,
            "empty_pages": 0,
            "status_codes": {},
            "errors": [],
            "stop_reason": "",
        }

    def _record_status(self, status_code: int) -> None:
        status_key = str(status_code)
        self.report["status_codes"][status_key] = self.report["status_codes"].get(status_key, 0) + 1

    def _record_error(self, message: str) -> None:
        if len(self.report["errors"]) < 5:
            self.report["errors"].append(message)

    def _sleep_with_backoff(self, attempt: int, retry_after: str | None = None) -> None:
        if retry_after and retry_after.isdigit():
            wait_seconds = max(config.REQUEST_RETRY_BACKOFF_SECONDS, float(retry_after))
        else:
            wait_seconds = config.REQUEST_RETRY_BACKOFF_SECONDS * (2 ** attempt)
        time.sleep(wait_seconds)

    def _get_soup(self, url: str) -> BeautifulSoup:
        last_exc: requests.RequestException | None = None
        for attempt in range(config.REQUEST_RETRY_ATTEMPTS):
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
                self.report["requests"] += 1
                self._record_status(response.status_code)
                response.raise_for_status()
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as exc:
                last_exc = exc
                self._record_error(f"{type(exc).__name__}: {exc}")
                if attempt == config.REQUEST_RETRY_ATTEMPTS - 1:
                    break
                self.report["retries"] += 1
                retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
                self._sleep_with_backoff(attempt, retry_after)
        raise last_exc if last_exc else requests.RequestException(f"Request failed for {url}")

    def _get_json(self, url: str, headers: dict[str, str] | None = None) -> dict:
        last_exc: requests.RequestException | None = None
        for attempt in range(config.REQUEST_RETRY_ATTEMPTS):
            try:
                response = self.session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS, headers=headers)
                self.report["requests"] += 1
                self._record_status(response.status_code)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exc = exc
                self._record_error(f"{type(exc).__name__}: {exc}")
                if attempt == config.REQUEST_RETRY_ATTEMPTS - 1:
                    break
                self.report["retries"] += 1
                retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
                self._sleep_with_backoff(attempt, retry_after)
        raise last_exc if last_exc else requests.RequestException(f"Request failed for {url}")

    def _build_keyword_pattern(self, keyword: str) -> re.Pattern[str]:
        cached = self._keyword_patterns.get(keyword)
        if cached:
            return cached

        normalized = keyword.strip().lower()
        parts = [part for part in re.split(r"[\s/-]+", normalized) if part]

        if not parts:
            pattern = re.compile(r"$^")
            self._keyword_patterns[keyword] = pattern
            return pattern

        if len(parts) == 1 and parts[0].isalpha() and len(parts[0]) <= 3:
            pattern = re.compile(rf"(?<![a-z]){re.escape(parts[0])}(?![a-z])", re.IGNORECASE)
            self._keyword_patterns[keyword] = pattern
            return pattern

        token_patterns = []
        for part in parts:
            escaped = re.escape(part)
            if part.isalpha():
                token_patterns.append(rf"{escaped}\w*")
            else:
                token_patterns.append(escaped)

        joiner = r"[\s/-]+"
        pattern = re.compile(rf"\b{joiner.join(token_patterns)}\b", re.IGNORECASE)
        self._keyword_patterns[keyword] = pattern
        return pattern

    def _matches_any_keyword(self, text: str, keywords: List[str]) -> bool:
        return any(self._build_keyword_pattern(keyword).search(text) for keyword in keywords)

    def _is_relevant_job(self, title: str, context: str) -> bool:
        if not title:
            return False

        title_text = title.strip()
        context_text = context.strip() if context else title_text
        combined = f"{title_text} {context_text}"

        if self._matches_any_keyword(combined, config.EXCLUDED_KEYWORDS):
            return False

        # Match only on the vacancy title to avoid metadata fields such as
        # research area or employer descriptions broadening the results.
        if not re.search(r"\b(phd|doctoral|doctorate)\b", title_text, re.IGNORECASE):
            return False

        return self._matches_any_keyword(title_text, config.KEYWORDS)

    def _format_status_codes(self) -> str:
        if not self.report["status_codes"]:
            return "none"
        return ",".join(
            f"{status}:{count}" for status, count in sorted(self.report["status_codes"].items(), key=lambda item: int(item[0]))
        )

    def get_report(self) -> dict:
        return {
            **self.report,
            "status_codes": self._format_status_codes(),
            "errors": list(self.report["errors"]),
        }

    @abstractmethod
    def scrape(self) -> List[Dict]:
        pass


class AcademicTransferScraper(BaseScraper):
    source_name = "AcademicTransfer"

    def scrape(self) -> List[Dict]:
        self._reset_report()
        jobs: List[Dict] = []
        seen_urls = set()
        token = self._get_public_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json; version=2",
            "Accept-Language": "en",
        }

        for page in range(config.ACADEMICTRANSFER_MAX_PAGES):
            offset = page * 10
            api_url = self._api_url(offset)
            logging.info("Scanning AcademicTransfer page %s: %s", page + 1, api_url)
            self.report["pages_scanned"] += 1

            payload = self._get_payload_with_empty_retry(api_url, headers, page + 1)
            results = payload.get("results", [])
            self.report["raw_items"] += len(results)

            if not results:
                self.report["stop_reason"] = "empty_results"
                break

            for item in results:
                href = item.get("absolute_url", "").strip()
                title = item.get("title", "").strip()
                description = self._html_to_text(item.get("description", ""))
                excerpt = self._html_to_text(item.get("excerpt", ""))
                organisation = item.get("organisation_name", "").strip() or "AcademicTransfer"
                location = item.get("city", "").strip() or "Netherlands"
                context = " ".join(
                    part for part in [title, excerpt, description, organisation, location] if part
                )

                if not href or href in seen_urls or not self._is_relevant_job(title, context):
                    continue

                seen_urls.add(href)
                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "employer": organisation,
                        "location": location,
                        "id": href,
                        "source": self.source_name,
                    }
                )

            next_url = payload.get("next")
            if not next_url:
                self.report["stop_reason"] = "no_next_page"
                break

            time.sleep(config.REQUEST_DELAY_SECONDS)

        self.report["matched_items"] = len(jobs)
        if not self.report["stop_reason"]:
            self.report["stop_reason"] = "max_pages_reached"

        return jobs

    def _get_public_access_token(self) -> str:
        soup = self._get_soup(config.ACADEMICTRANSFER_URL)
        payload_node = soup.select_one("#__NUXT_DATA__")
        if not payload_node or not payload_node.string:
            raise ValueError("AcademicTransfer public token payload was not found.")

        payload = json.loads(payload_node.string)
        match = re.search(r'\$satDataApiPublicAccessToken":(\d+)', payload_node.string)
        if not match:
            raise ValueError("AcademicTransfer public token reference was not found.")

        token_index = int(match.group(1))
        token = payload[token_index]
        if not isinstance(token, str) or not token:
            raise ValueError("AcademicTransfer public token value is invalid.")
        return token

    def _api_url(self, offset: int) -> str:
        search = quote_plus(config.ACADEMICTRANSFER_SEARCH_TERM)
        return (
            "https://api.academictransfer.com/vacancies/"
            f"?boost_spotlights=true&is_active=true&limit=10&offset={offset}"
            f"&search={search}&smcv=false&smrp=false"
        )

    def _get_payload_with_empty_retry(self, api_url: str, headers: dict[str, str], page_number: int) -> dict:
        for attempt in range(config.EMPTY_PAGE_RETRY_ATTEMPTS + 1):
            payload = self._get_json(api_url, headers=headers)
            if payload.get("results"):
                return payload
            self.report["empty_pages"] += 1
            if attempt == config.EMPTY_PAGE_RETRY_ATTEMPTS:
                logging.warning("AcademicTransfer page %s returned empty results after retries.", page_number)
                return payload
            self.report["retries"] += 1
            self._sleep_with_backoff(attempt)
        return {}

    def _html_to_text(self, value: str) -> str:
        if not value:
            return ""
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)

class EuraxessScraper(BaseScraper):
    source_name = "EURAXESS"

    def scrape(self) -> List[Dict]:
        self._reset_report()
        jobs: List[Dict] = []
        seen_urls = set()
        max_pages = config.EURAXESS_MAX_PAGES

        for page in range(max_pages):
            page_url = self._page_url(page)
            logging.info("Scanning EURAXESS page %s: %s", page + 1, page_url)
            self.report["pages_scanned"] += 1
            try:
                soup = self._get_soup_with_empty_retry(page_url, page + 1)
            except requests.RequestException as exc:
                logging.error("EURAXESS request failed on page %s: %s", page + 1, exc)
                self.report["stop_reason"] = f"request_failed_page_{page + 1}"
                break

            cards = soup.select("article.ecl-content-item")
            self.report["raw_items"] += len(cards)

            if not cards:
                self.report["stop_reason"] = "empty_results"
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

                card_location = self._extract_work_location(card)
                detail_metadata = self._get_detail_metadata(href)
                self.report["detail_validations"] += 1

                country = detail_metadata.get("country") or self._extract_country_from_location(card_location)
                if not self._is_target_country(country):
                    self.report["off_country_items"] += 1
                    continue

                location = card_location
                if detail_metadata.get("location"):
                    location = detail_metadata["location"]

                seen_urls.add(href)
                employer_node = card.select_one(".ecl-content-block__primary-meta-item a")
                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "employer": employer_node.get_text(" ", strip=True) if employer_node else "EURAXESS",
                        "location": location,
                        "id": href,
                        "source": "EURAXESS",
                    }
                )

            if not self._has_next_page(soup):
                self.report["stop_reason"] = "no_next_page"
                break

            time.sleep(config.EURAXESS_REQUEST_DELAY_SECONDS)

        self.report["matched_items"] = len(jobs)
        if not self.report["stop_reason"]:
            self.report["stop_reason"] = "max_pages_reached"
        return jobs

    def _get_soup_with_empty_retry(self, url: str, page_number: int) -> BeautifulSoup:
        last_soup: BeautifulSoup | None = None
        for attempt in range(config.EMPTY_PAGE_RETRY_ATTEMPTS + 1):
            soup = self._get_soup(url)
            last_soup = soup
            if soup.select("article.ecl-content-item"):
                return soup
            self.report["empty_pages"] += 1
            if attempt == config.EMPTY_PAGE_RETRY_ATTEMPTS:
                logging.warning("EURAXESS page %s returned no cards after retries.", page_number)
                return soup
            self.report["retries"] += 1
            self._sleep_with_backoff(attempt)
        return last_soup if last_soup else BeautifulSoup("", "html.parser")

    def _page_url(self, page: int) -> str:
        parsed = urlparse(config.EURAXESS_URL)
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["page"] = [str(page)]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    def _extract_work_location(self, card: BeautifulSoup) -> str:
        location_block = card.select_one(".id-Work-Locations .ecl-text-standard")
        if not location_block:
            return config.EURAXESS_COUNTRY_NAME

        location_text = location_block.get_text(" ", strip=True)
        parts = [part.strip() for part in location_text.split(",") if part.strip()]
        if len(parts) >= 4 and parts[0].lower().startswith("number of offers"):
            country = parts[1]
            city = parts[3]
            return f"{country}, {city}"
        if len(parts) >= 2 and parts[0].lower().startswith("number of offers"):
            return parts[1]
        return location_text

    def _extract_country_from_location(self, location: str) -> str:
        parts = [part.strip() for part in location.split(",") if part.strip()]
        return parts[0] if parts else location

    def _get_detail_metadata(self, href: str) -> dict[str, str]:
        cached = self._detail_cache.get(href)
        if cached is not None:
            return cached

        metadata = {"country": "", "location": ""}
        try:
            soup = self._get_soup(href)
        except requests.RequestException as exc:
            self._record_error(f"Detail validation failed for {href}: {exc}")
            self._detail_cache[href] = metadata
            return metadata

        for details in soup.select("dl.ecl-description-list"):
            terms = details.select("dt.ecl-description-list__term")
            definitions = details.select("dd.ecl-description-list__definition")
            for term, definition in zip(terms, definitions):
                label = term.get_text(" ", strip=True).lower()
                value = definition.get_text(" ", strip=True)
                if label == "country":
                    metadata["country"] = value
                elif label.startswith("work location"):
                    metadata["location"] = value

        self._detail_cache[href] = metadata
        return metadata

    def _is_target_country(self, country_or_location: str) -> bool:
        return bool(country_or_location) and country_or_location.lower().startswith(config.EURAXESS_COUNTRY_NAME.lower())

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        return bool(soup.select_one('.ecl-pagination__item--next a[href]'))

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        page_numbers = []
        for node in soup.select(".ecl-pagination__item a, .ecl-pagination__item span"):
            text = node.get_text(" ", strip=True)
            if text.isdigit():
                page_numbers.append(int(text))
        return max(page_numbers) if page_numbers else config.EURAXESS_MAX_PAGES
