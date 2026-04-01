from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.db import models

from apps.kengetallen.models import Subkengetal
from apps.calculations.calculator import CalculationResult


class SubsysteemCalculationMethod(models.TextChoices):
    Investering = "Investering", "Investering"
    Openbron = "openbron", "Openbron"


class SubsysteemInvesteringBerekening(TypedDict):
    afschrijving_eur_per_woning_per_jaar: Decimal
    onderhoud_eur_per_woning_per_jaar: Decimal


class SubsysteemScenarioResult(SubsysteemInvesteringBerekening, total=False):
    Scenario: str
    Method: str

    debiet_bron_m3_per_h: Decimal
    debiet_bron_l_per_s: Decimal
    energie_bron_joule_per_liter: Decimal
    cv_vermogen_kw_per_woning: Decimal
    cv_vermogen_w_per_woning: Decimal
    verhouding_vermogen_bron: Decimal

    aantal_woningen_op_bron: Decimal
    investering_eur_per_woning: Decimal


class SubsysteemFullResult(TypedDict):
    results: list[SubsysteemScenarioResult]
    by_scenario: dict[str, SubsysteemScenarioResult]


CONVERSIE_m3_L = Decimal("1000")
CONVERSIE_h_sec = Decimal("3600")
CONVERSIE_kJ_J = Decimal("1000")


def calculate_investering(subkengetal: Subkengetal) -> SubsysteemInvesteringBerekening:
    """Calculation method 'Investering'.

    Based on the `Subkengetal` connected to the subsysteem + scenario:

    - Afschrijving [€/w/j] = investeringskosten / levensduur
    - Onderhoud [€/w/j] = investeringskosten * beheer_en_onderhoud
    """
    investering = subkengetal.investeringskosten
    afschrijving = investering / subkengetal.levensduur
    onderhoud = investering * subkengetal.beheer_en_onderhoud
    return {
        "afschrijving_eur_per_woning_per_jaar": afschrijving,
        "onderhoud_eur_per_woning_per_jaar": onderhoud,
    }


def calculate_openbron_systeem(
    subkengetal: Subkengetal, *, cv_energie_calculation: CalculationResult
) -> SubsysteemScenarioResult:
    """Calculation method 'Openbron systeem'.

    Based on the `Subkengetal` connected to the subsysteem + scenario:

    Uses fields from the `Subkengetal` fixture:

    - Omrekenen m³/h naar L/s: `debiet_bron * CONVERSIE_m3_L / CONVERSIE_h_sec`
    - Berekening Joule/Liter: `energie_bron * delta_temperatuur_retour * CONVERSIE_kJ_J`
    - Warmtevraag vermogen per woning [W]: from the CV energie calculation:
      `cv_energie_calculation["Vermogen warmte [kW/woning]"] * 1000`
    """
    debiet_bron_m3_per_h = Decimal(subkengetal.debiet_bron)
    debiet_bron_l_per_s = debiet_bron_m3_per_h * CONVERSIE_m3_L / CONVERSIE_h_sec

    joule_per_liter = (
        subkengetal.energie_bron
        * Decimal(subkengetal.delta_temperatuur_retour)
        * CONVERSIE_kJ_J
    )

    cv_kw_per_woning = cv_energie_calculation["Vermogen warmte [kW/woning]"]
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

    return {
        "afschrijving_eur_per_woning_per_jaar": afschrijving,
        "onderhoud_eur_per_woning_per_jaar": onderhoud,
    }
