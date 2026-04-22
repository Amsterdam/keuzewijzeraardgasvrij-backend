from __future__ import annotations

import math
from decimal import Decimal

from django.test import TestCase

from apps.calculations.models import Conversie
from apps.calculations.subsysteem_calculations import calculate_staffel
from apps.kengetallen.models import ScenarioKeuze, Subkengetal


class StaffelCalculationTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_staffel_regeneratie_all_scenarios(self):
        # Regeneratie is subsysteem pk=6 in fixtures.
        aantal_woningen = 200
        jaren_tco = Conversie.objects.get(naam="jaren_tco").waarde

        for scenario in (ScenarioKeuze.LAAG, ScenarioKeuze.MIDDEN, ScenarioKeuze.HOOG):
            subkengetal = Subkengetal.objects.get(
                subsysteem_id=6,
                scenario=str(scenario),
            )

            self.assertIsNotNone(subkengetal.staffel)
            self.assertGreater(subkengetal.staffel, Decimal("0"))

            berekening = calculate_staffel(
                subkengetal,
                aantal_woningen=aantal_woningen,
            )

            aantal_staffels = math.ceil(Decimal(aantal_woningen) / subkengetal.staffel)
            investerings_kosten = subkengetal.investeringskosten * Decimal(
                aantal_staffels
            )
            expected_afschrijving = (
                investerings_kosten
                / Decimal(subkengetal.levensduur)
                / Decimal(aantal_woningen)
            )
            expected_onderhoud = (
                investerings_kosten
                * subkengetal.beheer_en_onderhoud
                / Decimal(aantal_woningen)
            )

            self.assertEqual(
                berekening.afschrijving_eur_per_woning_per_jaar,
                expected_afschrijving,
            )
            self.assertEqual(
                berekening.onderhoud_eur_per_woning_per_jaar,
                expected_onderhoud,
            )
            self.assertEqual(
                berekening.tco,
                (expected_afschrijving + expected_onderhoud) * jaren_tco,
            )
