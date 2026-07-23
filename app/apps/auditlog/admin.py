from __future__ import annotations

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from .models import AuditLog, AuditedModel


class AuditedAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if not isinstance(obj, AuditedModel):
            return super().save_model(request, obj, form, change)

        obj._audit_before_snapshot = None
        obj._audit_is_create = not change

        if change and obj.pk:
            previous = self.model.objects.get(pk=obj.pk)
            obj._audit_before_snapshot = previous.audit_snapshot()

        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj = form.instance
        if not isinstance(obj, AuditedModel):
            return

        before_snapshot = getattr(obj, "_audit_before_snapshot", None)
        is_create = getattr(obj, "_audit_is_create", False)
        after_snapshot = obj.audit_snapshot()

        if is_create:
            changes = self._format_created_snapshot(after_snapshot)
            action = AuditLog.Action.CREATED
        else:
            changes = self._format_changed_snapshot(
                before_snapshot or {}, after_snapshot
            )
            action = AuditLog.Action.UPDATED

        if not changes:
            return

        self._create_audit_log(
            request=request,
            obj=obj,
            action=action,
            changes=changes,
        )

    def delete_model(self, request, obj):
        if isinstance(obj, AuditedModel):
            self._create_audit_log(
                request=request,
                obj=obj,
                action=AuditLog.Action.DELETED,
                changes=self._format_deleted_snapshot(obj.audit_snapshot()),
            )

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        audited_objects = [obj for obj in queryset if isinstance(obj, AuditedModel)]

        for obj in audited_objects:
            self._create_audit_log(
                request=request,
                obj=obj,
                action=AuditLog.Action.DELETED,
                changes=self._format_deleted_snapshot(obj.audit_snapshot()),
            )

        super().delete_queryset(request, queryset)

    def _create_audit_log(self, *, request, obj, action: str, changes: str) -> None:
        AuditLog.objects.create(
            content_type=ContentType.objects.get_for_model(
                obj, for_concrete_model=False
            ),
            object_id=str(obj.pk),
            object_repr=str(obj),
            action=action,
            changes=changes,
            changed_by=request.user if request.user.is_authenticated else None,
        )

    def _format_created_snapshot(self, snapshot: dict[str, str]) -> str:
        return "\n".join(
            f"{field}: {self._render_value(value)}" for field, value in snapshot.items()
        )

    def _format_deleted_snapshot(self, snapshot: dict[str, str]) -> str:
        return "\n".join(
            f"{field}: {self._render_value(value)}" for field, value in snapshot.items()
        )

    def _format_changed_snapshot(
        self, before: dict[str, str], after: dict[str, str]
    ) -> str:
        changes: list[str] = []
        for field, new_value in after.items():
            old_value = before.get(field, "")
            if old_value == new_value:
                continue
            changes.append(
                f"{field}: {self._render_value(old_value)} -> {self._render_value(new_value)}"
            )
        return "\n".join(changes)

    def _render_value(self, value: str) -> str:
        return value or "(leeg)"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "changed_at",
        "changed_by",
        "content_type",
        "object_repr",
        "action",
        "changes_summary",
    )
    list_filter = ("action", "content_type", "changed_by", "changed_at")
    search_fields = ("object_repr", "changes", "changed_by__username")
    list_select_related = ("changed_by", "content_type")
    readonly_fields = (
        "changed_at",
        "changed_by",
        "content_type",
        "object_id",
        "object_repr",
        "action",
        "changes",
    )
    fields = readonly_fields

    @admin.display(description="Wijzigingen")
    def changes_summary(self, obj: AuditLog) -> str:
        first_line = obj.changes.splitlines()[0] if obj.changes else ""
        return first_line[:120]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
