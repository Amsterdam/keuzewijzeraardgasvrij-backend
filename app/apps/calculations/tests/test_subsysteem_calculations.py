from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.subsysteem_calculations import SubsysteemCalculationMethod
from apps.kengetallen.models import ScenarioKeuze, Subkengetal
from apps.systemen.models import Subsysteem


class SubsysteemCalculateTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_investering_all_scenarios(self):
        subsysteem = Subsysteem.objects.get(naam="Itho HPS 55 (split)")
        self.assertEqual(
            subsysteem.calculation_method, SubsysteemCalculationMethod.Investering
        )

        subsysteem_calculations = subsysteem.calculate()

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            subkengetal = Subkengetal.objects.get(
                subsysteem=subsysteem, scenario=scenario
            )

            expected_afschrijving = subkengetal.investeringskosten / Decimal(
                subkengetal.levensduur
            )
            expected_onderhoud = (
                subkengetal.investeringskosten * subkengetal.beheer_en_onderhoud
            )

            result = subsysteem_calculations.by_scenario[str(scenario)]
            self.assertEqual(
                result.berekening.afschrijving_eur_per_woning_per_jaar,
                expected_afschrijving,
            )
            self.assertEqual(
                result.berekening.onderhoud_eur_per_woning_per_jaar,
                expected_onderhoud,
            )
