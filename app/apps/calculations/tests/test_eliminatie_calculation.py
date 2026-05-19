from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import Eliminatie
from apps.calculations.models import GebruikersInvoer
from apps.kengetallen.models import BuurtcodeWarmteprogramma, Warmteprogramma
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
        assert result["redenen"] == [
            f"Voor {hoofdsysteem.naam} is mechanische ventilatie nodig, maar die is er niet."
        ], result

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
        assert result["redenen"] == [
            f"{hoofdsysteem.naam} is het meest geschikt voor gebouwen tussen 1 tot 20 woningen (er zijn 50 woningen in de VvE)."
        ], result

    def test_eliminatie_reason_stadsverwarming_no_warmtenet_and_no_plans(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Particulier Externe warmtelevering"
        )
        now_year = datetime.datetime.now().year
        warmtenet_start = now_year + 25
        warmtenet_stop = warmtenet_start + 10

        wp = Warmteprogramma.objects.create(
            categorie="TEST",
            warmtenet_start=warmtenet_start,
            warmtenet_stop=warmtenet_stop,
        )
        BuurtcodeWarmteprogramma.objects.create(
            buurtcode="TESTBUURT1", warmteprogramma=wp
        )

        calc_input = _calculation_input(
            aantal_woningen=50,
            wens_tot_koelen=False,
            buurtcode="TESTBUURT1",
            jaar_vervangen=now_year + 5,
            beschikbare_ruimte_in_woning_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_buiten_m2=Decimal("999"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            "Er is geen warmtenet in uw buurt, en er zijn ook geen plannen om dat aan te leggen."
        ], result

    def test_eliminatie_reason_stadsverwarming_warmtenet_later_than_verduurzaming(
        self,
    ) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Particulier Externe warmtelevering"
        )
        now_year = datetime.datetime.now().year
        warmtenet_start = now_year + 10
        warmtenet_stop = warmtenet_start + 10

        wp = Warmteprogramma.objects.create(
            categorie="TEST2",
            warmtenet_start=warmtenet_start,
            warmtenet_stop=warmtenet_stop,
        )
        BuurtcodeWarmteprogramma.objects.create(
            buurtcode="TESTBUURT2", warmteprogramma=wp
        )

        jaar_vervangen = now_year + 5
        calc_input = _calculation_input(
            aantal_woningen=50,
            wens_tot_koelen=False,
            buurtcode="TESTBUURT2",
            jaar_vervangen=jaar_vervangen,
            beschikbare_ruimte_in_woning_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_buiten_m2=Decimal("999"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"Er wordt tussen {warmtenet_start} en {warmtenet_stop} een warmtenet verwacht in uw buurt. Dit is later dan de verduurzaming in {jaar_vervangen}."
        ], result
