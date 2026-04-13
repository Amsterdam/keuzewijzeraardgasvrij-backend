from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, EnergieType
from apps.calculations.models import Conversie, GebruikersInvoer
from apps.calculations.subsysteem_calculations import (
    SubsysteemCalculationMethod,
    calculate_openbron_systeem,
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


class OpenbronCalculationTest(TestCase):
    fixtures = ["fixtures"]

    @staticmethod
    def _conversie(naam: str) -> Decimal:
        return Conversie.objects.get(naam=naam).waarde

    def test_calculate_openbron_systeem_matches_formula_all_scenarios(self):
        subsysteem = Subsysteem.objects.get(pk=4)
        self.assertEqual(
            subsysteem.calculation_method, SubsysteemCalculationMethod.Openbron
        )

        calc_input = _calculation_input()
        energie = EnergieCalculator().calculate(calc_input)

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            subkengetal = Subkengetal.objects.get(
                subsysteem=subsysteem, scenario=scenario
            )
            cv_row = energie.by_scenario[str(scenario)][EnergieType.CV]

            result = calculate_openbron_systeem(
                subkengetal,
                cv_energie_calculation=cv_row,
            )

            # Compute expected values using the same formula, but without hard-coded constants.
            conversie_m3_naar_l = self._conversie("m3_naar_l")
            conversie_h_naar_sec = self._conversie("h_naar_sec")
            conversie_kj_naar_j = self._conversie("kj_naar_j")

            debiet_bron_l_per_s = (
                Decimal(subkengetal.debiet_bron)
                * conversie_m3_naar_l
                / conversie_h_naar_sec
            )
            joule_per_liter = (
                subkengetal.energie_bron
                * Decimal(subkengetal.delta_temperatuur_retour)
                * conversie_kj_naar_j
            )

            cv_w_per_woning = cv_row.vermogen_warmte_kw_per_woning * Decimal("1000")
            aantal_woningen_op_bron = (
                debiet_bron_l_per_s
                * joule_per_liter
                / (cv_w_per_woning * subkengetal.verhouding_vermogen_bron)
            )
            investering_eur_per_woning = (
                subkengetal.investeringskosten / aantal_woningen_op_bron
            )

            expected_afschrijving = investering_eur_per_woning / Decimal(
                subkengetal.levensduur
            )
            expected_onderhoud = (
                investering_eur_per_woning * subkengetal.beheer_en_onderhoud
            )

            self.assertEqual(
                result.afschrijving_eur_per_woning_per_jaar,
                expected_afschrijving,
            )
            self.assertEqual(
                result.onderhoud_eur_per_woning_per_jaar,
                expected_onderhoud,
            )

    def test_subsysteem_calculate_openbron_uses_cv_energy_result(self):
        subsysteem = Subsysteem.objects.get(pk=4)
        self.assertEqual(
            subsysteem.calculation_method, SubsysteemCalculationMethod.Openbron
        )

        calc_input = _calculation_input()
        energie = EnergieCalculator().calculate(calc_input)

        subsysteem_calculations = subsysteem.calculate(energie_calculation=energie)

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            subkengetal = Subkengetal.objects.get(
                subsysteem=subsysteem, scenario=scenario
            )
            cv_row = energie.by_scenario[str(scenario)][EnergieType.CV]
            direct = calculate_openbron_systeem(
                subkengetal, cv_energie_calculation=cv_row
            )

            via_model = subsysteem_calculations.by_scenario[str(scenario)].berekening

            self.assertEqual(
                via_model.afschrijving_eur_per_woning_per_jaar,
                direct.afschrijving_eur_per_woning_per_jaar,
            )
            self.assertEqual(
                via_model.onderhoud_eur_per_woning_per_jaar,
                direct.onderhoud_eur_per_woning_per_jaar,
            )
