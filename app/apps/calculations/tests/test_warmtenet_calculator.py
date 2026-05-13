from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.calculations.calculator import WarmtenetCalculator
from apps.calculations.models import GebruikersInvoer


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
        "dubbel_glas": False,
        "wtw_aanwezig": False,
        "buurtcode": None,
        "jaar_vervangen": None,
    }
    defaults.update(overrides)
    return GebruikersInvoer.objects.create(**defaults)


class WarmtenetCalculatorTest(TestCase):
    fixtures = ["fixtures"]

    def test_returns_defaults_without_buurtcode(self):
        calc_input = _calculation_input(buurtcode=None)
        result = WarmtenetCalculator().calculate(calc_input)

        self.assertEqual(result.categorie, "")
        self.assertIsNone(result.warmtenet_start)
        self.assertIsNone(result.warmtenet_stop)
        self.assertFalse(result.warmtenet_mogelijk)

    def test_warmtenet_mogelijk_true_if_jaar_vervangen_ge_stop(self):
        calc_input = _calculation_input(buurtcode="BU03636910", jaar_vervangen=2040)
        result = WarmtenetCalculator().calculate(calc_input)

        self.assertEqual(
            result.categorie,
            "Warmtenetbuurt: gefaseerd starten vanaf 2030",
        )
        self.assertEqual(result.warmtenet_start, 2030)
        self.assertEqual(result.warmtenet_stop, 2040)
        self.assertTrue(result.warmtenet_mogelijk)

    def test_warmtenet_mogelijk_false_if_jaar_vervangen_lt_stop(self):
        calc_input = _calculation_input(buurtcode="BU03636910", jaar_vervangen=2039)
        result = WarmtenetCalculator().calculate(calc_input)

        self.assertEqual(result.warmtenet_stop, 2040)
        self.assertFalse(result.warmtenet_mogelijk)
