from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.kengetallen.models import BuurtcodeWarmteprogramma, Warmteprogramma

EXPECTED_HEADERS = {
    "BUURT_CODE",
    "TOELICHTING",
}


class Command(BaseCommand):
    help = "Importeer buurtcode-warmteprogramma koppelingen uit CSV."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "csv_path",
            type=str,
            help="Pad naar CSV met buurt_code en toelichting.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"Bestand niet gevonden: {csv_path}")
        if not csv_path.is_file():
            raise CommandError(f"Geen bestand: {csv_path}")

        content = csv_path.read_text(encoding="utf-8-sig", errors="strict")

        try:
            dialect = csv.Sniffer().sniff(content[:4096])
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(content.splitlines(), dialect=dialect)
        if not reader.fieldnames:
            raise CommandError("CSV heeft geen headerregel.")

        header_map: dict[str, str] = {}
        for original in reader.fieldnames:
            normalized = " ".join(original.strip().upper().split())
            header_map[original] = normalized

        missing = EXPECTED_HEADERS - set(header_map.values())
        if missing:
            expected = ", ".join(sorted(EXPECTED_HEADERS))
            got = ", ".join(reader.fieldnames)
            raise CommandError(
                "CSV mist verplichte kolommen: "
                f"{', '.join(sorted(missing))}. Verwacht: {expected}. Gevonden: {got}."
            )

        warmteprogrammas = {
            warmteprogramma.categorie: warmteprogramma
            for warmteprogramma in Warmteprogramma.objects.exclude(
                categorie__isnull=True
            )
        }

        records_by_buurtcode: dict[str, BuurtcodeWarmteprogramma] = {}
        total_rows = skipped_rows = 0

        for row_index, row in enumerate(reader, start=2):
            total_rows += 1

            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                normalized_row[header_map[key]] = (value or "").strip()

            buurtcode = normalized_row.get("BUURT_CODE", "").upper()
            toelichting = normalized_row.get("TOELICHTING", "")

            if not buurtcode:
                raise CommandError(f"Lege buurt_code op regel {row_index}.")

            warmteprogramma = warmteprogrammas.get(toelichting)
            if warmteprogramma is None:
                skipped_rows += 1
                continue

            records_by_buurtcode[buurtcode] = BuurtcodeWarmteprogramma(
                buurtcode=buurtcode,
                warmteprogramma=warmteprogramma,
            )

        with transaction.atomic():
            BuurtcodeWarmteprogramma.objects.all().delete()
            BuurtcodeWarmteprogramma.objects.bulk_create(records_by_buurtcode.values())

        self.stdout.write(
            self.style.SUCCESS(
                "Import afgerond. "
                f"Totaal rijen: {total_rows}, "
                f"geimporteerd: {len(records_by_buurtcode)}, "
                f"overgeslagen: {skipped_rows}."
            )
        )
