from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.auditlog.models import AuditLog
from apps.calculations.models import Conversie, EnergiePrijs
from apps.kengetallen.models import (
    BuurtcodeWarmteprogramma,
    Hoofdkengetal,
    ScenarioKeuze,
    Warmteprogramma,
)
from apps.kengetallen.transfer import (
    TransferError,
    apply_import,
    build_diff,
    export_json,
    parse,
)
from apps.systemen.models import Hoofdsysteem, Subsysteem


def _diff(payload: str):
    return build_diff(parse(payload))


def _model_diff(diff, label: str):
    return next(m for m in diff.models if m.label == label)


class TransferTestCase(TestCase):
    def setUp(self):
        self.sub = Subsysteem.objects.create(naam="Bodemlus")
        self.hoofd = Hoofdsysteem.objects.create(naam="Bodem-WP")
        self.hoofd.subsystemen.add(self.sub)
        self.kengetal = Hoofdkengetal.objects.create(
            hoofdsysteem=self.hoofd,
            scenario=ScenarioKeuze.MIDDEN,
            cop_tap=Decimal("2.5"),
            cop_cv=Decimal("4"),
            cop_gkw=Decimal("3"),
        )
        self.programma = Warmteprogramma.objects.create(categorie="A")
        self.programma.hoofdsystemen.add(self.hoofd)
        # Migraties zetten al standaardwaarden; voor de test beginnen we leeg.
        Conversie.objects.all().delete()
        EnergiePrijs.objects.all().delete()
        Conversie.objects.create(naam="kwh_naar_gj", waarde=Decimal("0.0036"))
        EnergiePrijs.objects.create(naam="gas", prijs_eur_per_gj=Decimal("40"))


class ExportImportTests(TransferTestCase):
    def test_roundtrip_has_no_changes(self):
        diff = _diff(export_json())
        self.assertFalse(diff.has_changes)

    def test_export_excludes_buurtcodes(self):
        BuurtcodeWarmteprogramma.objects.create(
            buurtcode="A00a", warmteprogramma=self.programma
        )
        models = {o["model"] for o in json.loads(export_json())}
        self.assertNotIn("kengetallen.buurtcodewarmteprogramma", models)
        self.assertIn("systemen.hoofdsysteem", models)
        self.assertIn("calculation_inputs.energieprijs", models)

    def test_updated_field_is_shown_and_applied(self):
        payload = export_json()
        Hoofdkengetal.objects.filter(pk=self.kengetal.pk).update(cop_tap=Decimal("9"))

        diff = _diff(payload)
        md = _model_diff(diff, "kengetallen.Hoofdkengetal")
        self.assertEqual(len(md.updated), 1)
        [change] = md.updated[0].changes
        self.assertEqual(change.field, "cop tap")
        self.assertEqual((change.old, change.new), ("9.000000000", "2.500000000"))

        apply_import(payload)
        self.kengetal.refresh_from_db()
        self.assertEqual(self.kengetal.cop_tap, Decimal("2.5"))
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATED, object_id=str(self.kengetal.pk)
            ).exists()
        )
        self.assertFalse(_diff(payload).has_changes)

    def test_created_and_deleted_are_applied(self):
        payload = export_json()
        # In de doelomgeving bestaat een extra record en ontbreekt er één.
        extra = Conversie.objects.create(naam="extra", waarde=Decimal("1"))
        Conversie.objects.filter(naam="kwh_naar_gj").delete()

        md = _model_diff(_diff(payload), "calculation_inputs.Conversie")
        self.assertEqual([o.pk for o in md.deleted], [extra.pk])
        self.assertEqual(len(md.created), 1)

        apply_import(payload)
        self.assertEqual(
            list(Conversie.objects.values_list("naam", flat=True)), ["kwh_naar_gj"]
        )
        # Sequence is bijgewerkt: nieuwe records botsen niet met geïmporteerde IDs.
        Conversie.objects.create(naam="na_import", waarde=Decimal("2"))

    def test_m2m_changes(self):
        payload = export_json()
        self.hoofd.subsystemen.clear()

        md = _model_diff(_diff(payload), "systemen.Hoofdsysteem")
        self.assertEqual(len(md.updated), 1)
        self.assertEqual(md.updated[0].changes[0].field, "subsystemen")

        apply_import(payload)
        self.assertEqual(list(self.hoofd.subsystemen.all()), [self.sub])

    def test_unknown_model_is_rejected(self):
        data = json.loads(export_json())
        data.append(
            {
                "model": "kengetallen.buurtcodewarmteprogramma",
                "pk": 1,
                "fields": {"buurtcode": "X", "warmteprogramma": self.programma.pk},
            }
        )
        with self.assertRaises(TransferError):
            parse(json.dumps(data))

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(TransferError):
            parse("geen json")

    def test_failure_rolls_back_everything(self):
        data = [
            o
            for o in json.loads(export_json())
            if o["model"] != "kengetallen.warmteprogramma"
        ]
        for o in data:
            if o["model"] == "calculation_inputs.conversie":
                o["fields"]["waarde"] = "99"
        # Buurtcode beschermt het warmteprogramma tegen verwijderen.
        BuurtcodeWarmteprogramma.objects.create(
            buurtcode="A00a", warmteprogramma=self.programma
        )

        with self.assertRaises(TransferError):
            apply_import(json.dumps(data))

        self.assertEqual(Conversie.objects.get().waarde, Decimal("0.0036"))
        self.assertTrue(Warmteprogramma.objects.exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_stale_fingerprint_is_rejected(self):
        payload = export_json()
        fingerprint = _diff(payload).fingerprint
        Conversie.objects.update(waarde=Decimal("5"))

        with self.assertRaises(TransferError):
            apply_import(payload, expected_fingerprint=fingerprint)


class TransferAdminTests(TransferTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("admin:kengetallen_kengetallentransfer_changelist")
        self.admin = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "pw"
        )

    def test_staff_without_superuser_is_denied(self):
        staff = get_user_model().objects.create_user("staff", password="pw")
        staff.is_staff = True
        staff.save()
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_export_download(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"export": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(json.loads(response.content))

    def test_compare_then_apply(self):
        self.client.force_login(self.admin)
        payload = export_json()
        Conversie.objects.update(waarde=Decimal("5"))

        response = self.client.post(
            self.url,
            {
                "action": "compare",
                "file": SimpleUploadedFile("export.json", payload.encode()),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wijzigingen doorvoeren")
        diff = response.context["diff"]

        response = self.client.post(
            self.url,
            {
                "action": "apply",
                "payload": payload,
                "fingerprint": diff.fingerprint,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversie.objects.get().waarde, Decimal("0.0036"))
        log = AuditLog.objects.get(action=AuditLog.Action.UPDATED)
        self.assertEqual(log.changed_by, self.admin)


class ReferenceTests(TransferTestCase):
    def test_missing_reference_is_rejected(self):
        data = json.loads(export_json())
        for o in data:
            if o["model"] == "kengetallen.hoofdkengetal":
                o["fields"]["hoofdsysteem"] = 999999
        with self.assertRaisesMessage(TransferError, "verwijst naar"):
            parse(json.dumps(data))

    def test_missing_m2m_reference_is_rejected(self):
        data = [
            o for o in json.loads(export_json()) if o["model"] != "systemen.subsysteem"
        ]
        with self.assertRaisesMessage(TransferError, "verwijst naar"):
            parse(json.dumps(data))
