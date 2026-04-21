from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from django.db import models

from apps.calculations.models import Conversie
from apps.kengetallen.models import Subkengetal
from apps.calculations.calculator import (
    EnergieCalculationResult,
    StadsverwarmingCalculatorFullResult,
)


class SubsysteemCalculationMethod(models.TextChoices):
    Investering = "Investering", "Investering"
    Openbron = "openbron", "Openbron"
    Gbs = "gbs", "GBS"
    Stadsverwarming = "stadsverwarming", "Stadsverwarming"
    Warmtepomp = "warmtepomp", "Warmtepomp"


@dataclass(frozen=True)
class SubsysteemBerekening:
    afschrijving_eur_per_woning_per_jaar: Decimal
    onderhoud_eur_per_woning_per_jaar: Decimal
    tco: Decimal


@dataclass(frozen=True)
class SubsysteemScenarioResult:
    scenario: str
    method: str
    berekening: SubsysteemBerekening


@dataclass(frozen=True)
class SubsysteemFullResult:
    results: list[SubsysteemScenarioResult]
    by_scenario: dict[str, SubsysteemScenarioResult]


def calculate_investering(subkengetal: Subkengetal) -> SubsysteemBerekening:
    """Calculation method 'Investering'.

    Based on the `Subkengetal` connected to the subsysteem + scenario:

    - Afschrijving [€/w/j] = investeringskosten / levensduur
    - Onderhoud [€/w/j] = investeringskosten * beheer_en_onderhoud
    """
    jaren_tco = get_jaren_tco()

    investering = subkengetal.investeringskosten
    afschrijving = investering / subkengetal.levensduur
    onderhoud = investering * subkengetal.beheer_en_onderhoud
    tco = (afschrijving + onderhoud) * jaren_tco
    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving,
        onderhoud_eur_per_woning_per_jaar=onderhoud,
        tco=tco,
    )


def calculate_openbron_systeem(
    subkengetal: Subkengetal, *, cv_energie_calculation: EnergieCalculationResult
) -> SubsysteemBerekening:
    """Calculation method 'Openbron systeem'.

    Based on the `Subkengetal` connected to the subsysteem + scenario:

    Uses fields from the `Subkengetal` fixture:

    - Omrekenen m³/h naar L/s: `debiet_bron * m3_naar_l / h_naar_sec`
    - Berekening Joule/Liter: `energie_bron * delta_temperatuur_retour * kj_naar_j`
    - Warmtevraag vermogen per woning [W]: from the CV energie calculation:
            `cv_energie_calculation.vermogen_warmte_kw_per_woning * 1000`
    """

    conversie_m3_naar_l = Conversie.objects.get(naam="m3_naar_l").waarde
    conversie_h_naar_sec = Conversie.objects.get(naam="h_naar_sec").waarde
    conversie_kj_naar_j = Conversie.objects.get(naam="kj_naar_j").waarde

    debiet_bron_m3_per_h = Decimal(subkengetal.debiet_bron)
    debiet_bron_l_per_s = (
        debiet_bron_m3_per_h * conversie_m3_naar_l / conversie_h_naar_sec
    )

    joule_per_liter = (
        subkengetal.energie_bron
        * Decimal(subkengetal.delta_temperatuur_retour)
        * conversie_kj_naar_j
    )

    cv_kw_per_woning = cv_energie_calculation.vermogen_warmte_kw_per_woning
    cv_w_per_woning = cv_kw_per_woning * Decimal("1000")

    verhouding_vermogen_bron = subkengetal.verhouding_vermogen_bron

    aantal_woningen_op_bron = (
        debiet_bron_l_per_s
        * joule_per_liter
        / (cv_w_per_woning * verhouding_vermogen_bron)
    )

    investering_eur_per_woning = (
        subkengetal.investeringskosten / aantal_woningen_op_bron
    )

    jaren_tco = get_jaren_tco()

    afschrijving = investering_eur_per_woning / Decimal(subkengetal.levensduur)
    onderhoud = investering_eur_per_woning * subkengetal.beheer_en_onderhoud
    tco = (afschrijving + onderhoud) * jaren_tco
    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving,
        onderhoud_eur_per_woning_per_jaar=onderhoud,
        tco=tco,
    )


