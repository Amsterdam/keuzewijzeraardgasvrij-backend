from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import logging

from attr import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PandData:
    aantal_woningen: int | None
    bouwjaar: int | None
    identificatie: str | None
    postcode: str | None = None


class PdokClient:
    def __init__(
        self,
        *,
        bag_base_url: str = "https://api.pdok.nl/kadaster/bag/ogc/v2",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._bag_base_url = (bag_base_url or "").rstrip("/")
        self._timeout_seconds = float(timeout_seconds)

    def get_pand_info(self, *, bag_id: str) -> PandData:
        pand_url, postcode = self._get_pand_url_postcode(identificatie=bag_id)

        identificatie, aantal_woningen, bouwjaar = self._get_pand_woningen_en_bouwjaar(
            pand_url=pand_url
        )

        return PandData(
            aantal_woningen=aantal_woningen,
            bouwjaar=bouwjaar,
            identificatie=identificatie,
            postcode=postcode,
        )

    def _get_pand_url_postcode(
        self, *, identificatie: str
    ) -> tuple[str | None, str | None]:
        identificatie = (identificatie or "").strip()
        if not identificatie:
            return None, None

        crs84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
        params = {
            "f": "json",
            "limit": 10,
            "crs": crs84,
            "bbox-crs": crs84,
            "profile": "rel-as-uri",
            "identificatie": identificatie,
        }
        url = (
            f"{self._bag_base_url}/collections/verblijfsobject/items"
            f"?{urlencode(params)}"
        )

        woning_data = self._get_json(url=url).get("features")
        if not isinstance(woning_data, list) or not woning_data:
            return None, None

        feature = woning_data[0]
        properties = feature.get("properties")

        if not properties:
            return None, None
        pand_url = properties.get("pand")[0] if properties.get("pand") else None
        postcode = properties.get("postcode")

        return pand_url, None if postcode is None else str(postcode)

    def _get_pand_woningen_en_bouwjaar(
        self, *, pand_url: str
    ) -> tuple[str | None, int | None, int | None]:
        pand_url = (pand_url or "").strip()
        if not pand_url:
            return None, None, None

        url = pand_url if "?" in pand_url else f"{pand_url}?f=json"
        data = self._get_json(url=url)

        properties = data.get("properties")
        if not properties:
            return None, None, None

        identificatie = properties.get("identificatie")
        aantal_verblijfsobjecten = properties.get("aantal_verblijfsobjecten")
        bouw_jaar = properties.get("bouwjaar")
        return (
            None if identificatie is None else str(identificatie),
            None if aantal_verblijfsobjecten is None else int(aantal_verblijfsobjecten),
            None if bouw_jaar is None else int(bouw_jaar),
        )

    def _get_json(self, *, url: str) -> dict[str, Any]:
        req = Request(
            url,
            headers={
                "Accept": "application/json",
            },
            method="GET",
        )

        with urlopen(req, timeout=self._timeout_seconds) as resp:
            payload = resp.read().decode("utf-8")
            data: dict[str, Any] = json.loads(payload)
            return data
