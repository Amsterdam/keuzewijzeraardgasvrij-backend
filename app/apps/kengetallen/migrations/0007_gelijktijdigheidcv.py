from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kengetallen", "0006_stadsverwarmingkengetal"),
    ]

    operations = [
        migrations.CreateModel(
            name="GelijktijdigheidCV",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("n_min", models.IntegerField()),
                ("n_max", models.IntegerField(blank=True, null=True)),
                ("factor", models.DecimalField(decimal_places=9, max_digits=18)),
            ],
            options={
                "verbose_name": "GelijktijdigheidCV",
                "verbose_name_plural": "GelijktijdigheidCV",
                "ordering": ["n_min"],
            },
        ),
        migrations.AddConstraint(
            model_name="gelijktijdigheidcv",
            constraint=models.UniqueConstraint(
                fields=("n_min", "n_max"),
                name="uniek_n_min_n_max_gelijktijdigheidcv",
            ),
        ),
    ]
