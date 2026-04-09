from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from numbers import Number
from typing import Final, Iterable, Literal

from apps.kengetallen.models import (
    AlgemeenKengetal,
    ScenarioKeuze,
    StadsverwarmingEenheid,
    StadsverwarmingKengetal,
    StadsverwarmingKlantType,
    StadsverwarmingProductType,
    StadsverwarmingVermogenBerekenenOp,
)

from .models import Conversie, GebruikersInvoer


EnergieTypeValue = Literal["tapwater", "cv", "gkw"]


class EnergieType:
    TAP: Final[EnergieTypeValue] = "tapwater"
    CV: Final[EnergieTypeValue] = "cv"
    GKW: Final[EnergieTypeValue] = "gkw"


@dataclass(frozen=True)
class EnergieCalculationResult:
    energie_type: EnergieTypeValue
    scenario: str
    vermogen_warmte_kw_per_woning: Decimal
    vermogen_warmte_kw_per_vve: Decimal
    gas_m3_per_year: Decimal
    capaciteit_warmte_kwh_per_year_per_woning: Decimal
    capaciteit_warmte_gj_per_year_per_woning: Decimal


@dataclass(frozen=True)
class EnergieCalculatorFullResult:
    results: list[EnergieCalculationResult]
    by_scenario: dict[str, dict[EnergieTypeValue, EnergieCalculationResult]]


@dataclass(frozen=True, slots=True)
class StadsverwarmingKengetalCalculationResult:
    scenario: str
    kengetal_id: int

    klanttype: StadsverwarmingKlantType
    producttype: StadsverwarmingProductType
    kostetype: str
    eenheid: StadsverwarmingEenheid
    interval: str
    vermogen_berekenen_op: StadsverwarmingVermogenBerekenenOp | None

    kw_min: Decimal | None
    kw_max: Decimal | None
    waarde_1: Decimal
    waarde_2: Decimal

    vermogen_cv_vve: Decimal
    vermogen_tap_vve: Decimal
    vermogen_koude_vve: Decimal
    te_berekenen_vermogen: Decimal | None

    is_tussen_min_max: bool
    is_boven_max: bool

    waarde_vast: Decimal
    waarde_geclassificeerd: Decimal
    waarde_variabel: Decimal

    factor_naar_jaar: Decimal
    factor_collectief: Decimal

    stadsverwarming_kosten_totaal: Decimal
    stadsverwarming_kosten_particulier: Decimal
    stadsverwarming_kosten_zakelijk_warmte: Decimal
    stadsverwarming_kosten_zakelijk_warmte_koude: Decimal


@dataclass(frozen=True, slots=True)
class StadsverwarmingCalculatorFullResult:
    results: list[StadsverwarmingKengetalCalculationResult]
    by_scenario: dict[str, list[StadsverwarmingKengetalCalculationResult]]


