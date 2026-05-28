from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class DsoClientError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DsoPandSummary:
    pand_id: str
    bouwjaar: int | None
    aantal_woningen: int
    oppervlakte_totaal: int


class DsoClient:
    def __init__(
        self,
        *,
        base_url: str = "https://api.data.amsterdam.nl/v1/bag/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = float(timeout_seconds)

    def get_bruto_vloeroppervlak(self, pand_id: str) -> int:
        all_vbos_url = (
            f"{self._base_url}/verblijfsobjecten?"
            f"{urlencode({'ligtInPanden.identificatie': pand_id, '_pageSize': 1000, '_fields': 'oppervlakte'})}"
        )
        verblijfsobjecten = (
            self._get_paginated_response(all_vbos_url)
            .get("_embedded", {})
            .get("verblijfsobjecten", [])
        )
        if not isinstance(verblijfsobjecten, list):
            return 0

        oppervlakte_totaal = 0
        for item in verblijfsobjecten:
            if not isinstance(item, dict):
                continue
            try:
                oppervlakte_totaal += int(item.get("oppervlakte") or 0)
            except Exception:
                pass

        return oppervlakte_totaal

    def _get_paginated_response(self, url: str) -> dict[str, Any]:
        print(f"Fetching URL: {url}")
        req = Request(
            url,
            headers={
                "User-Agent": "keuzewijzeraardgasvrij-backend/1.0",
            },
            method="GET",
        )
        with urlopen(req, timeout=self._timeout_seconds) as resp:
            payload = resp.read().decode("utf-8")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise DsoClientError("Unexpected JSON shape")

        while (
            isinstance(data.get("_links"), dict)
            and isinstance(data["_links"].get("next"), dict)
            and data["_links"]["next"].get("href")
        ):
            print(f"Fetching next page: {data['_links']['next']['href']}")
            next_page = str(data["_links"]["next"]["href"])
            req = Request(
                next_page,
                method="GET",
            )
            with urlopen(req, timeout=self._timeout_seconds) as resp:
                payload = resp.read().decode("utf-8")
            paged = json.loads(payload)
            if not isinstance(paged, dict):
                raise DsoClientError("Unexpected JSON shape")

            embedded = data.get("_embedded")
            paged_embedded = paged.get("_embedded")
            if isinstance(embedded, dict) and isinstance(paged_embedded, dict):
                for key, value in embedded.items():
                    if isinstance(value, list) and isinstance(
                        paged_embedded.get(key), list
                    ):
                        value.extend(paged_embedded[key])

            data["_links"] = paged.get("_links")

        return data
