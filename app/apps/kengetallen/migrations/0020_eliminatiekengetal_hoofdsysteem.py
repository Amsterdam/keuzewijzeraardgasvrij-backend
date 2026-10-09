import django.db.models.deletion
from django.db import migrations, models


def link_hoofdsysteem(apps, schema_editor):
    EliminatieKengetal = apps.get_model("kengetallen", "EliminatieKengetal")
    Hoofdsysteem = apps.get_model("systemen", "Hoofdsysteem")

    for kengetal in EliminatieKengetal.objects.all():
        try:
            kengetal.hoofdsysteem = Hoofdsysteem.objects.get(naam=kengetal.naam)
        except Hoofdsysteem.DoesNotExist:
            raise RuntimeError(
                f"EliminatieKengetal(pk={kengetal.pk}, naam={kengetal.naam!r}) "
                "kan niet aan een Hoofdsysteem gekoppeld worden: geen Hoofdsysteem "
                "met die naam. Corrigeer de naam voordat je deze migratie draait."
            )
        kengetal.save(update_fields=["hoofdsysteem"])


def restore_naam(apps, schema_editor):
    EliminatieKengetal = apps.get_model("kengetallen", "EliminatieKengetal")

    for kengetal in EliminatieKengetal.objects.select_related("hoofdsysteem"):
        kengetal.naam = kengetal.hoofdsysteem.naam
        kengetal.save(update_fields=["naam"])


class Migration(migrations.Migration):

    dependencies = [
        ("kengetallen", "0019_collectieveruimtetuin"),
        ("systemen", "0008_hoofdsysteem_beschrijving_url_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="eliminatiekengetal",
            name="hoofdsysteem",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eliminatie_kengetal",
                to="systemen.hoofdsysteem",
            ),
        ),
        migrations.RunPython(link_hoofdsysteem, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="eliminatiekengetal",
            name="hoofdsysteem",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="eliminatie_kengetal",
                to="systemen.hoofdsysteem",
            ),
        ),
        migrations.AlterModelOptions(
            name="eliminatiekengetal",
            options={
                "ordering": ["hoofdsysteem", "woningen_min"],
                "verbose_name": "Eliminatie kengetal",
                "verbose_name_plural": "Eliminatie kengetallen",
            },
        ),
        migrations.AlterField(
            model_name="eliminatiekengetal",
            name="naam",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_naam),
        migrations.RemoveField(
            model_name="eliminatiekengetal",
            name="naam",
        ),
    ]
