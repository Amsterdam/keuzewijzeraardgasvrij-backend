from django.db import migrations, models


def mark_systems_without_electricity(apps, schema_editor):
    Hoofdsysteem = apps.get_model("systemen", "Hoofdsysteem")
    Hoofdsysteem.objects.filter(
        models.Q(naam__icontains="warmtelevering")
        | models.Q(naam__icontains="warmtenet")
    ).update(verbruikt_elektriciteit=False)


class Migration(migrations.Migration):

    dependencies = [
        ("systemen", "0008_hoofdsysteem_beschrijving_url_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="hoofdsysteem",
            name="verbruikt_elektriciteit",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(
            mark_systems_without_electricity,
            migrations.RunPython.noop,
        ),
    ]
