from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import models

from apps.calculations.models import Conversie
from apps.kengetallen.models import Subkengetal
from apps.calculations.calculator import EnergieCalculationResult


class SubsysteemCalculationMethod(models.TextChoices):
    Investering = "Investering", "Investering"
    Openbron = "openbron", "Openbron"


@dataclass(frozen=True)
class SubsysteemBerekening:
    afschrijving_eur_per_woning_per_jaar: Decimal
    onderhoud_eur_per_woning_per_jaar: Decimal


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
    investering = subkengetal.investeringskosten
    afschrijving = investering / subkengetal.levensduur
    onderhoud = investering * subkengetal.beheer_en_onderhoud
    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving,
        onderhoud_eur_per_woning_per_jaar=onderhoud,
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

    afschrijving = investering_eur_per_woning / Decimal(subkengetal.levensduur)
    onderhoud = investering_eur_per_woning * subkengetal.beheer_en_onderhoud

    return SubsysteemBerekening(
        afschrijving_eur_per_woning_per_jaar=afschrijving,
        onderhoud_eur_per_woning_per_jaar=onderhoud,
    )
