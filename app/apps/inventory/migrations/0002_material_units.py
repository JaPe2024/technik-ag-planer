from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="MaterialUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=100, unique=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="organizations.organization", verbose_name="AG")),
                ("material", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="units", to="inventory.material")),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="UnitIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to="organizations.organization", verbose_name="AG")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="issues", to="inventory.materialunit")),
                ("production", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="productions.production")),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("returned_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("unit",), condition=models.Q(returned_at__isnull=True), name="unit_one_open_issue")]},
        ),
    ]
