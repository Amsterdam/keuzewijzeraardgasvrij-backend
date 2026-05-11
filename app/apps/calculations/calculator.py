from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from numbers import Number
from typing import TYPE_CHECKING, Final, Iterable, Literal, TypeAlias, TypedDict, cast
from django.db.models import Q
from apps.kengetallen.models import (
    AlgemeenKengetal,
    BuurtcodeWarmteprogramma,
    CollectieveRuimteBinnen,
    CollectieveRuimteBuiten,
    EliminatieKengetal,
    GelijktijdigheidCV,
    MultiCriteriaAnalyseKengetal,
    ScenarioKeuze,
    StadsverwarmingEenheid,
    StadsverwarmingInterval,
    StadsverwarmingKengetal,
    StadsverwarmingKlantType,
    StadsverwarmingProductType,
    StadsverwarmingVermogenBerekenenOp,
    McdaHoofdcriterium,
    McdaSubcriterium,
)

from .models import Conversie, GebruikersInvoer, HuidigSysteemChoices

if TYPE_CHECKING:
    from apps.systemen.models import Hoofdsysteem

EnergieTypeValue = Literal["tapwater", "cv", "gkw"]


MultiCriteriaAnalyseSortKey: TypeAlias = tuple[bool, Decimal, str]


class MultiCriteriaAnalyseRow(TypedDict):
    naam: str
    beschrijving: str
    tco: float
    score: float
    kosten_per_woning_per_jaar: float
    is_mogelijk: bool
    redenen: list[str]


class MultiCriteriaAnalyseMetrics(TypedDict):
    tco: Decimal
    elektrisch_vermogen: Decimal
    ruimte_in_woning: Decimal
    collectief_ruimte_binnen: Decimal
    collectief_ruimte_buiten: Decimal
    huidig_systeem: Decimal
    vloerverwarming: Decimal


class MultiCriteriaAnalyseBreakdownRow(TypedDict):
    naam: str
    is_mogelijk: bool
    score_totaal_1_10: Decimal

    tco_genormaliseerd: Decimal
    elektrisch_vermogen_genormaliseerd: Decimal
    ruimte_woning_genormaliseerd: Decimal
    ruimte_binnen_genormaliseerd: Decimal
    ruimte_buiten_genormaliseerd: Decimal

    score_huidig_systeem: Decimal
    score_huidig_systeem_genormaliseerd: Decimal
    score_vloerverwarming: Decimal
    score_vloerverwarming_genormaliseerd: Decimal

    score_tco_gewogen_1_10: Decimal
    score_elektrisch_vermogen_gewogen_1_10: Decimal
    score_ruimte_woning_gewogen_1_10: Decimal
    score_ruimte_binnen_gewogen_1_10: Decimal
    score_ruimte_buiten_gewogen_1_10: Decimal
    score_huidig_systeem_gewogen_1_10: Decimal
    score_vloerverwarming_gewogen_1_10: Decimal


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


@dataclass(frozen=True, slots=True)
class WarmtenetCalculatorResult:
    categorie: str
    warmtenet_start: int | None
    warmtenet_stop: int | None
    warmtenet_mogelijk: bool


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


class WarmtenetCalculator:
    def calculate(
        self, calculation_input: GebruikersInvoer
    ) -> WarmtenetCalculatorResult:
        buurtcode = calculation_input.buurtcode
        if not buurtcode:
            return WarmtenetCalculatorResult(
                categorie="",
                warmtenet_start=None,
                warmtenet_stop=None,
                warmtenet_mogelijk=False,
            )

        mapping = (
            BuurtcodeWarmteprogramma.objects.select_related("warmteprogramma")
            .filter(buurtcode=buurtcode)
            .first()
        )
        if mapping is None or mapping.warmteprogramma is None:
            return WarmtenetCalculatorResult(
                categorie="",
                warmtenet_start=None,
                warmtenet_stop=None,
                warmtenet_mogelijk=False,
            )

        wp = mapping.warmteprogramma
        jaar_vervangen = calculation_input.jaar_vervangen
        warmtenet_stop = wp.warmtenet_stop
        warmtenet_mogelijk = bool(
            jaar_vervangen is not None
            and warmtenet_stop is not None
            and jaar_vervangen >= warmtenet_stop
        )
        return WarmtenetCalculatorResult(
            categorie="" if wp.categorie is None else str(wp.categorie),
            warmtenet_start=wp.warmtenet_start,
            warmtenet_stop=wp.warmtenet_stop,
            warmtenet_mogelijk=warmtenet_mogelijk,
        )


