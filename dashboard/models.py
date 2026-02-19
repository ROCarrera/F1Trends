from django.db import models


class Season(models.Model):
    year = models.PositiveIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year"]

    def __str__(self) -> str:
        return str(self.year)


class Race(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="races")
    round = models.PositiveIntegerField()
    race_name = models.CharField(max_length=255)
    circuit_name = models.CharField(max_length=255, blank=True, default="")
    date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["season__year", "round"]
        constraints = [
            models.UniqueConstraint(fields=["season", "round"], name="unique_race_season_round")
        ]

    def __str__(self) -> str:
        return f"{self.season.year} R{self.round} {self.race_name}"


class Driver(models.Model):
    driver_id = models.CharField(max_length=64, unique=True)
    given_name = models.CharField(max_length=128)
    family_name = models.CharField(max_length=128)
    code = models.CharField(max_length=8, null=True, blank=True)
    permanent_number = models.CharField(max_length=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["family_name", "given_name"]

    def __str__(self) -> str:
        return f"{self.given_name} {self.family_name}"


class Constructor(models.Model):
    constructor_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    nationality = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Winner(models.Model):
    race = models.OneToOneField(Race, on_delete=models.CASCADE, related_name="winner")
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="wins")
    constructor = models.ForeignKey(
        Constructor, on_delete=models.CASCADE, related_name="wins"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["race__season__year", "race__round"]

    def __str__(self) -> str:
        return f"{self.race}: {self.driver} ({self.constructor})"
