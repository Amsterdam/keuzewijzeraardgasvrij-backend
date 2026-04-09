from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import (
    EnergieCalculator,
    EnergieType,
    StadsverwarmingCalculator,
)
from apps.calculations.models import GebruikersInvoer
from apps.kengetallen.models import (
    ScenarioKeuze,
    StadsverwarmingEenheid,
    StadsverwarmingInterval,
    StadsverwarmingKengetal,
    StadsverwarmingKlantType,
    StadsverwarmingProductType,
    StadsverwarmingVermogenBerekenenOp,
)


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
        "gasverbruik_per_woning": Decimal("500"),
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


class StadsverwarmingCalculatorTest(TestCase):
    fixtures = ["fixtures"]

    def test_zakelijk_koude_variabel_jaarlijks_costs_and_flags(self):
        calc_input = _calculation_input(aantal_woningen=200)
        energie = EnergieCalculator().calculate(calc_input)

        kengetal = StadsverwarmingKengetal.objects.get(
            klanttype=StadsverwarmingKlantType.ZAKELIJK,
            producttype=StadsverwarmingProductType.KOUDE,
            kostetype="Vastrecht periodiek",
            eenheid=StadsverwarmingEenheid.VARIABEL,
            interval=StadsverwarmingInterval.JAARLIJKS,
            vermogen_berekenen_op=StadsverwarmingVermogenBerekenenOp.KOUDE,
        )

        result = StadsverwarmingCalculator().calculate(
            energie_calculation=energie,
            aantal_woningen=calc_input.aantal_woningen,
        )

        scenario_key = str(ScenarioKeuze.MIDDEN)
        match = next(
            r for r in result.by_scenario[scenario_key] if r.kengetal_id == kengetal.id
        )

        te_berekenen_vermogen = energie.by_scenario[scenario_key][
            EnergieType.GKW
        ].vermogen_warmte_kw_per_vve
        self.assertEqual(match.te_berekenen_vermogen, te_berekenen_vermogen)

        self.assertTrue(match.is_tussen_min_max)
        self.assertFalse(match.is_boven_max)

        expected_factor_collectief = Decimal("1") / Decimal(calc_input.aantal_woningen)
        self.assertEqual(match.factor_collectief, expected_factor_collectief)

        self.assertEqual(match.factor_naar_jaar, Decimal("1"))

        expected_waarde_variabel = (
            te_berekenen_vermogen - kengetal.kw_min
        ) * kengetal.waarde_1
        self.assertEqual(match.waarde_variabel, expected_waarde_variabel)

        expected_total = expected_waarde_variabel * expected_factor_collectief
        self.assertEqual(match.stadsverwarming_kosten_totaal, expected_total)

        self.assertEqual(match.stadsverwarming_kosten_particulier, Decimal("0"))
        self.assertEqual(match.stadsverwarming_kosten_zakelijk_warmte, Decimal("0"))
        self.assertEqual(
            match.stadsverwarming_kosten_zakelijk_warmte_koude, expected_total
        )
