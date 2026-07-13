import math
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.calculations.calculator import RedenenScoreMessages
from apps.calculations.models import GebruikersInvoer
from apps.calculations.pdok_client import PandData
from apps.calculations.serializers import GebruikersInvoerCreateSerializer
from apps.kengetallen.models import (
    BuurtcodeWarmteprogramma,
    GasverbruikGegeven,
    Warmteprogramma,
)
from apps.systemen.models import Hoofdsysteem


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

    @classmethod
    def setUpTestData(cls) -> None:
        warmteprogramma, _ = Warmteprogramma.objects.get_or_create(
            categorie="Aardgasvrij gasnet: gestaag 70% gasbesparing tot 2040",
            defaults={
                "warmtenet_start": 9999,
                "warmtenet_stop": 9999,
            },
        )
        BuurtcodeWarmteprogramma.objects.update_or_create(
            buurtcode="BU03636501",
            defaults={"warmteprogramma": warmteprogramma},
        )

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
                    "beschrijving_url",
                    "beschrijving_url_title",
                    "warmteprogramma_tekst",
                    "omgevingsvergunning",
                    "tco",
                    "score",
                    "is_mogelijk",
                    "kosten_per_woning_per_jaar",
                    "kosten_per_woning_per_jaar_laag",
                    "kosten_per_woning_per_jaar_hoog",
                    "redenen_niet_mogelijk",
                    "redenen_score",
                ]
            ),
        )

        redenen_score = first.get("redenen_score")
        self.assertIsInstance(redenen_score, list)
        self.assertEqual(len(redenen_score), 4)
        self.assertTrue(all(isinstance(x, str) for x in redenen_score))
        self.assertIn(redenen_score[0], RedenenScoreMessages.TCO_ALL)
        self.assertIn(redenen_score[1], RedenenScoreMessages.ELEKTRISCH_ALL)
        self.assertIn(redenen_score[2], RedenenScoreMessages.RUIMTE_ALL)
        self.assertIn(redenen_score[3], RedenenScoreMessages.AANPASSING_ALL)

        # Validate TCO message buckets exactly (top 3/next 4/rest) based on returned TCOs.
        tco_by_naam = {
            str(r["naam"]): Decimal(str(r.get("tco", 0))) for r in response.data
        }
        ordered_namen = sorted(tco_by_naam.keys(), key=lambda n: (tco_by_naam[n], n))
        expected_tco_msg_by_naam: dict[str, str] = {}
        for idx, naam in enumerate(ordered_namen):
            if idx < 3:
                expected_tco_msg_by_naam[naam] = RedenenScoreMessages.TCO_BEST
            elif idx < 7:
                expected_tco_msg_by_naam[naam] = RedenenScoreMessages.TCO_AVERAGE
            else:
                expected_tco_msg_by_naam[naam] = RedenenScoreMessages.TCO_WORST

        for r in response.data:
            naam = str(r["naam"])
            redenen_score_any = r.get("redenen_score")
            self.assertIsInstance(redenen_score_any, list)
            self.assertEqual(len(redenen_score_any), 4)
            self.assertEqual(redenen_score_any[0], expected_tco_msg_by_naam[naam])

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

    def test_post_includes_warmteprogramma_text_based_on_matching_hoofdsysteem(self):
        warmteprogramma, _ = Warmteprogramma.objects.get_or_create(
            categorie="Lokale bronnetten en warmtenet: gestaag aardgasvrij tussen 2020 en 2032",
            defaults={
                "warmtenet_start": 2020,
                "warmtenet_stop": 2032,
            },
        )
        warmteprogramma.hoofdsystemen.set(
            Hoofdsysteem.objects.filter(
                naam__in=[
                    "Particulier Externe warmtelevering",
                    "Particulier Externe warmtelevering + externe koeling",
                    "Zakelijk Collectief Externe warmtelevering",
                    "Zakelijk Collectief Externe warmtelevering + externe koeling",
                    "Collectief Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                    "Collectief Open Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                ]
            )
        )
        BuurtcodeWarmteprogramma.objects.update_or_create(
            buurtcode="TESTWP001",
            defaults={"warmteprogramma": warmteprogramma},
        )

        payload = _valid_payload()
        payload["buurtcode"] = "TESTWP001"

        response = self.client.post(self.url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        by_name = {row["naam"]: row for row in response.data}
        self.assertEqual(
            by_name[
                "Collectief Open Bodem Energie Systeem met Individuele Bodemwarmtepomp"
            ]["warmteprogramma_tekst"],
            "Volgens de Transitievisie Warmte valt uw buurt binnen de categorie "
            "Lokale bronnetten en warmtenet: gestaag aardgasvrij tussen 2020 en 2032. "
            "Een collectief open bodem energie systeem met individuele bodemwarmtepomp sluit hierbij aan. "
            "Wat dit precies betekent, is op dit moment nog niet duidelijk. "
            "Mogelijk wordt er nu of in de toekomst ondersteuning of subsidie geboden voor technieken die binnen deze categorie vallen.",
        )
        self.assertEqual(
            by_name["Individuele Luchtwarmtepomp op Buitenlucht"][
                "warmteprogramma_tekst"
            ],
            "Volgens de Transitievisie Warmte valt uw buurt binnen de categorie "
            "Lokale bronnetten en warmtenet: gestaag aardgasvrij tussen 2020 en 2032. "
            "Een individuele luchtwarmtepomp op buitenlucht past niet binnen deze categorie. "
            "Het is op dit moment nog niet duidelijk welke gevolgen dit heeft. "
            "Het is mogelijk dat huidige of toekomstige ondersteuning zich richt op technieken die wel binnen deze categorie vallen.",
        )

    def test_post_returns_correct_scores(self):
        expected = [
            (
                "Collectief Open Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                7.0,
            ),
            ("Collectieve Luchtwarmtepomp op Buitenlucht", 6.0),
            ("Individuele Luchtwarmtepomp op Buitenlucht", 1.0),
            ("Zakelijk Collectief Externe warmtelevering", 9.0),
            (
                "Collectief Gesloten Bodem Energie Systeem met collectieve Bodemwarmtepomp",
                9.0,
            ),
            (
                "Collectief Open Bodem Energie Systeem met Centrale Bodemwarmtepomp",
                8.0,
            ),
            ("Particulier Externe warmtelevering", 7.0),
            (
                "Collectief Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                7.0,
            ),
            ("Zakelijk Collectief Externe warmtelevering + externe koeling", 6.0),
            ("Particulier Externe warmtelevering + externe koeling", 6.0),
            (
                "Individuele Gesloten Bodem Energie Systeem met Individuele Bodemwarmtepomp",
                6.0,
            ),
            ("Individuele Luchtwarmtepomp op Ventilatie", 2.0),
        ]

        response = self.client.post(self.url, data=_valid_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), len(expected))

        for actual, (expected_naam, expected_score) in zip(
            response.data, expected, strict=True
        ):
            self.assertEqual(actual.get("naam"), expected_naam)
            self.assertEqual(float(actual.get("score")), expected_score)

    def test_get_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch("apps.calculations.views.DsoClient.get_bruto_vloeroppervlak")
    @patch("apps.calculations.views.PdokClient.get_pand_info")
    def test_retrieve_returns_bag_info(
        self,
        mock_get_pand_info,
        mock_get_bruto_vloeroppervlak,
    ):
        bag_id = "0363010000828496"
        detail_url = reverse("calculationinput-prefill", args=[bag_id])
        GasverbruikGegeven.objects.create(
            postcode_start="1234AA",
            postcode_eind="1234ZZ",
            gemiddeld_verbruik=Decimal("100"),
        )
        mock_get_pand_info.return_value = PandData(
            aantal_woningen=24,
            bouwjaar=1983,
            identificatie="0363100012130718",
            postcode="1234AB",
        )
        mock_get_bruto_vloeroppervlak.return_value = 106

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            response.data,
            {
                "bruto_vloeroppervlak": 117,
                "aantal_woningen": 24,
                "bouwjaar": 1983,
                "gasverbruik_vve_totaal": 2400,
            },
        )
        mock_get_pand_info.assert_called_once_with(bag_id=bag_id)
        mock_get_bruto_vloeroppervlak.assert_called_once_with("0363100012130718")

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
