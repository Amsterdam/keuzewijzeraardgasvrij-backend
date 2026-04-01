from __future__ import annotations

from decimal import Decimal
from numbers import Number
from typing import Final, Iterable, Literal, TypedDict

from apps.kengetallen.models import AlgemeenKengetal, ScenarioKeuze

from .models import CalculationInput, Conversie


EnergieTypeValue = Literal["tapwater", "cv", "gkw"]


class EnergieType:
    """Constants used to choose which energy demand is calculated."""

    TAP: Final[EnergieTypeValue] = "tapwater"
    CV: Final[EnergieTypeValue] = "cv"
    GKW: Final[EnergieTypeValue] = "gkw"


CalculationResult = TypedDict(
    "CalculationResult",
    {
        "Type": EnergieTypeValue,
        "Scenario": str,
        "Vermogen warmte [kW/woning]": Decimal,
        "Vermogen warmte [kW/vve]": Decimal,
        "Gas [m³/j]": Decimal,
        "Capaciteit warmte [kWh/j/w]": Decimal,
        "Capaciteit warmte [GJ/j/w]": Decimal,
    },
)


class EnergieCalculatorFullResult(TypedDict):
    results: list[CalculationResult]
    by_scenario: dict[str, dict[EnergieTypeValue, CalculationResult]]


class EnergieCalculator:
    """Calculator for energy/gas demand metrics.

    Conversion factors are stored in the `Conversie` table (loaded via fixtures).
    """

    def calculate(
        self,
        calculation_input: CalculationInput,
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
        """Calculate all energie types for all scenarios.

        This centralizes the scenario + energie_type iteration so callers don't need
        to loop and invoke the calculator repeatedly.
        """

        conversie_m3gas_naar_kwh = Conversie.objects.get(naam="m3gas_naar_kwh").waarde
        conversie_kwh_naar_gj = Conversie.objects.get(naam="kwh_naar_gj").waarde

        results: list[CalculationResult] = []
        by_scenario: dict[str, dict[EnergieTypeValue, CalculationResult]] = {}

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

        return {"results": results, "by_scenario": by_scenario}

    def _calculate_single(
        self,
        energie_type: EnergieTypeValue,
        scenario: ScenarioKeuze,
        calculation_input: CalculationInput,
        *,
        conversie_m3gas_naar_kwh: Decimal,
        conversie_kwh_naar_gj: Decimal,
    ) -> CalculationResult:
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

        aantal_woningen = self._to_decimal(calculation_input.aantal_woningen)

        return {
            "Type": energie_type,
            "Scenario": str(scenario),
            "Vermogen warmte [kW/woning]": result["vermogen_warmte_kw_per_woning"],
            "Vermogen warmte [kW/vve]": result["vermogen_warmte_kw_per_woning"]
            * aantal_woningen,
            "Gas [m³/j]": result["gas_m3_per_year"],
            "Capaciteit warmte [kWh/j/w]": result[
                "capaciteit_warmte_kwh_per_year_per_woning"
            ],
            "Capaciteit warmte [GJ/j/w]": result[
                "capaciteit_warmte_gj_per_year_per_woning"
            ],
        }

    def _calculate_tap(
        self,
        scenario: ScenarioKeuze,
        calculation_input: CalculationInput,
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
        gelijktijdigheid_tap = 1 / Decimal(calculation_input.aantal_woningen).sqrt()
        percentage_ruimteverwarming = kengetallen["percentage_ruimteverwarming"]
        rendement_gasketel = kengetallen["rendement_gasketel"]

        vermogen_warmte_kw_per_woning = warmtevraag_kw_per_woning * gelijktijdigheid_tap

        tapwater_factor = (
            Decimal(1) if calculation_input.tapwater_op_gas else Decimal(0)
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
            * (Decimal(1) - percentage_ruimteverwarming)
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
        calculation_input: CalculationInput,
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
            else Decimal(1)
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
        calculation_input: CalculationInput,
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
            "gas_m3_per_year": Decimal(0),
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
