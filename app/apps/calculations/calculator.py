from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from numbers import Number
from typing import Final, Iterable, Literal
from django.db.models import Q
from apps.kengetallen.models import (
    AlgemeenKengetal,
    GelijktijdigheidCV,
    ScenarioKeuze,
    StadsverwarmingEenheid,
    StadsverwarmingInterval,
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
    woning_type: str | None = None
    vermogen_cv: Decimal | None = None


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
    stadsverwarming_kosten_particulier_warmte: Decimal
    stadsverwarming_kosten_particulier_koude: Decimal
    stadsverwarming_kosten_zakelijk_warmte: Decimal
    stadsverwarming_kosten_zakelijk_warmte_koude: Decimal


@dataclass(frozen=True, slots=True)
class StadsverwarmingScenarioKostenTotals:
    stadsverwarming_kosten_particulier_warmte: Decimal
    stadsverwarming_kosten_particulier_koude: Decimal
    stadsverwarming_kosten_zakelijk_warmte: Decimal
    stadsverwarming_kosten_zakelijk_warmte_koude: Decimal


@dataclass(frozen=True, slots=True)
class StadsverwarmingCalculatorFullResult:
    results: list[StadsverwarmingKengetalCalculationResult]
    by_scenario: dict[str, list[StadsverwarmingKengetalCalculationResult]]
    kosten_totals_by_scenario: dict[str, StadsverwarmingScenarioKostenTotals]


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
        woning_type = result.get("woning_type")
        vermogen_cv = result.get("vermogen_cv")
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
            woning_type=None if woning_type is None else str(woning_type),
            vermogen_cv=None if vermogen_cv is None else self._to_decimal(vermogen_cv),
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
        percentage_ruimteverwarming = kengetallen["percentage_ruimteverwarming"]
        rendement_gasketel = kengetallen["rendement_gasketel"]

        vermogen_warmte_kw_per_woning = (
            warmtevraag_kw_per_woning
            / Decimal(calculation_input.aantal_woningen).sqrt()
        )

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
                "percentage_ruimteverwarming",
                "rendement_gasketel",
                "gelijktijdigheid_cv",
                "gasvraag_koken",
                "vermogen_cv_max",
                "vermogen_cv_matig",
                "vermogen_cv_versterkt",
                "vermogen_cv_min",
            ],
        )

        percentage_ruimteverwarming = kengetallen["percentage_ruimteverwarming"]
        rendement_gasketel = kengetallen["rendement_gasketel"]
        gelijktijdigheid_cv = self._get_gelijktijdigheidcv_factor(
            aantal_woningen=calculation_input.aantal_woningen,
            fallback=kengetallen["gelijktijdigheid_cv"],
        )

        vermogen_cv = kengetallen["vermogen_cv_min"]
        woning_type = "Nieuwer dan 2021 (BENG)"
        if calculation_input.bouwjaar < 2000 and not calculation_input.dubbel_glas:
            woning_type = "Ouder dan 2000"
            vermogen_cv = kengetallen["vermogen_cv_max"]

        elif calculation_input.wtw_aanwezig and calculation_input.bouwjaar < 2021:
            woning_type = "Nieuwer dan 2000 of voorzien van dubbel glas (met WTW)"
            vermogen_cv = kengetallen["vermogen_cv_matig"]

        elif calculation_input.bouwjaar < 2021:
            woning_type = "Nieuwer dan 2000 of voorzien van dubbel glas"
            vermogen_cv = kengetallen["vermogen_cv_versterkt"]

        vermogen_warmte_kw_per_woning = (
            vermogen_cv
            * calculation_input.bruto_vloeroppervlak
            * gelijktijdigheid_cv
            / Decimal(calculation_input.aantal_woningen)
        )

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
            "woning_type": woning_type,
            "vermogen_cv": vermogen_cv,
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
        vermogen_warmte_kw_per_woning = (
            kengetallen["warmtevraag_koude"]
            * calculation_input.bruto_vloeroppervlak
            / Decimal(calculation_input.aantal_woningen)
        )
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

    def _get_gelijktijdigheidcv_factor(
        self,
        *,
        aantal_woningen: int,
        fallback: Decimal,
    ) -> Decimal:
        row = (
            GelijktijdigheidCV.objects.filter(n_min__lte=aantal_woningen)
            .filter(Q(n_max__isnull=True) | Q(n_max__gte=aantal_woningen))
            .order_by("-n_min")
            .values_list("factor", flat=True)
            .first()
        )
        return fallback if row is None else self._to_decimal(row)


