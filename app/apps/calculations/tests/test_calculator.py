from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, EnergieType
from apps.calculations.models import CalculationInput, Conversie
from apps.kengetallen.models import AlgemeenKengetal, ScenarioKeuze


def _calculation_input(**overrides: object) -> CalculationInput:
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
    return CalculationInput.objects.create(**defaults)


class EnergieCalculatorTest(TestCase):
    fixtures = ["fixtures"]

    @staticmethod
    def _kengetal(scenario: ScenarioKeuze, naam: str) -> Decimal:
        return AlgemeenKengetal.objects.get(scenario=scenario, naam=naam).waarde

    @staticmethod
    def _conversie(naam: str) -> Decimal:
        return Conversie.objects.get(naam=naam).waarde

    def test_tap_all_scenarios_tapwater_true_and_false(self):
        aantal_woningen = 200
        gasverbruik_vve_totaal = Decimal("1334.6")

        conversie_m3gas_naar_kwh = self._conversie("m3gas_naar_kwh")
        conversie_kwh_naar_gj = self._conversie("kwh_naar_gj")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            warmtevraag_tap = self._kengetal(scenario, "warmtevraag_tap")
            gelijktijdigheid_tap = 1 / Decimal(aantal_woningen).sqrt()
            percentage_ruimteverwarming = self._kengetal(
                scenario, "percentage_ruimteverwarming"
            )
            rendement_gasketel = self._kengetal(scenario, "rendement_gasketel")

            for tapwater_op_gas in (True, False):
                calc_input = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    gasverbruik_vve_totaal=gasverbruik_vve_totaal,
                )
                result = EnergieCalculator().calculate(
                    EnergieType.TAP, scenario, calc_input
                )

                expected_vermogen = warmtevraag_tap * gelijktijdigheid_tap
                expected_gas = (
                    (Decimal(1) - percentage_ruimteverwarming) * gasverbruik_vve_totaal
                    if tapwater_op_gas
                    else Decimal(0)
                )
                expected_kwh = (
                    expected_gas * rendement_gasketel * conversie_m3gas_naar_kwh
                )
                expected_gj = expected_kwh * conversie_kwh_naar_gj

                self.assertEqual(result["Type"], EnergieType.TAP)
                self.assertEqual(result["Scenario"], str(scenario))
                self.assertEqual(
                    result["Vermogen warmte [kW/woning]"], expected_vermogen
                )
                self.assertEqual(
                    result["Vermogen warmte [kW/vve]"],
                    expected_vermogen * Decimal(aantal_woningen),
                )
                self.assertEqual(result["Gas [m³/j]"], expected_gas)
                self.assertEqual(result["Capaciteit warmte [kWh/j/w]"], expected_kwh)
                self.assertEqual(result["Capaciteit warmte [GJ/j/w]"], expected_gj)

    def test_cv_all_scenarios_tapwater_true_and_false(self):
        aantal_woningen = 200
        gasverbruik_vve_totaal = Decimal("1334.6")

        conversie_m3gas_naar_kwh = self._conversie("m3gas_naar_kwh")
        conversie_kwh_naar_gj = self._conversie("kwh_naar_gj")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            warmtevraag_cv = self._kengetal(scenario, "warmtevraag_cv")
            gelijktijdigheid_cv = self._kengetal(scenario, "gelijktijdigheid_cv")
            percentage_ruimteverwarming = self._kengetal(
                scenario, "percentage_ruimteverwarming"
            )
            rendement_gasketel = self._kengetal(scenario, "rendement_gasketel")

            for tapwater_op_gas in (True, False):
                calc_input = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    gasverbruik_vve_totaal=gasverbruik_vve_totaal,
                )
                result = EnergieCalculator().calculate(
                    EnergieType.CV, scenario, calc_input
                )

                expected_vermogen = warmtevraag_cv * gelijktijdigheid_cv
                expected_gas = (
                    percentage_ruimteverwarming * gasverbruik_vve_totaal
                    if tapwater_op_gas
                    else gasverbruik_vve_totaal
                )
                expected_kwh = (
                    expected_gas * rendement_gasketel * conversie_m3gas_naar_kwh
                )
                expected_gj = expected_kwh * conversie_kwh_naar_gj

                self.assertEqual(result["Type"], EnergieType.CV)
                self.assertEqual(result["Scenario"], str(scenario))
                self.assertEqual(
                    result["Vermogen warmte [kW/woning]"], expected_vermogen
                )
                self.assertEqual(
                    result["Vermogen warmte [kW/vve]"],
                    expected_vermogen * Decimal(aantal_woningen),
                )
                self.assertEqual(result["Gas [m³/j]"], expected_gas)
                self.assertEqual(result["Capaciteit warmte [kWh/j/w]"], expected_kwh)
                self.assertEqual(result["Capaciteit warmte [GJ/j/w]"], expected_gj)

    def test_gkw_all_scenarios_tapwater_true_and_false(self):
        aantal_woningen = 200
        gasverbruik_vve_totaal = Decimal("1334.6")

        conversie_kwh_naar_gj = self._conversie("kwh_naar_gj")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            warmtevraag_koude = self._kengetal(scenario, "warmtevraag_koude")
            koudevraag_capaciteit = self._kengetal(scenario, "koudevraag_capaciteit")

            for tapwater_op_gas in (True, False):
                calc_input = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    gasverbruik_vve_totaal=gasverbruik_vve_totaal,
                )
                result = EnergieCalculator().calculate(
                    EnergieType.GKW, scenario, calc_input
                )

                expected_vermogen = warmtevraag_koude
                expected_kwh = koudevraag_capaciteit
                expected_gj = expected_kwh * conversie_kwh_naar_gj

                self.assertEqual(result["Type"], EnergieType.GKW)
                self.assertEqual(result["Scenario"], str(scenario))
                self.assertEqual(
                    result["Vermogen warmte [kW/woning]"], expected_vermogen
                )
                self.assertEqual(
                    result["Vermogen warmte [kW/vve]"],
                    expected_vermogen * Decimal(aantal_woningen),
                )
                self.assertEqual(result["Gas [m³/j]"], Decimal("0"))
                self.assertEqual(result["Capaciteit warmte [kWh/j/w]"], expected_kwh)
                self.assertEqual(result["Capaciteit warmte [GJ/j/w]"], expected_gj)
