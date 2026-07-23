from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditedModel(models.Model):
    audit_excluded_fields: set[str] = set()

    class Meta:
        abstract = True

    def audit_snapshot(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}

        for field in self._meta.concrete_fields:
            if field.primary_key or field.name in self.audit_excluded_fields:
                continue

            if field.is_relation:
                related_value = getattr(self, field.name)
                snapshot[str(field.verbose_name)] = self._format_audit_value(
                    related_value
                )
                continue

            snapshot[str(field.verbose_name)] = self._format_audit_value(
                getattr(self, field.name)
            )

        for field in self._meta.many_to_many:
            if field.name in self.audit_excluded_fields or self.pk is None:
                continue

            values = sorted(str(value) for value in getattr(self, field.name).all())
            snapshot[str(field.verbose_name)] = ", ".join(values)

        return snapshot

    @staticmethod
    def _format_audit_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Ja" if value else "Nee"
        if isinstance(value, Decimal):
            return format(value, "f")
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Aangemaakt"
        UPDATED = "updated", "Gewijzigd"
        DELETED = "deleted", "Verwijderd"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=Action.choices)
    changes = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name = "Auditlog"
        verbose_name_plural = "Auditlog"

    def __str__(self) -> str:
        return f"{self.get_action_display()} {self.content_type} {self.object_repr}"
