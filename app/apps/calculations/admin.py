from django.contrib import admin

from .models import CalculationInput, Conversie


def get_all_field_names(model):
    return [field.name for field in model._meta.fields]


@admin.register(CalculationInput)
class CalculationInputAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(CalculationInput)


@admin.register(Conversie)
class ConversieAdmin(admin.ModelAdmin):
    list_display = get_all_field_names(Conversie)
