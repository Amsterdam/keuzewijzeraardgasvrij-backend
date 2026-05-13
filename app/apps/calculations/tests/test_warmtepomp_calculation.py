from __future__ import annotations

import math
from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import EnergieCalculator, EnergieType
from apps.calculations.models import Conversie, GebruikersInvoer
from apps.calculations.subsysteem_calculations import calculate_warmtepomp
from apps.kengetallen.models import (
    CollectieveWarmtepompKengetal,
    ScenarioKeuze,
    Subkengetal,
)


class WarmtepompCalculationTest(TestCase):
    fixtures = ["fixtures"]

    def test_calculate_warmtepomp_lt_wp_output_afschrijving_onderhoud(self):
        """Single fixture-based test verifying warmtepomp output fields."""

        scenario = ScenarioKeuze.LAAG
        scenario_key = str(scenario)

        # Fixture: Collectieve LT-WP is subsysteem pk=24 and has Subkengetal for all scenarios.
        subkengetal = Subkengetal.objects.get(subsysteem_id=24, scenario=scenario_key)
        jaren_tco = Conversie.objects.get(naam="jaren_tco").waarde

        calc_input = GebruikersInvoer.objects.create(
            bouwjaar=1990,
            bruto_vloeroppervlak=Decimal("1234.5"),
            aantal_woningen=200,
            mechanische_ventilatie_aanwezig=True,
            vloerverwarming_aanwezig=False,
            tapwater_op_gas=True,
            koken_op_gas=False,
            gasverbruik_vve_totaal=Decimal("1334.6"),
            wens_tot_koelen=False,
        )

        energie = EnergieCalculator().calculate(calc_input)
        tap = energie.by_scenario[scenario_key][EnergieType.TAP]
        cv = energie.by_scenario[scenario_key][EnergieType.CV]

        berekening = calculate_warmtepomp(
            "Collectieve LT-WP",
            subkengetal=subkengetal,
            tap_energie_calculation=tap,
            cv_energie_calculation=cv,
            aantal_woningen=calc_input.aantal_woningen,
        )

        waarden = {
            k.naam: k.waarde
            for k in CollectieveWarmtepompKengetal.objects.filter(
                naam__in=(
                    "COEF_LT",
                    "EXP_LT",
                    "P_MAX_LT",
                )
            )
        }

        p_max = waarden["P_MAX_LT"]
        coef = waarden["COEF_LT"]
        exp = waarden["EXP_LT"]

        benodigd_vermogen = cv.vermogen_warmte_kw_per_vve
        aantal_warmtepompen = math.ceil(benodigd_vermogen / p_max)
        vermogen_per_warmtepomp = benodigd_vermogen / Decimal(aantal_warmtepompen)
        formule = coef * (vermogen_per_warmtepomp**exp) * benodigd_vermogen

        expected_afschrijving = (
            formule
            / Decimal(subkengetal.levensduur)
            / Decimal(calc_input.aantal_woningen)
        )
        expected_onderhoud = (
            formule
            * subkengetal.beheer_en_onderhoud
            / Decimal(calc_input.aantal_woningen)
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