class EnergieCalculator:
    def calculate(
        self,
        calculation_input: GebruikersInvoer,
        *,
        scenarios: Iterable[ScenarioKeuze] = (
            ScenarioKeuze.LAAG,
            ScenarioKeuze.MIDDEN,
            ScenarioKeuze.HOOG,
        ),
        energie_types: Iterable[EnergieTypeValue] = (
            EnergieType.TAP,
            EnergieType.CV,
            EnergieType.GKW,
        ),
    ) -> EnergieCalculatorFullResult:
        conversie_m3gas_naar_kwh = Conversie.objects.get(naam="m3gas_naar_kwh").waarde
        conversie_kwh_naar_gj = Conversie.objects.get(naam="kwh_naar_gj").waarde

        results: list[EnergieCalculationResult] = []
        by_scenario: dict[str, dict[EnergieTypeValue, EnergieCalculationResult]] = {}

        for scenario in scenarios:
            scenario_key = str(scenario)
            by_scenario[scenario_key] = {}

            for energie_type in energie_types:
                single = self._calculate_single(
                    energie_type,
                    scenario,
                    calculation_input,
                    conversie_m3gas_naar_kwh=conversie_m3gas_naar_kwh,
                    conversie_kwh_naar_gj=conversie_kwh_naar_gj,
                )
                results.append(single)
                by_scenario[scenario_key][energie_type] = single

        return EnergieCalculatorFullResult(results=results, by_scenario=by_scenario)

    def _calculate_single(
        self,
        energie_type: EnergieTypeValue,
        scenario: ScenarioKeuze,
        calculation_input: GebruikersInvoer,
        *,
        conversie_m3gas_naar_kwh: Decimal,
        conversie_kwh_naar_gj: Decimal,
    ) -> EnergieCalculationResult:
        if energie_type == EnergieType.TAP:
            result = self._calculate_tap(
                scenario,
                calculation_input,
                conversie_m3gas_naar_kwh=conversie_m3gas_naar_kwh,
                conversie_kwh_naar_gj=conversie_kwh_naar_gj,
            )
        elif energie_type == EnergieType.CV:
            result = self._calculate_cv(
                scenario,
                calculation_input,
                conversie_m3gas_naar_kwh=conversie_m3gas_naar_kwh,
                conversie_kwh_naar_gj=conversie_kwh_naar_gj,
            )
        else:
            result = self._calculate_gkw(
                scenario,
                conversie_kwh_naar_gj=conversie_kwh_naar_gj,
                calculation_input=calculation_input,
            )

        vermogen_warmte_kw_per_woning = result["vermogen_warmte_kw_per_woning"]
        return EnergieCalculationResult(
            energie_type=energie_type,
            scenario=str(scenario),
            vermogen_warmte_kw_per_woning=vermogen_warmte_kw_per_woning,
            vermogen_warmte_kw_per_vve=vermogen_warmte_kw_per_woning
            * calculation_input.aantal_woningen,
            gas_m3_per_year=result["gas_m3_per_year"],
            capaciteit_warmte_kwh_per_year_per_woning=result[
                "capaciteit_warmte_kwh_per_year_per_woning"
            ],
            capaciteit_warmte_gj_per_year_per_woning=result[
                "capaciteit_warmte_gj_per_year_per_woning"
            ],
        )

    def _calculate_tap(
        self,
        scenario: ScenarioKeuze,
        calculation_input: GebruikersInvoer,
        *,
        conversie_m3gas_naar_kwh: Decimal,
        conversie_kwh_naar_gj: Decimal,
    ):
        kengetallen = self._get_kengetallen(
            scenario,
            [
                "warmtevraag_tap",
                "percentage_ruimteverwarming",
                "rendement_gasketel",
                "gasvraag_koken",
            ],
        )

        warmtevraag_kw_per_woning = kengetallen["warmtevraag_tap"]
        gelijktijdigheid_tap = (
            Decimal("1") / Decimal(calculation_input.aantal_woningen).sqrt()
        )
        percentage_ruimteverwarming = kengetallen["percentage_ruimteverwarming"]
        rendement_gasketel = kengetallen["rendement_gasketel"]

        vermogen_warmte_kw_per_woning = warmtevraag_kw_per_woning * gelijktijdigheid_tap

        tapwater_factor = (
            Decimal("1") if calculation_input.tapwater_op_gas else Decimal("0")
        )
        gasverbruik_vve_totaal = self._to_decimal(
            calculation_input.gasverbruik_vve_totaal
        )
        gasverbruik_minus_gasvraag = (
            gasverbruik_vve_totaal - kengetallen["gasvraag_koken"]
            if calculation_input.koken_op_gas
            else gasverbruik_vve_totaal
        )
        gas_m3_per_year = (
            tapwater_factor
            * (Decimal("1") - percentage_ruimteverwarming)
            * gasverbruik_minus_gasvraag
        )

        capaciteit_kwh, capaciteit_gj = self._calculate_capaciteit_warmte_gj(
            gas_m3_per_year=gas_m3_per_year,
            rendement_gasketel=rendement_gasketel,
            conversie_m3gas_naar_kwh=conversie_m3gas_naar_kwh,
            conversie_kwh_naar_gj=conversie_kwh_naar_gj,
            aantal_woningen=calculation_input.aantal_woningen,
        )
        return {
            "vermogen_warmte_kw_per_woning": vermogen_warmte_kw_per_woning,
            "gas_m3_per_year": gas_m3_per_year,
            "capaciteit_warmte_kwh_per_year_per_woning": capaciteit_kwh,
            "capaciteit_warmte_gj_per_year_per_woning": capaciteit_gj,
        }

    def _calculate_cv(
        self,
        scenario: ScenarioKeuze,
        calculation_input: GebruikersInvoer,
        *,
        conversie_m3gas_naar_kwh: Decimal,
        conversie_kwh_naar_gj: Decimal,
    ):
        kengetallen = self._get_kengetallen(
            scenario,
            [
                "warmtevraag_cv",
                "percentage_ruimteverwarming",
                "rendement_gasketel",
                "gelijktijdigheid_cv",
                "gasvraag_koken",
            ],
        )

        warmtevraag_kw_per_woning = kengetallen["warmtevraag_cv"]
        percentage_ruimteverwarming = kengetallen["percentage_ruimteverwarming"]
        rendement_gasketel = kengetallen["rendement_gasketel"]
        gelijktijdigheid_cv = kengetallen["gelijktijdigheid_cv"]

        vermogen_warmte_kw_per_woning = warmtevraag_kw_per_woning * gelijktijdigheid_cv

        ruimteverwarming_factor = (
            percentage_ruimteverwarming
            if calculation_input.tapwater_op_gas
            else Decimal("1")
        )
        gasverbruik_vve_totaal = self._to_decimal(
            calculation_input.gasverbruik_vve_totaal
        )
        gasverbruik_minus_gasvraag = (
            gasverbruik_vve_totaal - kengetallen["gasvraag_koken"]
            if calculation_input.koken_op_gas
            else gasverbruik_vve_totaal
        )
        gas_m3_per_year = ruimteverwarming_factor * gasverbruik_minus_gasvraag

        capaciteit_kwh, capaciteit_gj = self._calculate_capaciteit_warmte_gj(
            gas_m3_per_year=gas_m3_per_year,
            rendement_gasketel=rendement_gasketel,
            conversie_m3gas_naar_kwh=conversie_m3gas_naar_kwh,
            conversie_kwh_naar_gj=conversie_kwh_naar_gj,
            aantal_woningen=calculation_input.aantal_woningen,
        )

        return {
            "vermogen_warmte_kw_per_woning": vermogen_warmte_kw_per_woning,
            "gas_m3_per_year": gas_m3_per_year,
            "capaciteit_warmte_kwh_per_year_per_woning": capaciteit_kwh,
            "capaciteit_warmte_gj_per_year_per_woning": capaciteit_gj,
        }

    def _calculate_gkw(
        self,
        scenario: ScenarioKeuze,
        *,
        conversie_kwh_naar_gj: Decimal,
        calculation_input: GebruikersInvoer,
    ):
        kengetallen = self._get_kengetallen(
            scenario,
            [
                "warmtevraag_koude",
                "koudevraag_capaciteit",
            ],
        )
        vermogen_warmte_kw_per_woning = kengetallen["warmtevraag_koude"]
        capaciteit_kwh = (
            kengetallen["koudevraag_capaciteit"]
            * calculation_input.bruto_vloeroppervlak
        )
        capaciteit_gj = capaciteit_kwh * conversie_kwh_naar_gj
        return {
            "vermogen_warmte_kw_per_woning": vermogen_warmte_kw_per_woning,
            "gas_m3_per_year": Decimal("0"),
            "capaciteit_warmte_kwh_per_year_per_woning": capaciteit_kwh,
            "capaciteit_warmte_gj_per_year_per_woning": capaciteit_gj,
        }

    def _calculate_capaciteit_warmte_gj(
        self,
        *,
        gas_m3_per_year: Decimal,
        rendement_gasketel: Decimal,
        conversie_m3gas_naar_kwh: Decimal,
        conversie_kwh_naar_gj: Decimal,
        aantal_woningen: Number,
    ) -> tuple[Decimal, Decimal]:
        capaciteit_kwh = (
            gas_m3_per_year
            * rendement_gasketel
            * conversie_m3gas_naar_kwh
            / aantal_woningen
        )
        return capaciteit_kwh, capaciteit_kwh * conversie_kwh_naar_gj

    def _to_decimal(self, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))

    def _get_kengetallen(
        self, scenario: ScenarioKeuze, names: Iterable[str]
    ) -> dict[str, Decimal]:
        requested = set(names)
        rows = (
            AlgemeenKengetal.objects.filter(scenario=scenario, naam__in=requested)
            .values_list("naam", "waarde")
            .iterator()
        )
        values = {naam: self._to_decimal(waarde) for naam, waarde in rows}
        missing = requested.difference(values.keys())
        if missing:
            raise AlgemeenKengetal.DoesNotExist(
                f"Missing AlgemeenKengetal for scenario={scenario}: {sorted(missing)}"
            )
        return values


