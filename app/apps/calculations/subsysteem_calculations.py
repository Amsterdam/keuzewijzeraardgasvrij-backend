from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from django.db import models


class SubsysteemCalculationMethod(models.TextChoices):
    Investering = "Investering", "Investering"


class SubsysteemInvesteringBerekening(TypedDict):
    afschrijving_eur_per_woning_per_jaar: Decimal
    onderhoud_eur_per_woning_per_jaar: Decimal


def calculate_investering(subkengetal) -> SubsysteemInvesteringBerekening:
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
