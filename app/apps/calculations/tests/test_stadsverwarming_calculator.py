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

    def _assert_scenario_totals(self, result, scenario_key: str) -> None:
        totals = result.kosten_totals_by_scenario[scenario_key]
        scenario_rows = result.by_scenario[scenario_key]

        expected_particulier_warmte = sum(
            (r.stadsverwarming_kosten_particulier_warmte for r in scenario_rows),
            start=Decimal("0"),
        )
        expected_particulier_koude = sum(
            (r.stadsverwarming_kosten_particulier_koude for r in scenario_rows),
            start=Decimal("0"),
        )
        expected_zakelijk_warmte = sum(
            (r.stadsverwarming_kosten_zakelijk_warmte for r in scenario_rows),
            start=Decimal("0"),
        )
        expected_zakelijk_warmte_koude = sum(
            (r.stadsverwarming_kosten_zakelijk_warmte_koude for r in scenario_rows),
            start=Decimal("0"),
        )

        self.assertEqual(
            totals.stadsverwarming_kosten_particulier_warmte,
            expected_particulier_warmte,
        )
        self.assertEqual(
            totals.stadsverwarming_kosten_particulier_koude, expected_particulier_koude
        )
        self.assertEqual(
            totals.stadsverwarming_kosten_zakelijk_warmte, expected_zakelijk_warmte
        )
        self.assertEqual(
            totals.stadsverwarming_kosten_zakelijk_warmte_koude,
            expected_zakelijk_warmte_koude,
        )

        self.assertGreater(
            totals.stadsverwarming_kosten_particulier_warmte, Decimal("0")
        )
        self.assertGreater(
            totals.stadsverwarming_kosten_particulier_koude, Decimal("0")
        )
        self.assertGreater(totals.stadsverwarming_kosten_zakelijk_warmte, Decimal("0"))
        self.assertGreater(
            totals.stadsverwarming_kosten_zakelijk_warmte_koude, Decimal("0")
        )

    def test_zakelijk_koude_variabel_jaarlijks(self):
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

        self._assert_scenario_totals(result, str(ScenarioKeuze.MIDDEN))

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

        self.assertEqual(match.waarde_vast, Decimal("0"))
        self.assertEqual(match.waarde_geclassificeerd, Decimal("0"))

        expected_total = expected_waarde_variabel * expected_factor_collectief
        self.assertEqual(match.stadsverwarming_kosten_totaal, expected_total)

        self.assertEqual(match.stadsverwarming_kosten_particulier_warmte, Decimal("0"))
        self.assertEqual(match.stadsverwarming_kosten_particulier_koude, Decimal("0"))
        self.assertEqual(match.stadsverwarming_kosten_zakelijk_warmte, Decimal("0"))
        self.assertEqual(
            match.stadsverwarming_kosten_zakelijk_warmte_koude, expected_total
        )

    def test_particulier_warmte_koude_vast_jaarlijks(self):
        calc_input = _calculation_input(aantal_woningen=200)
        energie = EnergieCalculator().calculate(calc_input)

        kengetal = StadsverwarmingKengetal.objects.get(
            klanttype=StadsverwarmingKlantType.PARTICULIER,
            producttype=StadsverwarmingProductType.WARMTE_KOUDE,
            kostetype="Vastrecht warmte",
            eenheid=StadsverwarmingEenheid.VAST,
            interval=StadsverwarmingInterval.JAARLIJKS,
            vermogen_berekenen_op=None,
        )

        result = StadsverwarmingCalculator().calculate(
            energie_calculation=energie,
            aantal_woningen=calc_input.aantal_woningen,
        )

        self._assert_scenario_totals(result, str(ScenarioKeuze.MIDDEN))

        scenario_key = str(ScenarioKeuze.MIDDEN)
        match = next(
            r for r in result.by_scenario[scenario_key] if r.kengetal_id == kengetal.id
        )

        self.assertIsNone(match.te_berekenen_vermogen)
        self.assertFalse(match.is_tussen_min_max)
        self.assertFalse(match.is_boven_max)

        self.assertEqual(match.factor_collectief, Decimal("1"))
        self.assertEqual(match.factor_naar_jaar, Decimal("1"))

        self.assertEqual(match.waarde_vast, kengetal.waarde_1)
        self.assertEqual(match.waarde_variabel, Decimal("0"))
        self.assertEqual(match.waarde_geclassificeerd, Decimal("0"))

        self.assertEqual(match.stadsverwarming_kosten_totaal, kengetal.waarde_1)
        self.assertEqual(
            match.stadsverwarming_kosten_particulier_warmte, kengetal.waarde_1
        )
        self.assertEqual(
            match.stadsverwarming_kosten_particulier_koude, kengetal.waarde_1
        )
        self.assertEqual(match.stadsverwarming_kosten_zakelijk_warmte, Decimal("0"))
        self.assertEqual(
            match.stadsverwarming_kosten_zakelijk_warmte_koude, Decimal("0")
        )

    def test_zakelijk_warmte_koude_variabel_maandelijks_quadratic_nonzero(self):
        calc_input = _calculation_input(aantal_woningen=200)
        energie = EnergieCalculator().calculate(calc_input)

        kengetal = StadsverwarmingKengetal.objects.get(
            klanttype=StadsverwarmingKlantType.ZAKELIJK,
            producttype=StadsverwarmingProductType.WARMTE_KOUDE,
            kostetype="Vastrecht periodiek",
            eenheid=StadsverwarmingEenheid.VARIABEL,
            interval=StadsverwarmingInterval.MAANDELIJKS,
            vermogen_berekenen_op=StadsverwarmingVermogenBerekenenOp.WARMTE,
            kw_min=Decimal("0"),
            kw_max=Decimal("999"),
        )

        result = StadsverwarmingCalculator().calculate(
            energie_calculation=energie,
            aantal_woningen=calc_input.aantal_woningen,
        )

        self._assert_scenario_totals(result, str(ScenarioKeuze.MIDDEN))

        scenario_key = str(ScenarioKeuze.MIDDEN)
        match = next(
            r for r in result.by_scenario[scenario_key] if r.kengetal_id == kengetal.id
        )

        expected_te_berekenen_vermogen = (
            energie.by_scenario[scenario_key][EnergieType.CV].vermogen_warmte_kw_per_vve
            + energie.by_scenario[scenario_key][
                EnergieType.TAP
            ].vermogen_warmte_kw_per_vve
        )
        self.assertEqual(match.te_berekenen_vermogen, expected_te_berekenen_vermogen)

        expected_is_boven_max = expected_te_berekenen_vermogen >= kengetal.kw_max
        expected_is_tussen_min_max = (
            kengetal.kw_min <= expected_te_berekenen_vermogen < kengetal.kw_max
        )
        self.assertEqual(match.is_tussen_min_max, expected_is_tussen_min_max)
        self.assertEqual(match.is_boven_max, expected_is_boven_max)

        if expected_is_tussen_min_max:
            expected_waarde_variabel = expected_te_berekenen_vermogen * (
                kengetal.waarde_1 - (kengetal.waarde_2 * expected_te_berekenen_vermogen)
            )
        else:
            expected_waarde_variabel = (kengetal.kw_max - kengetal.kw_min) * (
                kengetal.waarde_1
                - (kengetal.waarde_2 * (kengetal.kw_max - kengetal.kw_min))
            )

        self.assertEqual(match.waarde_variabel, expected_waarde_variabel)
        self.assertEqual(match.waarde_vast, Decimal("0"))
        self.assertEqual(match.waarde_geclassificeerd, Decimal("0"))

        expected_factor_collectief = Decimal("1") / Decimal(calc_input.aantal_woningen)
        self.assertEqual(match.factor_collectief, expected_factor_collectief)
        self.assertEqual(match.factor_naar_jaar, Decimal("12"))

        expected_total = (
            expected_waarde_variabel * Decimal("12") * expected_factor_collectief
        )
        self.assertEqual(match.stadsverwarming_kosten_totaal, expected_total)

        self.assertEqual(match.stadsverwarming_kosten_particulier_warmte, Decimal("0"))
        self.assertEqual(match.stadsverwarming_kosten_particulier_koude, Decimal("0"))
        self.assertEqual(match.stadsverwarming_kosten_zakelijk_warmte, expected_total)
        self.assertEqual(
            match.stadsverwarming_kosten_zakelijk_warmte_koude, expected_total
        )
