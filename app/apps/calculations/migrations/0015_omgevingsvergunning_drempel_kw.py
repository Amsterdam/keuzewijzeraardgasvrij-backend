from decimal import Decimal

from django.db import migrations


def add_omgevingsvergunning_drempel_kw(apps, schema_editor):
    Conversie = apps.get_model("calculation_inputs", "Conversie")
    Conversie.objects.update_or_create(
        naam="omgevingsvergunning_drempel_kw",
        defaults={"waarde": Decimal("70")},
    )


def remove_omgevingsvergunning_drempel_kw(apps, schema_editor):
    Conversie = apps.get_model("calculation_inputs", "Conversie")
    Conversie.objects.filter(naam="omgevingsvergunning_drempel_kw").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("calculation_inputs", "0014_gebruikersinvoer_created_at"),
    ]

    operations = [
        migrations.RunPython(
            add_omgevingsvergunning_drempel_kw,
            remove_omgevingsvergunning_drempel_kw,
        ),
    ]
