from django.contrib import admin

from .models import Hoofdsysteem, Subsysteem


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(Hoofdsysteem)
class HoofdsysteemAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Hoofdsysteem) + ["toon_subsystemen"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related("subsystemen")

    def toon_subsystemen(self, obj):
        return ", ".join(s.naam for s in obj.subsystemen.all())

    toon_subsystemen.short_description = "Subsystemen"


@admin.register(Subsysteem)
class SubsysteemAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Subsysteem)
