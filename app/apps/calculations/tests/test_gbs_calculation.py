from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, EnergieType
from apps.calculations.models import GebruikersInvoer
from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    calculate_gbs,
)
from apps.kengetallen.models import ScenarioKeuze, Subkengetal
from apps.systemen.models import Subsysteem


def _calculation_input(**overrides: object) -> GebruikersInvoer:
    defaults: dict[str, object] = {
        "bouwjaar": 1990,
        "bruto_vloeroppervlak": Decimal("1234.5"),
        "aantal_woningen": 200,
        "mechanische_ventilatie_aanwezig": True,
        "vloerverwarming_aanwezig": False,
        "tapwater_op_gas": True,
        "koken_op_gas": False,
        "gasverbruik_vve_totaal": Decimal("1334.6"),
        "wens_tot_koelen": False,
    }
    defaults.update(overrides)
    return GebruikersInvoer.objects.create(**defaults)


class GbsCalculationTest(TestCase):
    fixtures = ["fixtures"]

    def test_subsysteem_calculate_gbs_requires_calculation_input(self):
        subsysteem = Subsysteem.objects.get(naam="Bodemlus Collectief")
        self.assertEqual(subsysteem.calculation_method, SubsysteemCalculationMethod.Gbs)

        energie = EnergieCalculator().calculate(_calculation_input(aantal_woningen=150))

        with self.assertRaisesMessage(
            ValueError, "calculation_input is required for GBS calculations"
        ):
            subsysteem.calculate(
                scenarios=(ScenarioKeuze.MIDDEN,),
                energie_calculation=energie,
                calculation_input=None,
            )

    def test_subsysteem_calculate_gbs_matches_direct_calculate_gbs(self):
        subsysteem = Subsysteem.objects.get(naam="Bodemlus Collectief")
        self.assertEqual(subsysteem.calculation_method, SubsysteemCalculationMethod.Gbs)

        subkengetal = Subkengetal.objects.get(
            subsysteem=subsysteem,
            scenario=ScenarioKeuze.MIDDEN,
        )

        calc_input = _calculation_input(aantal_woningen=150)
        energie = EnergieCalculator().calculate(calc_input)
        cv_row = energie.by_scenario[str(ScenarioKeuze.MIDDEN)][EnergieType.CV]

        direct = calculate_gbs(
            subkengetal,
            cv_energie_calculation=cv_row,
            aantal_woningen=calc_input.aantal_woningen,
        )

        full = subsysteem.calculate(
            scenarios=(ScenarioKeuze.MIDDEN,),
            energie_calculation=energie,
            calculation_input=calc_input,
        )
        via_model = full.by_scenario[str(ScenarioKeuze.MIDDEN)].berekening

        self.assertEqual(
            via_model.afschrijving_eur_per_woning_per_jaar,
            direct.afschrijving_eur_per_woning_per_jaar,
        )
        self.assertEqual(
            via_model.onderhoud_eur_per_woning_per_jaar,
            direct.onderhoud_eur_per_woning_per_jaar,
        )
