from django.db import migrations, models


def mark_systems_without_electricity(apps, schema_editor):
    MultiCriteriaAnalyseKengetal = apps.get_model(
        "kengetallen", "MultiCriteriaAnalyseKengetal"
    )
    MultiCriteriaAnalyseKengetal.objects.filter(
        models.Q(hoofdsysteem__naam__icontains="warmtelevering")
        | models.Q(hoofdsysteem__naam__icontains="warmtenet")
    ).update(verbruikt_elektriciteit=False)


class Migration(migrations.Migration):

    dependencies = [
        ("kengetallen", "0020_eliminatiekengetal_hoofdsysteem"),
    ]

    operations = [
        migrations.AddField(
            model_name="multicriteriaanalysekengetal",
            name="verbruikt_elektriciteit",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(
            mark_systems_without_electricity,
            migrations.RunPython.noop,
        ),
    ]
