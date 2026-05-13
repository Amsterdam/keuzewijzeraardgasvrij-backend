from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import Eliminatie
from apps.calculations.models import GebruikersInvoer
from apps.systemen.models import Hoofdsysteem


def _calculation_input(**overrides: object) -> GebruikersInvoer:
    defaults: dict[str, object] = {
        "bouwjaar": 1990,
        "bruto_vloeroppervlak": Decimal("1234.5"),
        "aantal_woningen": 250,
        "mechanische_ventilatie_aanwezig": True,
        "vloerverwarming_aanwezig": False,
        "tapwater_op_gas": True,
        "koken_op_gas": False,
        "gasverbruik_vve_totaal": Decimal("1334.6"),
        "wens_tot_koelen": False,
    }
    defaults.update(overrides)
    return GebruikersInvoer.objects.create(**defaults)


class EliminatieCalculatorTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_returns_ruimte_binnen_en_buiten_from_fixtures(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Collectief Open Bodem Energie Systeem met Centrale Bodemwarmtepomp"
        )
        calc_input = _calculation_input(
            aantal_woningen=250,
            beschikbare_ruimte_in_woning_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_buiten_m2=Decimal("10000"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is True, result
        assert result["redenen"] == [], result

    def test_eliminatie_reason_mechanische_ventilatie_required(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Individuele Luchtwarmtepomp op Ventilatie"
        )
        calc_input = _calculation_input(
            aantal_woningen=50,
            mechanische_ventilatie_aanwezig=False,
            wens_tot_koelen=False,
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result

    def test_eliminatie_reason_kan_niet_koelen_when_cooling_desired(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Particulier Externe warmtelevering"
        )
        calc_input = _calculation_input(
            aantal_woningen=50,
            wens_tot_koelen=True,
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"Koeling is gewenst, maar {hoofdsysteem.naam} kan niet koelen."
        ], result

    def test_eliminatie_reason_aantal_woningen_out_of_range(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Individuele Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp"
        )
        calc_input = _calculation_input(aantal_woningen=50)

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