class Eliminatie:
    def calculate(
        self,
        calculation_input: GebruikersInvoer,
        hoofdsysteem_naam: str,
    ) -> dict[str, object]:
        hoofdsysteem_naam = hoofdsysteem_naam
        aantal_woningen = calculation_input.aantal_woningen
        collectief_ruimte_binnen_benodigd = _get_collectieve_ruimte(
            CollectieveRuimteBinnen,
            hoofdsysteem_naam=hoofdsysteem_naam,
            aantal_woningen=aantal_woningen,
        )
        collectief_ruimte_buiten_benodigd = _get_collectieve_ruimte(
            CollectieveRuimteBuiten,
            hoofdsysteem_naam=hoofdsysteem_naam,
            aantal_woningen=aantal_woningen,
        )

        eliminatie_kengetal = EliminatieKengetal.objects.get(naam=hoofdsysteem_naam)

        redenen: list[str] = []

        max_label = (
            "∞"
            if eliminatie_kengetal.woningen_max is None
            else str(eliminatie_kengetal.woningen_max)
        )
        if not (
            aantal_woningen >= eliminatie_kengetal.woningen_min
            and (
                eliminatie_kengetal.woningen_max is None
                or aantal_woningen <= eliminatie_kengetal.woningen_max
            )
        ):
            redenen.append(
                f"Aantal woningen {aantal_woningen} voldoet niet aan range {eliminatie_kengetal.woningen_min}–{max_label} van {hoofdsysteem_naam}."
            )

        if (
            calculation_input.beschikbare_ruimte_in_woning_m2 is not None
            and calculation_input.beschikbare_ruimte_in_woning_m2
            < eliminatie_kengetal.benodigde_ruimte_in_woning_m2
        ):
            redenen.append(
                "Ruimte in woning "
                f"{calculation_input.beschikbare_ruimte_in_woning_m2} m² is onvoldoende voor {hoofdsysteem_naam} "
                f"(benodigd {eliminatie_kengetal.benodigde_ruimte_in_woning_m2} m²)."
            )

        if (
            calculation_input.beschikbare_collectieve_ruimte_binnen_m2 is not None
            and calculation_input.beschikbare_collectieve_ruimte_binnen_m2
            < collectief_ruimte_binnen_benodigd
        ):
            redenen.append(
                "Collectieve ruimte binnen "
                f"{calculation_input.beschikbare_collectieve_ruimte_binnen_m2} m² is onvoldoende voor {hoofdsysteem_naam} "
                f"(benodigd {collectief_ruimte_binnen_benodigd} m²)."
            )

        if (
            calculation_input.beschikbare_collectieve_ruimte_buiten_m2 is not None
            and calculation_input.beschikbare_collectieve_ruimte_buiten_m2
            < collectief_ruimte_buiten_benodigd
        ):
            redenen.append(
                "Collectieve ruimte buiten "
                f"{calculation_input.beschikbare_collectieve_ruimte_buiten_m2} m² is onvoldoende voor {hoofdsysteem_naam} "
                f"(benodigd {collectief_ruimte_buiten_benodigd} m²)."
            )

        if (
            eliminatie_kengetal.mechanische_ventilatie_nodig
            and not calculation_input.mechanische_ventilatie_aanwezig
        ):
            redenen.append(
                f"Mechanische ventilatie is vereist voor {hoofdsysteem_naam}, maar mechanische ventilatie is niet aanwezig."
            )

        if calculation_input.wens_tot_koelen and not eliminatie_kengetal.kan_koelen:
            redenen.append(
                f"Koeling is gewenst, maar {hoofdsysteem_naam} kan niet koelen."
            )

        if eliminatie_kengetal.stadsverwarming_nodig:
            if (
                calculation_input.buurtcode
                and calculation_input.jaar_vervangen is not None
            ):
                warmtenet_berekening = WarmtenetCalculator().calculate(
                    calculation_input
                )
                if not warmtenet_berekening.warmtenet_mogelijk:
                    redenen.append(
                        "Warmtenet is niet mogelijk vanwege de buurtcode en/of het jaar van vervangen."
                    )

        is_mogelijk = len(redenen) == 0

        return {
            "is_mogelijk": is_mogelijk,
            "redenen": redenen,
        }


