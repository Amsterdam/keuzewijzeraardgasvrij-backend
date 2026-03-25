from django.apps import AppConfig


class CalculationsConfig(AppConfig):
    # New module path (renamed from apps.calculation_inputs).
    name = "apps.calculations"

    # Keep the historical app label so existing migrations/DB tables remain valid.
    label = "calculation_inputs"

    verbose_name = "Calculations"
