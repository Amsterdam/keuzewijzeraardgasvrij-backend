from django.contrib import admin

from .models import CalculationInput


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(CalculationInput)
class CalculationInputAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CalculationInput)
