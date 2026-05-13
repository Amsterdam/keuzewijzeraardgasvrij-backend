import math

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.calculations.models import GebruikersInvoer
from apps.calculations.serializers import GebruikersInvoerCreateSerializer


def _valid_payload():
    return {
        "bouwjaar": 1990,
        "bruto_vloeroppervlak": 15000,
        "aantal_woningen": 200,
        "mechanische_ventilatie_aanwezig": False,
        "vloerverwarming_aanwezig": False,
        "tapwater_op_gas": True,
        "gasverbruik_vve_totaal": 268920,
        "elektriciteitsverbruik_per_woning": 10,
        "elektriciteitsverbruik_vve_totaal": 10,
        "wens_tot_koelen": False,
        "koken_op_gas": True,
        "huidig_systeem": "collectief",
        "dubbel_glas": False,
        "buurtcode": "BU03636501",
        "beschikbare_ruimte_in_woning_m2": 1,
        "beschikbare_collectieve_ruimte_binnen_m2": 20,
        "beschikbare_collectieve_ruimte_buiten_m2": 100,
        "jaar_vervangen": 2040,
        "wtw_aanwezig": True,
    }


class CalculationInputCreateApiTest(TestCase):
    fixtures = ["fixtures"]

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("calculationinput-list")

    def test_post_creates_calculation_input(self):
        response = self.client.post(self.url, data=_valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(GebruikersInvoer.objects.count(), 1)

        self.assertIsInstance(response.data, list)
        self.assertGreater(len(response.data), 0)
        first = response.data[0]
        self.assertEqual(
            sorted(first.keys()),
            sorted(
                [
                    "naam",
                    "beschrijving",
                    "tco",
                    "score",
                    "is_mogelijk",
                    "redenen",
                    "kosten_per_woning_per_jaar",
                ]
            ),
        )

        # Ordering: is_mogelijk=true first, then is_mogelijk=false; within each group sort by score high→low.
        is_mogelijk_flags = [bool(r.get("is_mogelijk")) for r in response.data]
        if False in is_mogelijk_flags:
            first_false_idx = is_mogelijk_flags.index(False)
            self.assertTrue(all(is_mogelijk_flags[:first_false_idx]))
            self.assertTrue(all(not x for x in is_mogelijk_flags[first_false_idx:]))

        def _assert_non_increasing(values: list[float]) -> None:
            self.assertEqual(values, sorted(values, reverse=True))

        scores_true = [float(r["score"]) for r in response.data if r["is_mogelijk"]]
        scores_false = [
            float(r["score"]) for r in response.data if not r["is_mogelijk"]
        ]
        _assert_non_increasing(scores_true)
        _assert_non_increasing(scores_false)

        created = GebruikersInvoer.objects.get()
        self.assertEqual(created.bouwjaar, 1990)

    def test_post_returns_correct_scores(self):
        expected = [
            ("Zakelijk Collectief Externe warmtelevering", 9.0, True),
            (
                "Collectief Open Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                7.0,
                True,
            ),
            ("Particulier Externe warmtelevering", 7.0, True),
            (
                "Zakelijk Collectief Externe warmtelevering + externe koeling",
                6.0,
                True,
            ),
            ("Particulier Externe warmtelevering + externe koeling", 6.0, True),
            ("Collectieve Luchtwarmtepomp op Buitenlucht", 6.0, True),
            ("Individuele Luchtwarmtepomp op Buitenlucht", 1.0, True),
            (
                "Collectief Gesloten Bodem Energie Systeem met collectieve Bodemwarmtepomp",
                9.0,
                False,
            ),
            (
                "Collectief Open Bodem Energie Systeem met Centrale Bodemwarmtepomp",
                8.0,
                False,
            ),
            (
                "Collectief Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                7.0,
                False,
            ),
            (
                "Individuele Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                6.0,
                False,
            ),
            ("Individuele Luchtwarmtepomp op Ventilatie", 2.0, False),
        ]

        response = self.client.post(self.url, data=_valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), len(expected))

        for actual, (expected_naam, expected_score, expected_is_mogelijk) in zip(
            response.data, expected, strict=True
        ):
            self.assertEqual(actual.get("naam"), expected_naam)
            self.assertEqual(float(actual.get("score")), expected_score)
            self.assertEqual(bool(actual.get("is_mogelijk")), expected_is_mogelijk)

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_invalid_bouwjaar_returns_400(self):
        payload = _valid_payload()
        payload["bouwjaar"] = 2027
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("bouwjaar", response.data)

        payload["bouwjaar"] = 0
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("bouwjaar", response.data)

    def test_throttling(self):
        for _ in range(20):
            response = self.client.post(self.url, data=_valid_payload(), format="json")
            self.assertIn(
                response.status_code,
                (status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS),
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class GebruikersInvoerCreateSerializerTest(TestCase):
    def test_valid_payload_is_valid(self):
        serializer = GebruikersInvoerCreateSerializer(data=_valid_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_bruto_vloeroppervlak_zero(self):
        payload = _valid_payload()
        payload["bruto_vloeroppervlak"] = 0
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("bruto_vloeroppervlak", serializer.errors)

    def test_rejects_non_finite_numbers(self):
        payload = _valid_payload()
        payload["beschikbare_collectieve_ruimte_binnen_m2"] = math.nan
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("beschikbare_collectieve_ruimte_binnen_m2", serializer.errors)
