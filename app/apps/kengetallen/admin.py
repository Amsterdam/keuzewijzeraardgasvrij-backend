from decimal import Decimal
from typing import Any

from django.contrib import admin

from .models import (
    AlgemeenKengetal,
    BuurtcodeWarmteprogramma,
    CollectieveRuimteBinnen,
    CollectieveRuimteBuiten,
    CollectieveWarmtepompKengetal,
    EliminatieKengetal,
    GasverbruikGegeven,
    GelijktijdigheidCV,
    Hoofdkengetal,
    McdaHoofdcriterium,
    McdaSubcriterium,
    MultiCriteriaAnalyseKengetal,
    StadsverwarmingKengetal,
    Subkengetal,
    Warmteprogramma,
)

ADMIN_FIELD_LABELS = {
    Subkengetal: {
        "investeringskosten": "Investeringskosten (€)",
        "levensduur": "Levensduur (jaar)",
        "beheer_en_onderhoud": "Beheer en onderhoud [%/inv]",
        "staffel": "Aantal woningen staffel",
        "verhouding_vermogen_bron": "Verhouding vermogen bron/WP",
        "debiet_bron": "Debiet bron [m3/h]",
        "energie_bron": "Energie bron [kJ/kg.K]",
        "delta_temperatuur_retour": "ΔT retour [K]",
        "onttrekkingsvermogen": "Ontrekkingsvermogen [kW/lus]",
    },
    CollectieveRuimteBinnen: {
        "n_min": "Minimum aantal woningen",
        "n_max": "Maximum aantal woningen",
        "vereiste_m2": "Vereiste ruimte binnen (m2)",
    },
    CollectieveRuimteBuiten: {
        "n_min": "Minimum aantal woningen",
        "n_max": "Maximum aantal woningen",
        "vereiste_m2": "Vereiste ruimte buiten (m2)",
    },
    EliminatieKengetal: {
        "woningen_min": "Minimum aantal woningen",
        "woningen_max": "Maximum aantal woningen",
        "benodigde_ruimte_in_woning_m2": "Benodigde ruimte in woning (m2)",
        "stadsverwarming_nodig": "Stadsverwarming nodig",
        "mechanische_ventilatie_nodig": "Mechanische ventilatie nodig",
        "kan_koelen": "Kan koelen",
        "laag_energieverbruik": "Laag energieverbruik",
    },
    McdaHoofdcriterium: {
        "wegingsfactor": "Wegingsfactor",
    },
    McdaSubcriterium: {
        "relatieve_wegingsfactor": "Relatieve wegingsfactor",
    },
    GelijktijdigheidCV: {
        "n_min": "Minimum aantal woningen",
        "n_max": "Maximum aantal woningen",
        "factor": "Gelijktijdigheidsfactor cv",
    },
    Warmteprogramma: {
        "categorie": "Categorie warmteprogramma",
        "warmtenet_start": "Startjaar warmtenet",
        "warmtenet_stop": "Eindjaar warmtenet",
    },
    BuurtcodeWarmteprogramma: {
        "buurtcode": "Buurtcode",
        "warmteprogramma": "Warmteprogramma categorie",
    },
    StadsverwarmingKengetal: {
        "klanttype": "Klanttype",
        "producttype": "Producttype",
        "kostetype": "Kostentype",
        "eenheid": "Eenheid",
        "interval": "Interval",
        "vermogen_berekenen_op": "Vermogen berekenen op",
        "kw_min": "Minimum vermogen (kW)",
        "kw_max": "Maximum vermogen (kW)",
        "positieve_factor": "Positieve factor",
        "negatieve_factor": "Negatieve factor",
    },
    GasverbruikGegeven: {
        "gemiddeld_verbruik": "Gemiddeld m3 per woning per jaar",
    },
}


def get_all_field_names(model):
    return [build_admin_field(model, field.name) for field in model._meta.fields]


def get_field_label(model, field_name: str) -> str:
    return ADMIN_FIELD_LABELS.get(model, {}).get(
        field_name, model._meta.get_field(field_name).verbose_name
    )


def build_admin_field(model, field_name: str):
    @admin.display(description=get_field_label(model, field_name), ordering=field_name)
    def display_field(obj: Any):
        return getattr(obj, field_name)

    display_field.__name__ = f"{model.__name__.lower()}_{field_name}"
    return display_field


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


@admin.register(GasverbruikGegeven)
class GasverbruikGegevenAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(GasverbruikGegeven)


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