def calculate_gbs(
    subkengetal: Subkengetal,
    cv_energie_calculation: EnergieCalculationResult,
    aantal_woningen: int | Decimal,
) -> SubsysteemBerekening:
    """Calculation method 'GBS'.
    Based on the `Subkengetal` connected to the subsysteem + scenario:
    - Warmtevraag vermogen VvE totaal [kW]:
        `warmtevraag_vermogen_vve_totaal = cv_energie_calculation.vermogen_warmte_kw_per_vve`
    - Vermogen bron [kW]:
        `verhouding_bron = warmtevraag_vermogen_vve_totaal * subkengetal.verhouding_vermogen_bron`
    - Aantal lussen:
        `berekening_aantal_lussen = verhouding_bron / subkengetal.onttrekkingsvermogen`
    - Investering VvE:
        `investering_vve = subkengetal.investeringskosten * berekening_aantal_lussen`
    - Investering per woning:
        `investering_eur_per_woning = investering_vve / aantal_woningen`
    - Afschrijving [€/w/j]:
        `afschrijving_woning_per_jaar = investering_eur_per_woning / Decimal(subkengetal.levensduur)`
    - Onderhoud [€/w/j]:
        `onderhoud_woning_per_jaar = investering_eur_per_woning * subkengetal.beheer_en_onderhoud`
    """
    warmtevraag_vermogen_vve_totaal = cv_energie_calculation.vermogen_warmte_kw_per_vve
    verhouding_bron = (
        warmtevraag_vermogen_vve_totaal * subkengetal.verhouding_vermogen_bron
    )
    berekening_aantal_lussen = verhouding_bron / subkengetal.onttrekkingsvermogen
    investering_vve = subkengetal.investeringskosten * berekening_aantal_lussen

    investering_eur_per_woning = investering_vve / aantal_woningen
    afschrijving_woning_per_jaar = investering_eur_per_woning / Decimal(
        subkengetal.levensduur
    )
    jaren_tco = get_jaren_tco()

    onderhoud_woning_per_jaar = (
        investering_eur_per_woning * subkengetal.beheer_en_onderhoud
    )
    tco = (afschrijving_woning_per_jaar + onderhoud_woning_per_jaar) * jaren_tco
    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving_woning_per_jaar,
        onderhoud_eur_per_woning_per_jaar=onderhoud_woning_per_jaar,
        tco=tco,
    )


def calculate_stadsverwarming(
    subsysteem_naam: str,
    stadsverwarming_result: StadsverwarmingCalculatorFullResult,
    scenario: object,
) -> SubsysteemBerekening:
    totals = stadsverwarming_result.kosten_totals_by_scenario[str(scenario)]
    if subsysteem_naam == "Particulier Stadswarmte":
        kosten = totals.stadsverwarming_kosten_particulier_warmte
    elif subsysteem_naam == "Particulier Stadswarmte + koude":
        kosten = totals.stadsverwarming_kosten_particulier_koude
    elif subsysteem_naam == "Zakelijk Stadswarmte":
        kosten = totals.stadsverwarming_kosten_zakelijk_warmte
    elif subsysteem_naam == "Zakelijk Stadswarmte + koude":
        kosten = totals.stadsverwarming_kosten_zakelijk_warmte_koude
    else:
        raise ValueError(f"Unknown stadswarmte subsysteem: {subsysteem_naam}")

    jaren_tco = get_jaren_tco()
    tco = kosten * jaren_tco
    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=Decimal("0"),
        onderhoud_eur_per_woning_per_jaar=Decimal("0"),
        tco=tco,
    )


def calculate_warmtepomp(
    subsysteem_naam: str,
    subkengetal: Subkengetal,
    tap_energie_calculation: EnergieCalculationResult,
    cv_energie_calculation: EnergieCalculationResult,
    aantal_woningen: int | Decimal,
) -> SubsysteemBerekening:
    """Calculation method 'Warmtepomp'."""

    P_MAX_LT = Decimal("250")
    P_MAX_HT = Decimal("250")
    COEF_LT = Decimal("3822.1")
    COEF_HT = Decimal("3900.6")
    EXP_LT = Decimal("-0.417")
    EXP_HT = Decimal("-0.408")

    P_MAX = P_MAX_LT if subsysteem_naam == "Collectieve LT-WP" else P_MAX_HT
    benodigd_vermogen = tap_energie_calculation.vermogen_warmte_kw_per_vve
    if subsysteem_naam == "Collectieve LWP":
        benodigd_vermogen += cv_energie_calculation.vermogen_warmte_kw_per_vve
    elif subsysteem_naam == "Collectieve LT-WP":
        benodigd_vermogen = cv_energie_calculation.vermogen_warmte_kw_per_vve

    aantal_warmtepompen_benodigd = math.ceil(benodigd_vermogen / P_MAX)
    vermogen_per_Warmtepomp = benodigd_vermogen / aantal_warmtepompen_benodigd
    formule = COEF_HT * (vermogen_per_Warmtepomp**EXP_HT) * benodigd_vermogen
    if subsysteem_naam == "Collectieve LT-WP":
        formule = COEF_LT * (vermogen_per_Warmtepomp**EXP_LT) * benodigd_vermogen

    jaren_tco = get_jaren_tco()
    afschrijving = formule / subkengetal.levensduur / aantal_woningen
    onderhoud = formule * subkengetal.beheer_en_onderhoud / aantal_woningen
    tco = (afschrijving + onderhoud) * jaren_tco

    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving,
        onderhoud_eur_per_woning_per_jaar=onderhoud,
        tco=tco,
    )


def get_jaren_tco() -> Decimal:
    return Conversie.objects.get(naam="jaren_tco").waarde
