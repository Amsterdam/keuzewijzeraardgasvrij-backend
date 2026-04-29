from django.contrib import admin

from .models import (
    AlgemeenKengetal,
    BuurtcodeWarmteprogramma,
    CollectieveRuimteBinnen,
    CollectieveRuimteBuiten,
    CollectieveWarmtepompKengetal,
    EliminatieKengetal,
    GelijktijdigheidCV,
    Hoofdkengetal,
    StadsverwarmingKengetal,
    Subkengetal,
    Warmteprogramma,
)


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(Hoofdkengetal)
class HoofdkengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Hoofdkengetal)
    list_select_related = True


@admin.register(Subkengetal)
class SubkengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Subkengetal)
    list_select_related = True


@admin.register(AlgemeenKengetal)
class AlgemeenKengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(AlgemeenKengetal)


@admin.register(GelijktijdigheidCV)
class GelijktijdigheidCVAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(GelijktijdigheidCV)


@admin.register(CollectieveWarmtepompKengetal)
class CollectieveWarmtepompKengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CollectieveWarmtepompKengetal)


@admin.register(CollectieveRuimteBinnen)
class CollectieveRuimteBinnenAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CollectieveRuimteBinnen)
    list_select_related = True


@admin.register(CollectieveRuimteBuiten)
class CollectieveRuimteBuitenAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CollectieveRuimteBuiten)
    list_select_related = True


@admin.register(EliminatieKengetal)
class EliminatieKengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(EliminatieKengetal)


@admin.register(Warmteprogramma)
class WarmteprogrammaAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Warmteprogramma)


@admin.register(BuurtcodeWarmteprogramma)
class BuurtcodeWarmteprogrammaAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(BuurtcodeWarmteprogramma)
    list_select_related = True


@admin.register(StadsverwarmingKengetal)
class StadsverwarmingKengetalAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(StadsverwarmingKengetal)
