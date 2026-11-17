from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


def render_value(value: str) -> str:
    return value or "(leeg)"


def format_snapshot(snapshot: dict[str, str]) -> str:
    return "\n".join(
        f"{field}: {render_value(value)}" for field, value in snapshot.items()
    )


def format_changed_snapshot(before: dict[str, str], after: dict[str, str]) -> str:
    changes: list[str] = []
    for field, new_value in after.items():
        old_value = before.get(field, "")
        if old_value == new_value:
            continue
        changes.append(
            f"{field}: {render_value(old_value)} -> {render_value(new_value)}"
        )
    return "\n".join(changes)


def create_audit_log(*, obj, action: str, changes: str, user=None) -> AuditLog:
    return AuditLog.objects.create(
        content_type=ContentType.objects.get_for_model(obj, for_concrete_model=False),
        object_id=str(obj.pk),
        object_repr=str(obj)[:255],
        action=action,
        changes=changes,
        changed_by=user if user is not None and user.is_authenticated else None,
    )
