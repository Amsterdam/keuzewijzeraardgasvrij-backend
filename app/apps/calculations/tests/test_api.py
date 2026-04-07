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
        "bruto_vloeroppervlak": 1234.5,
        "aantal_woningen": 10,
        "mechanische_ventilatie_aanwezig": True,
        "vloerverwarming_aanwezig": False,
        "inpandige_berging_aanwezig": True,
        "ruimte_op_het_dak_aanwezig": True,
        "type_dak": "plat_dak",
        "tapwater_op_gas": True,
        "gasverbruik_per_woning": 500.0,
        "gasverbruik_vve_totaal": 5000.0,
        "elektriciteitsverbruik_per_woning": 1000.0,
        "elektriciteitsverbruik_vve_totaal": 10000.0,
        "gecontracteerd_vermogen": 50.0,
        "huidige_warmtesysteem": "cv_ketel",
        "volledig_gasloos": False,
        "wens_tot_koelen": False,
    }


class CalculationInputCreateApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("calculationinput-create")

    def test_post_creates_calculation_input(self):
        response = self.client.post(self.url, data=_valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(GebruikersInvoer.objects.count(), 1)

        created = GebruikersInvoer.objects.get()
        self.assertEqual(created.bouwjaar, 1990)
        self.assertEqual(created.type_dak, "plat_dak")

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

    def test_invalid_choice_returns_400(self):
        payload = _valid_payload()
        payload["type_dak"] = "geen_dak"
        response = self.client.post(self.url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("type_dak", response.data)

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
        payload["gasverbruik_per_woning"] = math.inf
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("gasverbruik_per_woning", serializer.errors)

        payload = _valid_payload()
        payload["elektriciteitsverbruik_vve_totaal"] = math.nan
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("elektriciteitsverbruik_vve_totaal", serializer.errors)

    def test_rejects_invalid_choices(self):
        payload = _valid_payload()
        payload["type_dak"] = "geen_dak"
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("type_dak", serializer.errors)

        payload = _valid_payload()
        payload["huidige_warmtesysteem"] = "onbekend"
        serializer = GebruikersInvoerCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("huidige_warmtesysteem", serializer.errors)
