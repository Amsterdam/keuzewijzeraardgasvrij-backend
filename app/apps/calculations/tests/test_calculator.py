from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, EnergieType
from apps.calculations.models import Conversie, GebruikersInvoer
from apps.kengetallen.models import AlgemeenKengetal, ScenarioKeuze


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
                    koken_op_gas=False,
                    gasverbruik_vve_totaal=gasverbruik_vve_totaal,
                )
                energie = EnergieCalculator().calculate(calc_input)
                result = energie.by_scenario[str(scenario)][EnergieType.TAP]
                expected_vermogen = warmtevraag_tap * gelijktijdigheid_tap
                expected_gas = (
                    (Decimal(1) - percentage_ruimteverwarming) * gasverbruik_vve_totaal
                    if tapwater_op_gas
                    else Decimal(0)
                )
                expected_kwh = (
                    expected_gas
                    * rendement_gasketel
                    * conversie_m3gas_naar_kwh
                    / aantal_woningen
                )
                expected_gj = expected_kwh * conversie_kwh_naar_gj

                self.assertEqual(result.energie_type, EnergieType.TAP)
                self.assertEqual(result.scenario, str(scenario))
                self.assertEqual(
                    result.vermogen_warmte_kw_per_woning, expected_vermogen
                )
                self.assertEqual(
                    result.vermogen_warmte_kw_per_vve,
                    expected_vermogen * Decimal(aantal_woningen),
                )
                self.assertEqual(result.gas_m3_per_year, expected_gas)
                self.assertEqual(
                    result.capaciteit_warmte_kwh_per_year_per_woning, expected_kwh
                )
                self.assertEqual(
                    result.capaciteit_warmte_gj_per_year_per_woning, expected_gj
                )

    def test_cv_all_scenarios_tapwater_true_and_false(self):
        aantal_woningen = 200
        gasverbruik_vve_totaal = Decimal("1334.6")

        calculator = EnergieCalculator()

        conversie_m3gas_naar_kwh = self._conversie("m3gas_naar_kwh")
        conversie_kwh_naar_gj = self._conversie("kwh_naar_gj")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            gelijktijdigheid_cv_fallback = self._kengetal(
                scenario, "gelijktijdigheid_cv"
            )
            percentage_ruimteverwarming = self._kengetal(
                scenario, "percentage_ruimteverwarming"
            )
            rendement_gasketel = self._kengetal(scenario, "rendement_gasketel")

            gelijktijdigheid_cv = calculator._get_gelijktijdigheidcv_factor(
                aantal_woningen=aantal_woningen,
                fallback=gelijktijdigheid_cv_fallback,
            )

            vermogen_cv_max = self._kengetal(scenario, "vermogen_cv_max")

            for tapwater_op_gas in (True, False):
                calc_input = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    koken_op_gas=False,
                    gasverbruik_vve_totaal=gasverbruik_vve_totaal,
                    dubbel_glas=False,
                    wtw_aanwezig=False,
                    bouwjaar=1990,
                )
                energie = calculator.calculate(calc_input)
                result = energie.by_scenario[str(scenario)][EnergieType.CV]

                expected_woning_type = "Ouder dan 2000"
                expected_vermogen_cv = vermogen_cv_max
                expected_vermogen = (
                    expected_vermogen_cv
                    * calc_input.bruto_vloeroppervlak
                    * gelijktijdigheid_cv
                    / Decimal(aantal_woningen)
                )
                expected_gas = (
                    percentage_ruimteverwarming * gasverbruik_vve_totaal
                    if tapwater_op_gas
                    else gasverbruik_vve_totaal
                )
                expected_kwh = (
                    expected_gas
                    * rendement_gasketel
                    * conversie_m3gas_naar_kwh
                    / aantal_woningen
                )
                expected_gj = expected_kwh * conversie_kwh_naar_gj

                self.assertEqual(result.energie_type, EnergieType.CV)
                self.assertEqual(result.scenario, str(scenario))
                self.assertEqual(result.woning_type, expected_woning_type)
                self.assertEqual(result.vermogen_cv, expected_vermogen_cv)
                self.assertEqual(
                    result.vermogen_warmte_kw_per_woning, expected_vermogen
                )
                self.assertEqual(
                    result.vermogen_warmte_kw_per_vve,
                    expected_vermogen * Decimal(aantal_woningen),
                )
                self.assertEqual(result.gas_m3_per_year, expected_gas)
                self.assertEqual(
                    result.capaciteit_warmte_kwh_per_year_per_woning, expected_kwh
                )
                self.assertEqual(
                    result.capaciteit_warmte_gj_per_year_per_woning, expected_gj
                )

    def test_gkw_all_scenarios_tapwater_true_and_false(self):
        aantal_woningen = 200
        conversie_kwh_naar_gj = self._conversie("kwh_naar_gj")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            warmtevraag_koude = self._kengetal(scenario, "warmtevraag_koude")
            koudevraag_capaciteit = self._kengetal(scenario, "koudevraag_capaciteit")

            calc_input = _calculation_input()
            energie = EnergieCalculator().calculate(calc_input)
            result = energie.by_scenario[str(scenario)][EnergieType.GKW]

            expected_vermogen = (
                warmtevraag_koude
                * calc_input.bruto_vloeroppervlak
                / Decimal(calc_input.aantal_woningen)
            )
            expected_kwh = koudevraag_capaciteit * calc_input.bruto_vloeroppervlak
            expected_gj = expected_kwh * conversie_kwh_naar_gj

            self.assertEqual(result.energie_type, EnergieType.GKW)
            self.assertEqual(result.scenario, str(scenario))
            self.assertEqual(result.vermogen_warmte_kw_per_woning, expected_vermogen)
            self.assertEqual(
                result.vermogen_warmte_kw_per_vve,
                expected_vermogen * Decimal(aantal_woningen),
            )
            self.assertEqual(result.gas_m3_per_year, Decimal("0"))
            self.assertEqual(
                result.capaciteit_warmte_kwh_per_year_per_woning, expected_kwh
            )
            self.assertEqual(
                result.capaciteit_warmte_gj_per_year_per_woning, expected_gj
            )

    def test_tap_koken_op_gas_subtracts_gasvraag_koken(self):
        aantal_woningen = 200
        gasverbruik_vve_totaal = Decimal("1334.6")
        conversie_m3gas_naar_kwh = self._conversie("m3gas_naar_kwh")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            percentage_ruimteverwarming = self._kengetal(
                scenario, "percentage_ruimteverwarming"
            )
            rendement_gasketel = self._kengetal(scenario, "rendement_gasketel")
            gasvraag_koken = self._kengetal(scenario, "gasvraag_koken")

            base = _calculation_input(
                aantal_woningen=aantal_woningen,
                tapwater_op_gas=True,
                koken_op_gas=False,
                gasverbruik_vve_totaal=gasverbruik_vve_totaal,
            )
            with_koken_op_gas = _calculation_input(
                aantal_woningen=aantal_woningen,
                tapwater_op_gas=True,
                koken_op_gas=True,
                gasverbruik_vve_totaal=gasverbruik_vve_totaal,
            )

            base_energie = EnergieCalculator().calculate(base)
            koken_energie = EnergieCalculator().calculate(with_koken_op_gas)

            base_result = base_energie.by_scenario[str(scenario)][EnergieType.TAP]
            koken_result = koken_energie.by_scenario[str(scenario)][EnergieType.TAP]

            expected_delta_gas = (
                Decimal(1) - percentage_ruimteverwarming
            ) * gasvraag_koken
            self.assertEqual(
                base_result.gas_m3_per_year - koken_result.gas_m3_per_year,
                expected_delta_gas,
            )

            expected_delta_kwh = (
                expected_delta_gas
                * rendement_gasketel
                * conversie_m3gas_naar_kwh
                / aantal_woningen
            )
            self.assertEqual(
                base_result.capaciteit_warmte_kwh_per_year_per_woning
                - koken_result.capaciteit_warmte_kwh_per_year_per_woning,
                expected_delta_kwh,
            )

    def test_cv_koken_op_gas_subtracts_gasvraag_koken(self):
        aantal_woningen = 200
        conversie_m3gas_naar_kwh = self._conversie("m3gas_naar_kwh")

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            percentage_ruimteverwarming = self._kengetal(
                scenario, "percentage_ruimteverwarming"
            )
            rendement_gasketel = self._kengetal(scenario, "rendement_gasketel")
            gasvraag_koken = self._kengetal(scenario, "gasvraag_koken")

            for tapwater_op_gas in (True, False):
                base = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    koken_op_gas=False,
                )
                with_koken_op_gas = _calculation_input(
                    aantal_woningen=aantal_woningen,
                    tapwater_op_gas=tapwater_op_gas,
                    koken_op_gas=True,
                )

                base_energie = EnergieCalculator().calculate(base)
                koken_energie = EnergieCalculator().calculate(with_koken_op_gas)

                base_result = base_energie.by_scenario[str(scenario)][EnergieType.CV]
                koken_result = koken_energie.by_scenario[str(scenario)][EnergieType.CV]

                factor = percentage_ruimteverwarming if tapwater_op_gas else Decimal(1)
                expected_delta_gas = factor * gasvraag_koken
                self.assertEqual(
                    base_result.gas_m3_per_year - koken_result.gas_m3_per_year,
                    expected_delta_gas,
                )

                expected_delta_kwh = (
                    expected_delta_gas
                    * rendement_gasketel
                    * conversie_m3gas_naar_kwh
                    / aantal_woningen
                )
                self.assertEqual(
                    base_result.capaciteit_warmte_kwh_per_year_per_woning
                    - koken_result.capaciteit_warmte_kwh_per_year_per_woning,
                    expected_delta_kwh,
                )
