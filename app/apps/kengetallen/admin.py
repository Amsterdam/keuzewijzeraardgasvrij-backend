from decimal import Decimal

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
    McdaHoofdcriterium,
    McdaSubcriterium,
    MultiCriteriaAnalyseKengetal,
    StadsverwarmingKengetal,
    Subkengetal,
    Warmteprogramma,
)


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


def format(value: Decimal | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return str(value.quantize(Decimal("0.01")))


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


@admin.register(MultiCriteriaAnalyseKengetal)
class MultiCriteriaAnalyseKengetalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "hoofdsysteem",
        "huidig_systeem_collectief_2dp",
        "huidig_systeem_individueel_2dp",
        "vloerverwarming_aanwezig_waar_2dp",
        "vloerverwarming_aanwezig_onwaar_2dp",
    )
    list_select_related = True

    @admin.display(description="Huidig systeem - collectief")
    def huidig_systeem_collectief_2dp(self, obj: MultiCriteriaAnalyseKengetal) -> str:
        return format(obj.huidig_systeem_collectief)

    @admin.display(description="Huidig systeem - individueel")
    def huidig_systeem_individueel_2dp(self, obj: MultiCriteriaAnalyseKengetal) -> str:
        return format(obj.huidig_systeem_individueel)

    @admin.display(description="Vloerverwarming aanwezig WAAR")
    def vloerverwarming_aanwezig_waar_2dp(
        self, obj: MultiCriteriaAnalyseKengetal
    ) -> str:
        return format(obj.vloerverwarming_aanwezig_waar)

    @admin.display(description="Vloerverwarming aanwezig ONWAAR")
    def vloerverwarming_aanwezig_onwaar_2dp(
        self, obj: MultiCriteriaAnalyseKengetal
    ) -> str:
        return format(obj.vloerverwarming_aanwezig_onwaar)


@admin.register(McdaHoofdcriterium)
class McdaHoofdcriteriumAdmin(admin.ModelAdmin):
    list_display = ("id", "naam", "wegingsfactor_2dp")

    @admin.display(description="Wegingsfactor")
    def wegingsfactor_2dp(self, obj: McdaHoofdcriterium) -> str:
        return format(obj.wegingsfactor)


@admin.register(McdaSubcriterium)
class McdaSubcriteriumAdmin(admin.ModelAdmin):
    list_display = ("id", "hoofdcriterium", "naam", "relatieve_wegingsfactor_2dp")
    list_select_related = True

    @admin.display(description="Relatieve wegingsfactor")
    def relatieve_wegingsfactor_2dp(self, obj: McdaSubcriterium) -> str:
        return format(obj.relatieve_wegingsfactor)


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