class StadsverwarmingCalculator:
    def calculate(
        self,
        energie_calculation: EnergieCalculatorFullResult,
        aantal_woningen: int,
    ) -> StadsverwarmingCalculatorFullResult:
        jaren_tco = Conversie.objects.get(naam="jaren_tco").waarde
        conversie_md_j = Decimal("12")

        results: list[StadsverwarmingKengetalCalculationResult] = []
        by_scenario: dict[str, list[StadsverwarmingKengetalCalculationResult]] = {}
        kosten_totals_by_scenario: dict[str, StadsverwarmingScenarioKostenTotals] = {}

        kengetallen = StadsverwarmingKengetal.objects.order_by("id")
        for scenario_key, by_type in energie_calculation.by_scenario.items():
            by_scenario[scenario_key] = []

            total_particulier_warmte = Decimal("0")
            total_particulier_koude = Decimal("0")
            total_zakelijk_warmte = Decimal("0")
            total_zakelijk_warmte_koude = Decimal("0")

            vermogens = self._get_scenario_vermogens(by_type)
            for kengetal in kengetallen:
                factor_collectief = self._get_factor_collectief(
                    klanttype=kengetal.klanttype,
                    aantal_woningen=aantal_woningen,
                )
                factor_naar_jaar = self._get_factor_naar_jaar(
                    interval=kengetal.interval,
                    jaren_tco=jaren_tco,
                    conversie_md_j=conversie_md_j,
                )

                te_berekenen_vermogen = self._get_te_berekenen_vermogen(
                    vermogen_berekenen_op=kengetal.vermogen_berekenen_op,
                    vermogens=vermogens,
                )
                is_tussen_min_max, is_boven_max = self._calculate_minmax_flags(
                    te_berekenen_vermogen=te_berekenen_vermogen,
                    kw_min=kengetal.kw_min,
                    kw_max=kengetal.kw_max,
                )

                waarde_vast = self._get_waarde_vast(kengetal.eenheid, kengetal.waarde_1)
                waarde_geclassificeerd = self._get_waarde_geclassificeerd(
                    eenheid=kengetal.eenheid,
                    is_tussen_min_max=is_tussen_min_max,
                    waarde_1=kengetal.waarde_1,
                )
                waarde_variabel = self._get_waarde_variabel(
                    eenheid=kengetal.eenheid,
                    te_berekenen_vermogen=te_berekenen_vermogen,
                    is_tussen_min_max=is_tussen_min_max,
                    is_boven_max=is_boven_max,
                    kw_min=kengetal.kw_min,
                    kw_max=kengetal.kw_max,
                    waarde_1=kengetal.waarde_1,
                    waarde_2=kengetal.waarde_2,
                )

                kosten_totaal = self._get_kosten_totaal(
                    waarde_vast=waarde_vast,
                    waarde_variabel=waarde_variabel,
                    waarde_geclassificeerd=waarde_geclassificeerd,
                    factor_naar_jaar=factor_naar_jaar,
                    factor_collectief=factor_collectief,
                )
                (
                    kosten_particulier_warmte,
                    kosten_particulier_koude,
                    kosten_zakelijk_warmte,
                    kosten_zakelijk_warmte_koude,
                ) = self._get_kosten_for_type(
                    klanttype=kengetal.klanttype,
                    producttype=kengetal.producttype,
                    kosten_totaal=kosten_totaal,
                )

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
                    vermogen_cv_vve=vermogens[EnergieType.CV],
                    vermogen_tap_vve=vermogens[EnergieType.TAP],
                    vermogen_koude_vve=vermogens[EnergieType.GKW],
                    te_berekenen_vermogen=te_berekenen_vermogen,
                    is_tussen_min_max=is_tussen_min_max,
                    is_boven_max=is_boven_max,
                    waarde_vast=waarde_vast,
                    waarde_geclassificeerd=waarde_geclassificeerd,
                    waarde_variabel=waarde_variabel,
                    factor_naar_jaar=factor_naar_jaar,
                    factor_collectief=factor_collectief,
                    stadsverwarming_kosten_totaal=kosten_totaal,
                    stadsverwarming_kosten_particulier_warmte=kosten_particulier_warmte,
                    stadsverwarming_kosten_particulier_koude=kosten_particulier_koude,
                    stadsverwarming_kosten_zakelijk_warmte=kosten_zakelijk_warmte,
                    stadsverwarming_kosten_zakelijk_warmte_koude=kosten_zakelijk_warmte_koude,
                )

                results.append(single)
                by_scenario[scenario_key].append(single)

                total_particulier_warmte += (
                    single.stadsverwarming_kosten_particulier_warmte
                )
                total_particulier_koude += (
                    single.stadsverwarming_kosten_particulier_koude
                )
                total_zakelijk_warmte += single.stadsverwarming_kosten_zakelijk_warmte
                total_zakelijk_warmte_koude += (
                    single.stadsverwarming_kosten_zakelijk_warmte_koude
                )

            kosten_totals_by_scenario[scenario_key] = (
                StadsverwarmingScenarioKostenTotals(
                    stadsverwarming_kosten_particulier_warmte=total_particulier_warmte,
                    stadsverwarming_kosten_particulier_koude=total_particulier_koude,
                    stadsverwarming_kosten_zakelijk_warmte=total_zakelijk_warmte,
                    stadsverwarming_kosten_zakelijk_warmte_koude=total_zakelijk_warmte_koude,
                )
            )

        return StadsverwarmingCalculatorFullResult(
            results=results,
            by_scenario=by_scenario,
            kosten_totals_by_scenario=kosten_totals_by_scenario,
        )

    def _get_scenario_vermogens(
        self,
        by_type: dict[EnergieTypeValue, EnergieCalculationResult],
    ) -> dict[EnergieTypeValue, Decimal]:
        return {
            EnergieType.CV: by_type[EnergieType.CV].vermogen_warmte_kw_per_vve,
            EnergieType.TAP: by_type[EnergieType.TAP].vermogen_warmte_kw_per_vve,
            EnergieType.GKW: by_type[EnergieType.GKW].vermogen_warmte_kw_per_vve,
        }

    def _get_factor_collectief(
        self, *, klanttype: str, aantal_woningen: int
    ) -> Decimal:
        if klanttype == StadsverwarmingKlantType.ZAKELIJK:
            return Decimal("1") / Decimal(aantal_woningen)
        return Decimal("1")

    def _get_factor_naar_jaar(
        self,
        interval: str,
        jaren_tco: Decimal,
        conversie_md_j: Decimal,
    ) -> Decimal:
        if interval == StadsverwarmingInterval.EENMALIG:
            return Decimal("1") / jaren_tco
        if interval == StadsverwarmingInterval.MAANDELIJKS:
            return conversie_md_j
        return Decimal("1")

    def _get_te_berekenen_vermogen(
        self,
        vermogen_berekenen_op: str | None,
        vermogens: dict[EnergieTypeValue, Decimal],
    ) -> Decimal | None:
        if vermogen_berekenen_op == StadsverwarmingVermogenBerekenenOp.WARMTE:
            return vermogens[EnergieType.CV] + vermogens[EnergieType.TAP]
        if vermogen_berekenen_op == StadsverwarmingVermogenBerekenenOp.KOUDE:
            return vermogens[EnergieType.GKW]
        return None

    def _calculate_minmax_flags(
        self,
        te_berekenen_vermogen: Decimal | None,
        kw_min: Decimal | None,
        kw_max: Decimal | None,
    ) -> tuple[bool, bool]:
        if te_berekenen_vermogen is None:
            return False, False

        min_val = kw_min if kw_min is not None else Decimal("-Infinity")
        max_val = kw_max if kw_max is not None else Decimal("Infinity")

        is_boven_max = te_berekenen_vermogen >= max_val
        is_tussen_min_max = min_val <= te_berekenen_vermogen < max_val
        return is_tussen_min_max, is_boven_max

    def _get_waarde_vast(self, eenheid: str, waarde_1: Decimal) -> Decimal:
        return waarde_1 if eenheid == StadsverwarmingEenheid.VAST else Decimal("0")

    def _get_waarde_geclassificeerd(
        self,
        eenheid: str,
        is_tussen_min_max: bool,
        waarde_1: Decimal,
    ) -> Decimal:
        if eenheid == StadsverwarmingEenheid.GECLASSIFICEERD and is_tussen_min_max:
            return waarde_1
        return Decimal("0")

    def _get_waarde_variabel(
        self,
        eenheid: str,
        te_berekenen_vermogen: Decimal | None,
        is_tussen_min_max: bool,
        is_boven_max: bool,
        kw_min: Decimal | None,
        kw_max: Decimal | None,
        waarde_1: Decimal,
        waarde_2: Decimal,
    ) -> Decimal:
        if eenheid != StadsverwarmingEenheid.VARIABEL or te_berekenen_vermogen is None:
            return Decimal("0")

        if waarde_2 > 0 and is_tussen_min_max:
            return (te_berekenen_vermogen - kw_min) * (
                waarde_1 - (waarde_2 * te_berekenen_vermogen)
            )
        if waarde_2 > 0 and is_boven_max and kw_max is not None:
            return (kw_max - kw_min) * (waarde_1 - (waarde_2 * (kw_max - kw_min)))
        if waarde_2 == 0 and is_tussen_min_max:
            return (te_berekenen_vermogen - kw_min) * waarde_1
        if waarde_2 == 0 and is_boven_max and kw_max is not None:
            return (kw_max - kw_min) * waarde_1

        return Decimal("0")

    def _get_kosten_totaal(
        self,
        *,
        waarde_vast: Decimal,
        waarde_variabel: Decimal,
        waarde_geclassificeerd: Decimal,
        factor_naar_jaar: Decimal,
        factor_collectief: Decimal,
    ) -> Decimal:
        return (
            (waarde_vast + waarde_variabel + waarde_geclassificeerd)
            * factor_naar_jaar
            * factor_collectief
        )

    def _get_kosten_for_type(
        self,
        *,
        klanttype: str,
        producttype: str,
        kosten_totaal: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        if klanttype == StadsverwarmingKlantType.PARTICULIER and producttype in {
            StadsverwarmingProductType.WARMTE,
            StadsverwarmingProductType.WARMTE_KOUDE,
        }:
            kosten_particulier_warmte = kosten_totaal
        else:
            kosten_particulier_warmte = Decimal("0")

        if klanttype == StadsverwarmingKlantType.PARTICULIER and producttype in {
            StadsverwarmingProductType.KOUDE,
            StadsverwarmingProductType.WARMTE_KOUDE,
        }:
            kosten_particulier_koude = kosten_totaal
        else:
            kosten_particulier_koude = Decimal("0")

        if klanttype == StadsverwarmingKlantType.ZAKELIJK and producttype in {
            StadsverwarmingProductType.WARMTE,
            StadsverwarmingProductType.WARMTE_KOUDE,
        }:
            kosten_zakelijk_warmte = kosten_totaal
        else:
            kosten_zakelijk_warmte = Decimal("0")

        if klanttype == StadsverwarmingKlantType.ZAKELIJK and producttype in {
            StadsverwarmingProductType.KOUDE,
            StadsverwarmingProductType.WARMTE_KOUDE,
        }:
            kosten_zakelijk_warmte_koude = kosten_totaal
        else:
            kosten_zakelijk_warmte_koude = Decimal("0")

        return (
            kosten_particulier_warmte,
            kosten_particulier_koude,
            kosten_zakelijk_warmte,
            kosten_zakelijk_warmte_koude,
        )
