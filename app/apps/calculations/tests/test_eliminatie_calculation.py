from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import Eliminatie
from apps.calculations.models import GebruikersInvoer
from apps.kengetallen.models import (
    BuurtcodeWarmteprogramma,
    EliminatieKengetal,
    Warmteprogramma,
)
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
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_dak_m2=Decimal("0"),
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
            f"Voor {hoofdsysteem.naam} is mechanische ventilatie nodig. Uw gebouw heeft dat nu niet."
            " Gaat u het gebouw verbouwen en komt er mechanische ventilatie? Vul de keuzewijzer dan opnieuw in met deze informatie."
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
            f"{hoofdsysteem.naam} is het meest geschikt voor gebouwen tussen 1 en 20 woningen (er zijn 50 woningen in de VvE)."
        ], result

    def test_eliminatie_reason_te_weinig_ruimte_in_woning(self) -> None:
        hoofdsysteem = (
            EliminatieKengetal.objects.filter(woningen_min=20, woningen_max=150)
            .first()
            .hoofdsysteem
        )
        calc_input = _calculation_input(
            aantal_woningen=50,
            beschikbare_ruimte_in_woning_m2=Decimal("0.5"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("10000"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"Er is te weinig ruimte in de woning voor {hoofdsysteem.naam} (ongeveer nodig: 1.0 m²)."
            " Kijk of u ruimte kunt vrijmaken. Vul de keuzewijzer daarna opnieuw in met de nieuwe hoeveelheid ruimte."
        ], result

    def test_eliminatie_reason_te_weinig_gezamenlijke_buitenruimte(self) -> None:
        hoofdsysteem = Hoofdsysteem.objects.get(
            naam="Collectief Open Bodem Energie Systeem met Centrale Bodemwarmtepomp"
        )
        calc_input = _calculation_input(
            aantal_woningen=250,
            beschikbare_ruimte_in_woning_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("0"),
            beschikbare_collectieve_ruimte_dak_m2=Decimal("0"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"Er is te weinig gezamenlijke buitenruimte voor {hoofdsysteem.naam} (ongeveer nodig: 60 m²)."
            " Kijk of u buitenruimte kunt vrijmaken. Vul de keuzewijzer daarna in met de nieuwe hoeveelheid ruimte."
        ], result

    def test_eliminatie_reason_te_weinig_woningen_suggests_samenwerken(self) -> None:
        hoofdsysteem = (
            EliminatieKengetal.objects.filter(woningen_min=20, woningen_max=150)
            .first()
            .hoofdsysteem
        )
        calc_input = _calculation_input(
            aantal_woningen=10,
            beschikbare_ruimte_in_woning_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_binnen_m2=Decimal("10000"),
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("10000"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"{hoofdsysteem.naam} is het meest geschikt voor gebouwen tussen 20 en 150 woningen (er zijn 10 woningen in de VvE)."
            " Dit systeem is misschien mogelijk als u samenwerkt met gebouwen naast of dicht bij uw gebouw."
            " Bespreek dit met die buren en vul de keuzewijzer opnieuw in met de gegevens van alle gebouwen samen."
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
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_dak_m2=Decimal("0"),
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
            beschikbare_collectieve_ruimte_tuin_m2=Decimal("999"),
            beschikbare_collectieve_ruimte_dak_m2=Decimal("0"),
        )

        result = Eliminatie().calculate(calc_input, hoofdsysteem.naam)
        assert result["is_mogelijk"] is False, result
        assert result["redenen"] == [
            f"Er wordt tussen {warmtenet_start} en {warmtenet_stop} een warmtenet verwacht in uw buurt. Dit is later dan de verduurzaming in {jaar_vervangen}."
        ], result
