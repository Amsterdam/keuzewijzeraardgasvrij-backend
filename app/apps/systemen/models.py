from django.db import models


class Hoofdsysteem(models.Model):
    naam = models.CharField(max_length=255)
    beschrijving = models.TextField(blank=True, null=True)
    subsystemen = models.ManyToManyField("Subsysteem", related_name="hoofdsystemen")
    beschrijving_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Hoofdsysteem"
        verbose_name_plural = "Hoofdsystemen"

    def __str__(self):
        return self.naam


class SubsysteemType(models.TextChoices):
    KENGETAL = "kengetal", "Kengetal"
    STADSWARMTE = "stadswarmte", "Stadswarmte"


class Subsysteem(models.Model):
    naam = models.CharField(max_length=255)

    type = models.CharField(
        max_length=20, choices=SubsysteemType.choices, default=SubsysteemType.KENGETAL
    )

    class Meta:
        verbose_name = "Subsysteem"
        verbose_name_plural = "Subsystemen"

    def __str__(self):
        return self.naam