class StadsverwarmingCalculator:
    def calculate(
        self,
        *,
        energie_calculation: EnergieCalculatorFullResult,
        aantal_woningen: int,
    ) -> StadsverwarmingCalculatorFullResult:

        jaren_tco = Decimal("30")
        conversie_md_j = Decimal("12")

        results: list[StadsverwarmingKengetalCalculationResult] = []
        by_scenario: dict[str, list[StadsverwarmingKengetalCalculationResult]] = {}
        kengetallen = StadsverwarmingKengetal.objects.order_by("id")

        for scenario_key, by_type in energie_calculation.by_scenario.items():
            by_scenario[scenario_key] = []
            cv_kw = by_type[EnergieType.CV].vermogen_warmte_kw_per_vve
            tap_kw = by_type[EnergieType.TAP].vermogen_warmte_kw_per_vve
            koude_kw = by_type[EnergieType.GKW].vermogen_warmte_kw_per_vve

            for kengetal in kengetallen:
                if str(kengetal.klanttype) == "zakelijk":
                    factor_collectief = Decimal("1") / Decimal(aantal_woningen)
                else:
                    factor_collectief = Decimal("1")

                interval = str(kengetal.interval)
                if interval == "eenmalig":
                    factor_naar_jaar = Decimal("1") / jaren_tco
                elif interval == "maandelijks":
                    factor_naar_jaar = conversie_md_j
                else:
                    factor_naar_jaar = Decimal("1")

                te_berekenen_vermogen: Decimal | None = None
                if (
                    kengetal.vermogen_berekenen_op
                    == StadsverwarmingVermogenBerekenenOp.WARMTE
                ):
                    te_berekenen_vermogen = cv_kw + tap_kw
                elif (
                    kengetal.vermogen_berekenen_op
                    == StadsverwarmingVermogenBerekenenOp.KOUDE
                ):
                    te_berekenen_vermogen = koude_kw

                is_tussen_min_max = False
                is_boven_max = False

                if te_berekenen_vermogen is not None:
                    min_val = (
                        kengetal.kw_min
                        if kengetal.kw_min is not None
                        else Decimal("-Infinity")
                    )
                    max_val = (
                        kengetal.kw_max
                        if kengetal.kw_max is not None
                        else Decimal("Infinity")
                    )

                    is_boven_max = te_berekenen_vermogen >= max_val
                    is_tussen_min_max = min_val <= te_berekenen_vermogen < max_val

                waarde_vast = (
                    kengetal.waarde_1
                    if kengetal.eenheid == StadsverwarmingEenheid.VAST
                    else Decimal("0")
                )

                waarde_geclassificeerd = Decimal("0")
                if (
                    kengetal.eenheid == StadsverwarmingEenheid.GECLASSIFICEERD
                    and is_tussen_min_max
                ):
                    waarde_geclassificeerd = kengetal.waarde_1

                waarde_variabel = Decimal("0")
                if (
                    kengetal.eenheid == StadsverwarmingEenheid.VARIABEL
                    and te_berekenen_vermogen is not None
                ):
                    if kengetal.waarde_2 > 0 and is_tussen_min_max:
                        waarde_variabel = (te_berekenen_vermogen - kengetal.kw_min) * (
                            kengetal.waarde_1
                            - (kengetal.waarde_2 * te_berekenen_vermogen)
                        )
                    elif (
                        kengetal.waarde_2 > 0
                        and is_boven_max
                        and kengetal.kw_max is not None
                    ):
                        waarde_variabel = (kengetal.kw_max - kengetal.kw_min) * (
                            kengetal.waarde_1
                            - (kengetal.waarde_2 * (kengetal.kw_max - kengetal.kw_min))
                        )
                    elif kengetal.waarde_2 == 0 and is_tussen_min_max:
                        waarde_variabel = (
                            te_berekenen_vermogen - kengetal.kw_min
                        ) * kengetal.waarde_1
                    elif (
                        kengetal.waarde_2 == 0
                        and is_boven_max
                        and kengetal.kw_max is not None
                    ):
                        waarde_variabel = (
                            kengetal.kw_max - kengetal.kw_min
                        ) * kengetal.waarde_1

                stadsverwarming_kosten_totaal = (
                    (waarde_vast + waarde_variabel + waarde_geclassificeerd)
                    * factor_naar_jaar
                    * factor_collectief
                )

                if (
                    kengetal.klanttype == StadsverwarmingKlantType.PARTICULIER
                    and kengetal.producttype
                    in {
                        StadsverwarmingProductType.WARMTE,
                        StadsverwarmingProductType.WARMTE_KOUDE,
                    }
                ):
                    stadsverwarming_kosten_particulier = stadsverwarming_kosten_totaal
                else:
                    stadsverwarming_kosten_particulier = Decimal("0")

                if (
                    kengetal.klanttype == StadsverwarmingKlantType.ZAKELIJK
                    and kengetal.producttype
                    in {
                        StadsverwarmingProductType.WARMTE,
                        StadsverwarmingProductType.WARMTE_KOUDE,
                    }
                ):
                    stadsverwarming_kosten_zakelijk_warmte = (
                        stadsverwarming_kosten_totaal
                    )
                else:
                    stadsverwarming_kosten_zakelijk_warmte = Decimal("0")

                if (
                    kengetal.klanttype == StadsverwarmingKlantType.ZAKELIJK
                    and kengetal.producttype
                    in {
                        StadsverwarmingProductType.KOUDE,
                        StadsverwarmingProductType.WARMTE_KOUDE,
                    }
                ):
                    stadsverwarming_kosten_zakelijk_warmte_koude = (
                        stadsverwarming_kosten_totaal
                    )
                else:
                    stadsverwarming_kosten_zakelijk_warmte_koude = Decimal("0")

                single = StadsverwarmingKengetalCalculationResult(
                    scenario=str(scenario_key),
                    kengetal_id=kengetal.id,
                    klanttype=StadsverwarmingKlantType(kengetal.klanttype),
                    producttype=StadsverwarmingProductType(kengetal.producttype),
                    kostetype=str(kengetal.kostetype),
                    eenheid=StadsverwarmingEenheid(kengetal.eenheid),
                    interval=str(kengetal.interval),
                    vermogen_berekenen_op=(
                        None
                        if kengetal.vermogen_berekenen_op is None
                        else StadsverwarmingVermogenBerekenenOp(
                            kengetal.vermogen_berekenen_op
                        )
                    ),
                    kw_min=kengetal.kw_min,
                    kw_max=kengetal.kw_max,
                    waarde_1=kengetal.waarde_1,
                    waarde_2=kengetal.waarde_2,
                    vermogen_cv_vve=cv_kw,
                    vermogen_tap_vve=tap_kw,
                    vermogen_koude_vve=koude_kw,
                    te_berekenen_vermogen=te_berekenen_vermogen,
                    is_tussen_min_max=is_tussen_min_max,
                    is_boven_max=is_boven_max,
                    waarde_vast=waarde_vast,
                    waarde_geclassificeerd=waarde_geclassificeerd,
                    waarde_variabel=waarde_variabel,
                    factor_naar_jaar=factor_naar_jaar,
                    factor_collectief=factor_collectief,
                    stadsverwarming_kosten_totaal=stadsverwarming_kosten_totaal,
                    stadsverwarming_kosten_particulier=stadsverwarming_kosten_particulier,
                    stadsverwarming_kosten_zakelijk_warmte=stadsverwarming_kosten_zakelijk_warmte,
                    stadsverwarming_kosten_zakelijk_warmte_koude=stadsverwarming_kosten_zakelijk_warmte_koude,
                )
                results.append(single)
                by_scenario[scenario_key].append(single)

        return StadsverwarmingCalculatorFullResult(
            results=results, by_scenario=by_scenario
        )