class MultiCriteriaAnalyse:
    def calculate(
        self,
        calculation_input: GebruikersInvoer,
        hoofdsystemen: Iterable[Hoofdsysteem],
        energie_calculation: EnergieCalculatorFullResult,
    ) -> list[tuple[MultiCriteriaAnalyseSortKey, MultiCriteriaAnalyseRow]]:
        hoofdsystemen_list = list(hoofdsystemen)
        eliminatie = Eliminatie()
        weights = self._get_weights()

        rows_in_order, metrics_by_hoofdsysteem_naam = self._build_rows_and_metrics(
            hoofdsystemen_list=hoofdsystemen_list,
            calculation_input=calculation_input,
            energie_calculation=energie_calculation,
            eliminatie=eliminatie,
        )

        metric_lists = self._collect_metric_lists(
            hoofdsystemen_list=hoofdsystemen_list,
            metrics_by_hoofdsysteem_naam=metrics_by_hoofdsysteem_naam,
        )
        score_by_hoofdsysteem_naam = self._calculate_scores(
            hoofdsystemen_list=hoofdsystemen_list,
            metrics_by_hoofdsysteem_naam=metrics_by_hoofdsysteem_naam,
            weights=weights,
            metric_lists=metric_lists,
        )
        return self._build_items(
            rows_in_order=rows_in_order,
            score_by_hoofdsysteem_naam=score_by_hoofdsysteem_naam,
        )

    def calculate_breakdown_for_admin(
        self,
        *,
        calculation_input: GebruikersInvoer,
        hoofdsystemen: Iterable[Hoofdsysteem],
        energie_calculation: EnergieCalculatorFullResult,
    ) -> list[MultiCriteriaAnalyseBreakdownRow]:
        hoofdsystemen_list = list(hoofdsystemen)
        eliminatie = Eliminatie()
        weights = self._get_weights()

        rows_in_order, metrics_by_hoofdsysteem_naam = self._build_rows_and_metrics(
            hoofdsystemen_list=hoofdsystemen_list,
            calculation_input=calculation_input,
            energie_calculation=energie_calculation,
            eliminatie=eliminatie,
        )
        metric_lists = self._collect_metric_lists(
            hoofdsystemen_list=hoofdsystemen_list,
            metrics_by_hoofdsysteem_naam=metrics_by_hoofdsysteem_naam,
        )

        normalized_by_naam = self._calculate_normalized_metrics(
            hoofdsystemen_list=hoofdsystemen_list,
            metrics_by_hoofdsysteem_naam=metrics_by_hoofdsysteem_naam,
            metric_lists=metric_lists,
        )

        score_by_naam = self._calculate_scores(
            hoofdsystemen_list=hoofdsystemen_list,
            metrics_by_hoofdsysteem_naam=metrics_by_hoofdsysteem_naam,
            weights=weights,
            metric_lists=metric_lists,
        )

        breakdown_rows: list[MultiCriteriaAnalyseBreakdownRow] = []
        for row in rows_in_order:
            hoofdsysteem_naam = row["naam"]
            metrics = metrics_by_hoofdsysteem_naam[hoofdsysteem_naam]
            normalized = normalized_by_naam[hoofdsysteem_naam]
            totaal_score = score_by_naam.get(hoofdsysteem_naam, Decimal("0"))

            score_tco_gewogen_1_10 = (
                normalized["tco"] * weights["weging_tco"] * Decimal("10")
            )
            score_elektrisch_vermogen_gewogen_1_10 = (
                normalized["elektrisch_vermogen"]
                * weights["weging_vermogen"]
                * Decimal("10")
            )
            score_ruimte_woning_gewogen_1_10 = (
                normalized["ruimte_in_woning"]
                * weights["weging_ruimtebeslag_woning"]
                * weights["weging_ruimtebeslag"]
                * Decimal("10")
            )
            score_ruimte_binnen_gewogen_1_10 = (
                normalized["collectief_ruimte_binnen"]
                * weights["weging_ruimtebeslag_collectief_binnen"]
                * weights["weging_ruimtebeslag"]
                * Decimal("10")
            )
            score_ruimte_buiten_gewogen_1_10 = (
                normalized["collectief_ruimte_buiten"]
                * weights["weging_ruimtebeslag_collectief_buiten"]
                * weights["weging_ruimtebeslag"]
                * Decimal("10")
            )
            score_huidig_systeem_gewogen_1_10 = (
                normalized["huidig_systeem"]
                * weights["weging_aanpassing_systeem"]
                * weights["weging_aanpassing"]
                * Decimal("10")
            )
            score_vloerverwarming_gewogen_1_10 = (
                normalized["vloerverwarming"]
                * weights["weging_aanpassing_vloerverwarming"]
                * weights["weging_aanpassing"]
                * Decimal("10")
            )

            breakdown_rows.append(
                {
                    "naam": hoofdsysteem_naam,
                    "is_mogelijk": bool(row["is_mogelijk"]),
                    "score_totaal_1_10": totaal_score,
                    "tco_genormaliseerd": normalized["tco"],
                    "elektrisch_vermogen_genormaliseerd": normalized[
                        "elektrisch_vermogen"
                    ],
                    "ruimte_woning_genormaliseerd": normalized["ruimte_in_woning"],
                    "ruimte_binnen_genormaliseerd": normalized[
                        "collectief_ruimte_binnen"
                    ],
                    "ruimte_buiten_genormaliseerd": normalized[
                        "collectief_ruimte_buiten"
                    ],
                    "score_huidig_systeem": metrics["huidig_systeem"],
                    "score_huidig_systeem_genormaliseerd": normalized["huidig_systeem"],
                    "score_vloerverwarming": metrics["vloerverwarming"],
                    "score_vloerverwarming_genormaliseerd": normalized[
                        "vloerverwarming"
                    ],
                    "score_tco_gewogen_1_10": score_tco_gewogen_1_10,
                    "score_elektrisch_vermogen_gewogen_1_10": score_elektrisch_vermogen_gewogen_1_10,
                    "score_ruimte_woning_gewogen_1_10": score_ruimte_woning_gewogen_1_10,
                    "score_ruimte_binnen_gewogen_1_10": score_ruimte_binnen_gewogen_1_10,
                    "score_ruimte_buiten_gewogen_1_10": score_ruimte_buiten_gewogen_1_10,
                    "score_huidig_systeem_gewogen_1_10": score_huidig_systeem_gewogen_1_10,
                    "score_vloerverwarming_gewogen_1_10": score_vloerverwarming_gewogen_1_10,
                }
            )

        return breakdown_rows

    def _calculate_subsysteem_tco(
        self,
        *,
        hoofdsysteem: Hoofdsysteem,
        energie_calculation: EnergieCalculatorFullResult,
        calculation_input: GebruikersInvoer,
    ) -> Decimal:
        subsysteem_tco = Decimal("0")
        for subsysteem in hoofdsysteem.subsystemen.all():
            if not subsysteem.calculation_method:
                continue
            subs_full = subsysteem.calculate(
                scenarios=(ScenarioKeuze.MIDDEN,),
                energie_calculation=energie_calculation,
                calculation_input=calculation_input,
            )
            subsysteem_tco += subs_full.by_scenario[ScenarioKeuze.MIDDEN].berekening.tco
        return subsysteem_tco

    def _calculate_eliminatie(
        self,
        *,
        eliminatie: Eliminatie,
        calculation_input: GebruikersInvoer,
        hoofdsysteem_naam: str,
    ) -> tuple[bool, list[str]]:
        elim = eliminatie.calculate(calculation_input, hoofdsysteem_naam)
        is_mogelijk = bool(elim.get("is_mogelijk"))
        redenen_any = elim.get("redenen")
        if not isinstance(redenen_any, list):
            redenen_any = []
        redenen = cast(list[str], redenen_any)
        return is_mogelijk, redenen

    def _build_row(
        self,
        *,
        hoofdsysteem: Hoofdsysteem,
        tco_midden: Decimal,
        score: Decimal,
        is_mogelijk: bool,
        redenen: list[str],
    ) -> MultiCriteriaAnalyseRow:
        return {
            "naam": hoofdsysteem.naam,
            "beschrijving": str(hoofdsysteem.beschrijving or ""),
            "tco": float(tco_midden),
            "score": round(score),
            "kosten_per_woning_per_jaar": float(tco_midden / Decimal("30")),
            "is_mogelijk": is_mogelijk,
            "redenen": redenen,
        }

    def _build_metrics(
        self,
        *,
        hoofdsysteem: Hoofdsysteem,
        full,
        calculation_input: GebruikersInvoer,
        tco: Decimal,
    ) -> MultiCriteriaAnalyseMetrics:
        eliminatie_kengetal = EliminatieKengetal.objects.get(naam=hoofdsysteem.naam)
        ruimte_in_woning = self._to_decimal(
            eliminatie_kengetal.benodigde_ruimte_in_woning_m2
        )
        collectief_ruimte_binnen = self._to_decimal(
            _get_collectieve_ruimte(
                CollectieveRuimteBinnen,
                hoofdsysteem_naam=hoofdsysteem.naam,
                aantal_woningen=calculation_input.aantal_woningen,
            )
        )
        collectief_ruimte_buiten = self._to_decimal(
            _get_collectieve_ruimte(
                CollectieveRuimteBuiten,
                hoofdsysteem_naam=hoofdsysteem.naam,
                aantal_woningen=calculation_input.aantal_woningen,
            )
        )

        mca_kengetal = MultiCriteriaAnalyseKengetal.objects.get(
            hoofdsysteem__naam=hoofdsysteem.naam
        )
        huidig_systeem = (
            mca_kengetal.huidig_systeem_collectief
            if calculation_input.huidig_systeem == HuidigSysteemChoices.COLLECTIEF
            else mca_kengetal.huidig_systeem_individueel
        )
        vloerverwarming = (
            mca_kengetal.vloerverwarming_aanwezig_waar
            if calculation_input.vloerverwarming_aanwezig
            else mca_kengetal.vloerverwarming_aanwezig_onwaar
        )

        elektrisch_vermogen = self._to_decimal(
            full.by_scenario[ScenarioKeuze.MIDDEN].elektrisch_vermogen
        )

        return {
            "tco": self._to_decimal(tco),
            "elektrisch_vermogen": elektrisch_vermogen,
            "ruimte_in_woning": ruimte_in_woning,
            "collectief_ruimte_binnen": collectief_ruimte_binnen,
            "collectief_ruimte_buiten": collectief_ruimte_buiten,
            "huidig_systeem": self._to_decimal(huidig_systeem),
            "vloerverwarming": self._to_decimal(vloerverwarming),
        }

    def _build_rows_and_metrics(
        self,
        *,
        hoofdsystemen_list: list[Hoofdsysteem],
        calculation_input: GebruikersInvoer,
        energie_calculation: EnergieCalculatorFullResult,
        eliminatie: Eliminatie,
    ) -> tuple[list[MultiCriteriaAnalyseRow], dict[str, MultiCriteriaAnalyseMetrics]]:
        rows_in_order: list[MultiCriteriaAnalyseRow] = []
        metrics_by_hoofdsysteem_naam: dict[str, MultiCriteriaAnalyseMetrics] = {}

        for hoofdsysteem in hoofdsystemen_list:
            full = hoofdsysteem.calculate(energie_calculation=energie_calculation)
            subsysteem_tco = self._calculate_subsysteem_tco(
                hoofdsysteem=hoofdsysteem,
                energie_calculation=energie_calculation,
                calculation_input=calculation_input,
            )
            tco_midden = (
                full.by_scenario[ScenarioKeuze.MIDDEN].tco + subsysteem_tco
            ).quantize(Decimal("0.01"))

            is_mogelijk, redenen = self._calculate_eliminatie(
                eliminatie=eliminatie,
                calculation_input=calculation_input,
                hoofdsysteem_naam=hoofdsysteem.naam,
            )

            row = self._build_row(
                hoofdsysteem=hoofdsysteem,
                tco_midden=tco_midden,
                score=Decimal("0"),
                is_mogelijk=is_mogelijk,
                redenen=redenen,
            )
            rows_in_order.append(row)

            metrics_by_hoofdsysteem_naam[hoofdsysteem.naam] = self._build_metrics(
                hoofdsysteem=hoofdsysteem,
                full=full,
                calculation_input=calculation_input,
                tco=tco_midden,
            )

        return rows_in_order, metrics_by_hoofdsysteem_naam

    def _collect_metric_lists(
        self,
        *,
        hoofdsystemen_list: list[Hoofdsysteem],
        metrics_by_hoofdsysteem_naam: dict[str, MultiCriteriaAnalyseMetrics],
    ) -> dict[str, list[Decimal]]:
        tco_values: list[Decimal] = []
        elektrisch_vermogen_values: list[Decimal] = []
        ruimte_in_woning_values: list[Decimal] = []
        collectief_ruimte_binnen_values: list[Decimal] = []
        collectief_ruimte_buiten_values: list[Decimal] = []
        huidig_systeem_values: list[Decimal] = []
        vloerverwarming_values: list[Decimal] = []

        for hoofdsysteem in hoofdsystemen_list:
            metrics = metrics_by_hoofdsysteem_naam[hoofdsysteem.naam]
            tco_values.append(metrics["tco"])
            elektrisch_vermogen_values.append(metrics["elektrisch_vermogen"])
            ruimte_in_woning_values.append(metrics["ruimte_in_woning"])
            collectief_ruimte_binnen_values.append(metrics["collectief_ruimte_binnen"])
            collectief_ruimte_buiten_values.append(metrics["collectief_ruimte_buiten"])
            huidig_systeem_values.append(metrics["huidig_systeem"])
            vloerverwarming_values.append(metrics["vloerverwarming"])

        return {
            "tco": tco_values,
            "elektrisch_vermogen": elektrisch_vermogen_values,
            "ruimte_in_woning": ruimte_in_woning_values,
            "collectief_ruimte_binnen": collectief_ruimte_binnen_values,
            "collectief_ruimte_buiten": collectief_ruimte_buiten_values,
            "huidig_systeem": huidig_systeem_values,
            "vloerverwarming": vloerverwarming_values,
        }

    def _calculate_normalized_metrics(
        self,
        *,
        hoofdsystemen_list: list[Hoofdsysteem],
        metrics_by_hoofdsysteem_naam: dict[str, MultiCriteriaAnalyseMetrics],
        metric_lists: dict[str, list[Decimal]],
    ) -> dict[str, dict[str, Decimal]]:
        normalized_by_naam: dict[str, dict[str, Decimal]] = {}
        for hoofdsysteem in hoofdsystemen_list:
            naam = hoofdsysteem.naam
            metrics = metrics_by_hoofdsysteem_naam[naam]
            normalized_by_naam[naam] = {
                "tco": self._inverse_min_max_normalize(
                    metric_lists["tco"], metrics["tco"]
                ),
                "elektrisch_vermogen": self._inverse_min_max_normalize(
                    metric_lists["elektrisch_vermogen"],
                    metrics["elektrisch_vermogen"],
                ),
                "ruimte_in_woning": self._inverse_min_max_normalize(
                    metric_lists["ruimte_in_woning"],
                    metrics["ruimte_in_woning"],
                ),
                "collectief_ruimte_binnen": self._inverse_min_max_normalize(
                    metric_lists["collectief_ruimte_binnen"],
                    metrics["collectief_ruimte_binnen"],
                ),
                "collectief_ruimte_buiten": self._inverse_min_max_normalize(
                    metric_lists["collectief_ruimte_buiten"],
                    metrics["collectief_ruimte_buiten"],
                ),
                "huidig_systeem": self._inverse_min_max_normalize(
                    metric_lists["huidig_systeem"],
                    metrics["huidig_systeem"],
                ),
                "vloerverwarming": self._inverse_min_max_normalize(
                    metric_lists["vloerverwarming"],
                    metrics["vloerverwarming"],
                ),
            }
        return normalized_by_naam

    def _calculate_scores(
        self,
        *,
        hoofdsystemen_list: list[Hoofdsysteem],
        metrics_by_hoofdsysteem_naam: dict[str, MultiCriteriaAnalyseMetrics],
        weights: dict[str, Decimal],
        metric_lists: dict[str, list[Decimal]],
    ) -> dict[str, Decimal]:
        score_by_hoofdsysteem_naam: dict[str, Decimal] = {}

        for hoofdsysteem in hoofdsystemen_list:
            metrics = metrics_by_hoofdsysteem_naam[hoofdsysteem.naam]

            tco_normalized = self._inverse_min_max_normalize(
                metric_lists["tco"],
                metrics["tco"],
            )
            elektrisch_vermogen_normalized = self._inverse_min_max_normalize(
                metric_lists["elektrisch_vermogen"],
                metrics["elektrisch_vermogen"],
            )
            ruimte_in_woning_normalized = self._inverse_min_max_normalize(
                metric_lists["ruimte_in_woning"],
                metrics["ruimte_in_woning"],
            )
            collectief_ruimte_binnen_normalized = self._inverse_min_max_normalize(
                metric_lists["collectief_ruimte_binnen"],
                metrics["collectief_ruimte_binnen"],
            )
            collectief_ruimte_buiten_normalized = self._inverse_min_max_normalize(
                metric_lists["collectief_ruimte_buiten"],
                metrics["collectief_ruimte_buiten"],
            )

            score_tco = tco_normalized * weights["weging_tco"]
            score_vermogen = elektrisch_vermogen_normalized * weights["weging_vermogen"]
            score_ruimte_in_woning = (
                ruimte_in_woning_normalized
                * weights["weging_ruimtebeslag_woning"]
                * weights["weging_ruimtebeslag"]
            )
            score_collectief_binnen = (
                collectief_ruimte_binnen_normalized
                * weights["weging_ruimtebeslag_collectief_binnen"]
                * weights["weging_ruimtebeslag"]
            )
            score_collectief_buiten = (
                collectief_ruimte_buiten_normalized
                * weights["weging_ruimtebeslag_collectief_buiten"]
                * weights["weging_ruimtebeslag"]
            )
            score_aanpassing_systeem = (
                metrics["huidig_systeem"]
                * weights["weging_aanpassing_systeem"]
                * weights["weging_aanpassing"]
            )
            score_aanpassing_vloerverwarming = (
                metrics["vloerverwarming"]
                * weights["weging_aanpassing_vloerverwarming"]
                * weights["weging_aanpassing"]
            )
            totaal_score = (
                score_tco
                + score_vermogen
                + score_ruimte_in_woning
                + score_collectief_binnen
                + score_collectief_buiten
                + score_aanpassing_systeem
                + score_aanpassing_vloerverwarming
            ) * Decimal("10")

            score_by_hoofdsysteem_naam[hoofdsysteem.naam] = totaal_score

        return score_by_hoofdsysteem_naam

    def _build_items(
        self,
        *,
        rows_in_order: list[MultiCriteriaAnalyseRow],
        score_by_hoofdsysteem_naam: dict[str, Decimal],
    ) -> list[tuple[MultiCriteriaAnalyseSortKey, MultiCriteriaAnalyseRow]]:
        items: list[tuple[MultiCriteriaAnalyseSortKey, MultiCriteriaAnalyseRow]] = []

        for row in rows_in_order:
            hoofdsysteem_naam = row["naam"]
            score = score_by_hoofdsysteem_naam.get(hoofdsysteem_naam, Decimal("0"))
            row["score"] = round(score)

            sort_key: MultiCriteriaAnalyseSortKey = (
                not bool(row["is_mogelijk"]),
                -score,
                hoofdsysteem_naam,
            )
            items.append((sort_key, row))

        return items

    def _get_weights(self) -> dict[str, Decimal]:
        return {
            "weging_tco": self._to_decimal(
                McdaHoofdcriterium.objects.get(naam="TCO").wegingsfactor
            ),
            "weging_vermogen": self._to_decimal(
                McdaHoofdcriterium.objects.get(naam="Vermogen").wegingsfactor
            ),
            "weging_ruimtebeslag": self._to_decimal(
                McdaHoofdcriterium.objects.get(naam="Ruimtebeslag").wegingsfactor
            ),
            "weging_aanpassing": self._to_decimal(
                McdaHoofdcriterium.objects.get(naam="Impact aanpassingen").wegingsfactor
            ),
            "weging_ruimtebeslag_woning": self._to_decimal(
                McdaSubcriterium.objects.get(naam="Woning").relatieve_wegingsfactor
            ),
            "weging_ruimtebeslag_collectief_binnen": self._to_decimal(
                McdaSubcriterium.objects.get(naam="COL binnen").relatieve_wegingsfactor
            ),
            "weging_ruimtebeslag_collectief_buiten": self._to_decimal(
                McdaSubcriterium.objects.get(naam="COL buiten").relatieve_wegingsfactor
            ),
            "weging_aanpassing_systeem": self._to_decimal(
                McdaSubcriterium.objects.get(
                    naam="Aanpassingen - systeem"
                ).relatieve_wegingsfactor
            ),
            "weging_aanpassing_vloerverwarming": self._to_decimal(
                McdaSubcriterium.objects.get(
                    naam="Aanpassingen - Vloerverwarming"
                ).relatieve_wegingsfactor
            ),
        }

    @staticmethod
    def _to_decimal(value: object) -> Decimal:
        return Decimal(str(value))

    # (Highest value - input) / (Highest value - Lowest value)
    @staticmethod
    def _inverse_min_max_normalize(values: list[Decimal], input: Decimal) -> Decimal:
        if not values:
            return Decimal("0")

        max_val = max(values)
        min_val = min(values)
        if max_val == min_val:
            return Decimal("0")
        return (max_val - input) / (max_val - min_val)


def _get_collectieve_ruimte(
    model,
    *,
    hoofdsysteem_naam: str,
    aantal_woningen: int,
) -> Decimal:
    value = (
        model.objects.filter(
            hoofdsysteem__naam=hoofdsysteem_naam,
            n_min__lte=aantal_woningen,
        )
        .filter(Q(n_max__isnull=True) | Q(n_max__gte=aantal_woningen))
        .order_by("-n_min")
        .values_list("vereiste_m2", flat=True)
        .first()
    )
    if value is None:
        raise model.DoesNotExist(
            f"Missing {model.__name__} for hoofdsysteem={hoofdsysteem_naam!r}, aantal_woningen={aantal_woningen}"
        )
    return value
