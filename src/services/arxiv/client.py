import asyncio
import logging
import time
from functools import cached_property
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlencode, quote

import httpx

from src.config import ArxivSettings
from src.schemas.arxiv.paper import ArxivPaper

logger = logging.getLogger(__name__)


class ArxivClient:
    """Client for interacting with the arXiv API."""

    def __init__(self, settings: ArxivSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None

    @cached_property
    def pdf_cache_dir(self) -> Path:
        """PDF cache directory path."""
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @property
    def base_url(self) -> str:
        return self._settings.base_url

    @property
    def namespaces(self) -> dict:
        return self._settings.namespaces

    @property
    def rate_limit_delay(self) -> float:
        return self._settings.rate_limit_delay

    @property
    def timeout_seconds(self) -> int:
        return self._settings.timeout_seconds

    @property
    def max_results(self) -> int:
        return self._settings.max_results

    @property
    def search_category(self) -> str:
        return self._settings.search_category

    async def fetch_papers(
            self,
            max_results: Optional[int] = None,
            start: int = 0,
            sort_by: str = "submittedDate",
            sort_order: str = "descending",
            from_date: Optional[str] = None,
            to_date: Optional[str] = None,
    ) -> List[ArxivPaper]:
        """Fetch papers from arXiv API based on the given criteria."""

        if max_results is None:
            max_results = self.max_results

        search_query = f"cat:{self.search_category}"

        if from_date or to_date:
            date_from = f"{from_date}0000" if from_date else "*"
            date_to = f"{to_date}2359" if to_date else "*"

            search_query += f" AND submittedDate:[{date_from}+TO+{date_to}]"

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 2000),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        safe = ":+[]&"
        url = f"{self.base_url}?{urlencode(params, quote_via=quote, safe=safe)}"

        try:
            logger.info(f"Fetching {max_results} {self.search_category} papers from arXiv")

            if self._last_request_time is not None:
                time_since_last = time.time() - self._last_request_time
                if time_since_last < self.rate_limit_delay:
                    sleep_time = self.rate_limit_delay - time_since_last
                    await asyncio.sleep(sleep_time)

            self._last_request_time = time.time()

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            papers = self.parse_response(xml_data)
            logger.info(f"Fetched {len(papers)} papers from arXiv")

            return papers

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return []
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            return []

    async def fetch_papers_with_query(
            self,
            search_query: str,
            max_results: Optional[int] = None,
            start: int = 0,
            sort_by: str = "submittedDate",
            sort_order: str = "descending",
            from_date: Optional[str] = None,
            to_date: Optional[str] = None,
    ) -> List[ArxivPaper]:
        """Fetch papers from arXiv API based on the given criteria."""

        if max_results is None:
            max_results = self.max_results

        if from_date or to_date:
            date_from = f"{from_date}0000" if from_date else "*"
            date_to = f"{to_date}2359" if to_date else "*"

            search_query += f" AND submittedDate:[{date_from}+TO+{date_to}]"

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 2000),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        safe = ":+[]&"
        url = f"{self.base_url}?{urlencode(params, quote_via=quote, safe=safe)}"

        try:
            logger.info(f"Fetching {max_results} {self.search_category} papers from arXiv")

            if self._last_request_time is not None:
                time_since_last = time.time() - self._last_request_time
                if time_since_last < self.rate_limit_delay:
                    sleep_time = self.rate_limit_delay - time_since_last
                    await asyncio.sleep(sleep_time)

            self._last_request_time = time.time()

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            papers = self.parse_response(xml_data)
            logger.info(f"Fetched {len(papers)} papers from arXiv")

            return papers

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return []
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            return []

    async def fetch_paper_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
        params = {"id_list": clean_id, "max_results": 1}

        safe = ":+[]*"  # Don't encode :, +, [, ], *, characters needed for arXiv queries
        url = f"{self.base_url}?{urlencode(params, quote_via=quote, safe=safe)}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_data = response.text

            papers = self._parse_response(xml_data)

            if papers:
                return papers[0]
            else:
                logger.warning(f"Paper {arxiv_id} not found")
                return None

        except httpx.TimeoutException as e:
            logger.error(f"Request timed out: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return None
        except Exception as e:
            logger.error(f"Unknown error: {e}")
            return None

    def parse_response(self, xml_data: str) -> List[ArxivPaper]:
        """Parse the XML response from arXiv API and extract paper data."""
        return xml_data
