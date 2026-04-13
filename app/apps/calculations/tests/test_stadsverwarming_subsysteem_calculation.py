from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, StadsverwarmingCalculator
from apps.calculations.models import GebruikersInvoer
from apps.calculations.subsysteem_calculations import calculate_stadsverwarming
from apps.kengetallen.models import ScenarioKeuze
from apps.systemen.models import Subsysteem


def _calculation_input(**overrides: object) -> GebruikersInvoer:
    defaults: dict[str, object] = {
        "bouwjaar": 1990,
        "bruto_vloeroppervlak": Decimal("1234.5"),
        "aantal_woningen": 200,
        "mechanische_ventilatie_aanwezig": True,
        "vloerverwarming_aanwezig": False,
        "inpandige_berging_aanwezig": True,
        "ruimte_op_het_dak_aanwezig": True,
        "type_dak": "plat_dak",
        "tapwater_op_gas": True,
        "koken_op_gas": False,
        "gasverbruik_vve_totaal": Decimal("1334.6"),
        "elektriciteitsverbruik_per_woning": Decimal("1000"),
        "elektriciteitsverbruik_vve_totaal": Decimal("10000"),
        "gecontracteerd_vermogen": Decimal("50"),
        "huidige_warmtesysteem": "cv_ketel",
        "volledig_gasloos": False,
        "wens_tot_koelen": False,
    }
    defaults.update(overrides)
    return GebruikersInvoer.objects.create(**defaults)


class StadsverwarmingSubsysteemCalculationTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_stadsverwarming_maps_to_correct_totals(self):
        calc_input = _calculation_input(aantal_woningen=200)
        energie = EnergieCalculator().calculate(calc_input)
        stadsverwarming_result = StadsverwarmingCalculator().calculate(
            energie_calculation=energie,
            aantal_woningen=calc_input.aantal_woningen,
        )

        scenario = ScenarioKeuze.MIDDEN
        totals = stadsverwarming_result.kosten_totals_by_scenario[str(scenario)]

        for subsysteem_naam, expected in (
            (
                "Particulier Stadswarmte",
                totals.stadsverwarming_kosten_particulier_warmte,
            ),
            (
                "Particulier Stadswarmte + koude",
                totals.stadsverwarming_kosten_particulier_koude,
            ),
            ("Zakelijk Stadswarmte", totals.stadsverwarming_kosten_zakelijk_warmte),
            (
                "Zakelijk Stadswarmte + koude",
                totals.stadsverwarming_kosten_zakelijk_warmte_koude,
            ),
        ):
            berekening = calculate_stadsverwarming(
                subsysteem_naam,
                stadsverwarming_result,
                scenario,
            )
            self.assertEqual(
                berekening.afschrijving_eur_per_woning_per_jaar, Decimal("0")
            )
            self.assertEqual(berekening.onderhoud_eur_per_woning_per_jaar, Decimal("0"))
            self.assertEqual(berekening.tco, expected * Decimal("30"))

    def test_subsysteem_calculate_stadsverwarming_uses_calculator_totals(self):
        subsysteem = Subsysteem.objects.get(naam="Particulier Stadswarmte")

        calc_input = _calculation_input(aantal_woningen=200)
        energie = EnergieCalculator().calculate(calc_input)
        stadsverwarming_result = StadsverwarmingCalculator().calculate(
            energie_calculation=energie,
            aantal_woningen=calc_input.aantal_woningen,
        )
        expected = stadsverwarming_result.kosten_totals_by_scenario[
            str(ScenarioKeuze.MIDDEN)
        ].stadsverwarming_kosten_particulier_warmte

        full = subsysteem.calculate(
            scenarios=(ScenarioKeuze.MIDDEN,),
            energie_calculation=energie,
            calculation_input=calc_input,
        )
        via_model = full.by_scenario[str(ScenarioKeuze.MIDDEN)].berekening
        self.assertEqual(via_model.onderhoud_eur_per_woning_per_jaar, Decimal("0"))
        self.assertEqual(via_model.tco, expected * Decimal("30"))
