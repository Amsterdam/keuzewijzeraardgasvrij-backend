from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calculation_inputs", "0015_omgevingsvergunning_drempel_kw"),
    ]

    operations = [
        migrations.RenameField(
            model_name="gebruikersinvoer",
            old_name="beschikbare_collectieve_ruimte_buiten_m2",
            new_name="beschikbare_collectieve_ruimte_tuin_m2",
        ),
        migrations.AddField(
            model_name="gebruikersinvoer",
            name="beschikbare_collectieve_ruimte_dak_m2",
            field=models.DecimalField(decimal_places=9, default=0, max_digits=18),
        ),
    ]
