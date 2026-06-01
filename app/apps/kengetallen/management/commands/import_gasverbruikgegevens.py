from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.kengetallen.models import GasverbruikGegeven

EXPECTED_HEADERS = {
    "POSTCODE",
    "POSTCODE_EIND",
    "PRODUCTSOORT",
    "SJA GEMIDDELD",
}


class Command(BaseCommand):
    help = "Importeer gasverbruikgegevens uit CSV (alleen PRODUCTSOORT=GAS)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "csv_path",
            type=str,
            help="Pad naar CSV met POSTCODE, POSTCODE_EIND, PRODUCTSOORT, SJA GEMIDDELD.",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            help="Schrijf de import echt weg. Zonder deze vlag wordt alles teruggedraaid.",
            default=False,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        csv_path = Path(options["csv_path"])
        no_dry_run = options["no_dry_run"]
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

        total_rows = gas_rows = created = updated = 0

        for row_index, row in enumerate(reader, start=2):
            total_rows += 1

            normalized_row: dict[str, str] = {}
            for key, value in row.items():
                if key is None:
                    continue
                normalized_row[header_map[key]] = (value or "").strip()

            productsoort = normalized_row.get("PRODUCTSOORT", "").strip().upper()
            if productsoort != "GAS":
                continue

            gas_rows += 1

            postcode_start = normalized_row.get("POSTCODE", "").strip().upper()
            postcode_eind = normalized_row.get("POSTCODE_EIND", "").strip().upper()
            if not postcode_start or not postcode_eind:
                raise CommandError(f"Lege POSTCODE/POSTCODE_EIND op regel {row_index}.")

            gemiddeld_raw = normalized_row.get("SJA GEMIDDELD", "")
            raw = gemiddeld_raw.replace("\u00a0", " ").strip().replace(" ", "")
            if raw == "":
                raise CommandError(f"Lege 'SJA GEMIDDELD' op regel {row_index}.")
            if "," in raw:
                raw = raw.replace(".", "").replace(",", ".")

            try:
                gemiddeld_verbruik = Decimal(raw)
            except (InvalidOperation, ValueError) as exc:
                raise CommandError(
                    f"Ongeldige 'SJA GEMIDDELD' op regel {row_index}: {gemiddeld_raw!r}"
                ) from exc

            existing = GasverbruikGegeven.objects.filter(
                postcode_start=postcode_start,
                postcode_eind=postcode_eind,
            ).first()
            if existing is None:
                created += 1
            else:
                updated += 1

            if no_dry_run:
                GasverbruikGegeven.objects.update_or_create(
                    postcode_start=postcode_start,
                    postcode_eind=postcode_eind,
                    defaults={"gemiddeld_verbruik": gemiddeld_verbruik},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Dry run afgerond' if not no_dry_run else 'Import afgerond'}. "
                f"Totaal rijen: {total_rows}, "
                f"GAS rijen: {gas_rows}, "
                f"aangemaakt: {created}, "
                f"bijgewerkt: {updated}."
            )
        )
