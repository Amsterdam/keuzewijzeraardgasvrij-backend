from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "calculation_inputs",
            "0013_remove_gebruikersinvoer_elektriciteitsverbruik_per_woning_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="gebruikersinvoer",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
