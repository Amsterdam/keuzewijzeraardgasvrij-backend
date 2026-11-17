"""Export/import van kengetallen tussen omgevingen (bijv. acc -> prod).

Welke modellen meegaan staat in TRANSFER_MODELS. Records worden gematcht op
primary key; een import maakt de database voor deze modellen gelijk aan het
bestand (aanmaken, wijzigen en verwijderen).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.color import no_style
from django.core.serializers.base import DeserializationError, DeserializedObject
from django.db import IntegrityError, connection, models, transaction
from django.db.models import ProtectedError

from apps.auditlog.models import AuditedModel, AuditLog
from apps.auditlog.services import (
    create_audit_log,
    format_changed_snapshot,
    format_snapshot,
)
from apps.calculations.models import Conversie, EnergiePrijs
from apps.systemen.models import Hoofdsysteem, Subsysteem

from .models import (
    AlgemeenKengetal,
    CollectieveRuimteBinnen,
    CollectieveRuimteBuiten,
    CollectieveRuimteTuin,
    CollectieveWarmtepompKengetal,
    EliminatieKengetal,
    GelijktijdigheidCV,
    Hoofdkengetal,
    McdaHoofdcriterium,
    McdaSubcriterium,
    MultiCriteriaAnalyseKengetal,
    StadsverwarmingKengetal,
    Subkengetal,
    Warmteprogramma,
)

# Volgorde is belangrijk: modellen waar naar verwezen wordt komen eerst.
# Aanmaken/wijzigen gebeurt in deze volgorde, verwijderen in omgekeerde volgorde.
TRANSFER_MODELS: list[type[models.Model]] = [
    Subsysteem,
    Hoofdsysteem,
    Hoofdkengetal,
    Subkengetal,
    AlgemeenKengetal,
    GelijktijdigheidCV,
    CollectieveRuimteBinnen,
    CollectieveRuimteBuiten,
    CollectieveRuimteTuin,
    EliminatieKengetal,
    MultiCriteriaAnalyseKengetal,
    McdaHoofdcriterium,
    McdaSubcriterium,
    CollectieveWarmtepompKengetal,
    StadsverwarmingKengetal,
    Warmteprogramma,
    Conversie,
    EnergiePrijs,
]


class TransferError(Exception):
    pass


@dataclass
class FieldChange:
    field: str
    old: str
    new: str


@dataclass
class ObjectChange:
    pk: object
    repr: str
    changes: list[FieldChange]


@dataclass
class ModelDiff:
    label: str
    verbose_name: str
    created: list[ObjectChange] = field(default_factory=list)
    updated: list[ObjectChange] = field(default_factory=list)
    deleted: list[ObjectChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.created or self.updated or self.deleted)


@dataclass
class ImportDiff:
    models: list[ModelDiff]

    @property
    def has_changes(self) -> bool:
        return any(m.has_changes for m in self.models)

    @property
    def totals(self) -> dict[str, int]:
        return {
            "created": sum(len(m.created) for m in self.models),
            "updated": sum(len(m.updated) for m in self.models),
            "deleted": sum(len(m.deleted) for m in self.models),
        }

    @property
    def fingerprint(self) -> str:
        raw = json.dumps([asdict(m) for m in self.models], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


# --------------------------------------------------------------------------- export


def export_json() -> str:
    objects = []
    for model in TRANSFER_MODELS:
        objects.extend(model._default_manager.order_by("pk"))
    return serializers.serialize("json", objects, indent=2)


# --------------------------------------------------------------------------- parse


def parse(payload: str) -> list[DeserializedObject]:
    try:
        objects = list(serializers.deserialize("json", payload))
    except DeserializationError as exc:
        raise TransferError(f"Ongeldig importbestand: {exc}") from exc

    allowed = set(TRANSFER_MODELS)
    seen: set[tuple[type[models.Model], object]] = set()
    for item in objects:
        model = type(item.object)
        if model not in allowed:
            raise TransferError(
                f"Model {model._meta.label} hoort niet bij de kengetallen-export."
            )
        key = (model, item.object.pk)
        if item.object.pk is None or key in seen:
            raise TransferError(
                f"Ontbrekende of dubbele pk voor {model._meta.label}: {item.object.pk}"
            )
        seen.add(key)

    _check_references(objects, seen)
    return objects


def _check_references(
    objects: list[DeserializedObject],
    present: set[tuple[type[models.Model], object]],
) -> None:
    """Elke verwijzing moet naar een record in het bestand wijzen (of, voor
    modellen buiten de export, naar een bestaand record in de database)."""
    allowed = set(TRANSFER_MODELS)

    def exists(model: type[models.Model], pk: object) -> bool:
        if model in allowed:
            return (model, pk) in present
        return model._default_manager.filter(pk=pk).exists()

    for item in objects:
        obj = item.object
        refs = [
            (f, getattr(obj, f.attname))
            for f in obj._meta.concrete_fields
            if f.is_relation and getattr(obj, f.attname) is not None
        ]
        for f in obj._meta.many_to_many:
            refs.extend((f, pk) for pk in (item.m2m_data or {}).get(f.name, []))
        for f, pk in refs:
            if not exists(f.related_model, pk):
                raise TransferError(
                    f"{obj._meta.verbose_name} #{obj.pk} verwijst naar "
                    f"{f.related_model._meta.verbose_name} #{pk}, "
                    "maar die staat niet in het bestand."
                )


# --------------------------------------------------------------------------- diff


def _safe_str(obj: models.Model) -> str:
    try:
        return str(obj)
    except ObjectDoesNotExist:
        return f"{obj._meta.verbose_name} #{obj.pk}"


class _Formatter:
    """Maakt leesbare waarden van velden, inclusief namen bij relaties."""

    def __init__(self, incoming: list[DeserializedObject]):
        self._incoming = {(type(i.object), i.object.pk): i.object for i in incoming}
        self._cache: dict[tuple[type[models.Model], object], str] = {}

    def related(self, model: type[models.Model], pk: object) -> str:
        if pk is None:
            return ""
        key = (model, pk)
        if key not in self._cache:
            obj = (
                self._incoming.get(key) or model._default_manager.filter(pk=pk).first()
            )
            label = _safe_str(obj) if obj is not None else "?"
            self._cache[key] = f"{label} (#{pk})"
        return self._cache[key]

    def values(
        self, obj: models.Model, m2m: dict[str, list] | None = None
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for f in obj._meta.concrete_fields:
            if f.primary_key:
                continue
            raw = getattr(obj, f.attname)
            if f.is_relation:
                out[str(f.verbose_name)] = self.related(f.related_model, raw)
            else:
                out[str(f.verbose_name)] = AuditedModel._format_audit_value(raw)
        for f in obj._meta.many_to_many:
            if m2m is not None:
                pks = m2m.get(f.name, [])
            else:
                pks = list(getattr(obj, f.name).values_list("pk", flat=True))
            labels = sorted(self.related(f.related_model, pk) for pk in pks)
            out[str(f.verbose_name)] = ", ".join(labels)
        return out


def _changes(before: dict[str, str], after: dict[str, str]) -> list[FieldChange]:
    return [
        FieldChange(name, before.get(name, ""), value)
        for name, value in after.items()
        if before.get(name, "") != value
    ]


def build_diff(incoming: list[DeserializedObject]) -> ImportDiff:
    fmt = _Formatter(incoming)
    by_model: dict[type[models.Model], list[DeserializedObject]] = {}
    for item in incoming:
        by_model.setdefault(type(item.object), []).append(item)

    diffs: list[ModelDiff] = []
    for model in TRANSFER_MODELS:
        md = ModelDiff(
            label=model._meta.label,
            verbose_name=str(model._meta.verbose_name_plural),
        )
        existing = {
            obj.pk: obj
            for obj in model._default_manager.prefetch_related(
                *[f.name for f in model._meta.many_to_many]
            )
        }
        items = sorted(by_model.get(model, []), key=lambda i: i.object.pk)
        incoming_pks = set()
        for item in items:
            obj = item.object
            incoming_pks.add(obj.pk)
            new_values = fmt.values(obj, item.m2m_data or {})
            current = existing.get(obj.pk)
            if current is None:
                md.created.append(
                    ObjectChange(obj.pk, _safe_str(obj), _changes({}, new_values))
                )
                continue
            changes = _changes(fmt.values(current), new_values)
            if changes:
                md.updated.append(ObjectChange(obj.pk, _safe_str(current), changes))

        for pk in sorted(set(existing) - incoming_pks):
            current = existing[pk]
            old_values = fmt.values(current)
            md.deleted.append(
                ObjectChange(
                    pk,
                    _safe_str(current),
                    [FieldChange(k, v, "") for k, v in old_values.items()],
                )
            )
        diffs.append(md)
    return ImportDiff(diffs)


# --------------------------------------------------------------------------- apply


def _reset_sequences() -> None:
    statements = connection.ops.sequence_reset_sql(no_style(), TRANSFER_MODELS)
    if not statements:
        return
    with connection.cursor() as cursor:
        for sql in statements:
            cursor.execute(sql)


def apply_import(payload: str, *, user=None, expected_fingerprint: str | None = None):
    """Voert de import door. Alles of niets."""
    try:
        return _apply(payload, user=user, expected_fingerprint=expected_fingerprint)
    except ProtectedError as exc:
        blocking = ", ".join(sorted({_safe_str(o) for o in exc.protected_objects})[:10])
        raise TransferError(
            f"Verwijderen niet mogelijk, er wordt nog naar verwezen door: {blocking}"
        ) from exc
    except IntegrityError as exc:
        raise TransferError(f"Import geweigerd door de database: {exc}") from exc


def _apply(payload: str, *, user, expected_fingerprint: str | None) -> ImportDiff:
    with transaction.atomic():
        incoming = parse(payload)
        diff = build_diff(incoming)
        if expected_fingerprint and diff.fingerprint != expected_fingerprint:
            raise TransferError(
                "De database of het bestand is gewijzigd sinds de vergelijking. "
                "Vergelijk opnieuw."
            )

        incoming_by_model: dict[type[models.Model], list[DeserializedObject]] = {}
        for item in incoming:
            incoming_by_model.setdefault(type(item.object), []).append(item)

        for model in TRANSFER_MODELS:
            existing = model._default_manager.in_bulk()
            for item in incoming_by_model.get(model, []):
                obj = item.object
                current = existing.get(obj.pk)
                before = current.audit_snapshot() if current is not None else None
                item.save()
                saved = model._default_manager.get(pk=obj.pk)
                after = saved.audit_snapshot()
                if before is None:
                    create_audit_log(
                        obj=saved,
                        action=AuditLog.Action.CREATED,
                        changes=format_snapshot(after),
                        user=user,
                    )
                elif before != after:
                    create_audit_log(
                        obj=saved,
                        action=AuditLog.Action.UPDATED,
                        changes=format_changed_snapshot(before, after),
                        user=user,
                    )

        for model in reversed(TRANSFER_MODELS):
            keep = {i.object.pk for i in incoming_by_model.get(model, [])}
            for obj in model._default_manager.exclude(pk__in=keep):
                create_audit_log(
                    obj=obj,
                    action=AuditLog.Action.DELETED,
                    changes=format_snapshot(obj.audit_snapshot()),
                    user=user,
                )
                obj.delete()

        # Controleer uitgestelde FK-constraints nu, zodat fouten hier al optreden
        # (en netjes worden gemeld) in plaats van pas bij de commit.
        connection.check_constraints()
        _reset_sequences()
    return diff
