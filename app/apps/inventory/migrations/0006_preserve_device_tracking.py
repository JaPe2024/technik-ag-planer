from django.db import migrations


def preserve_devices(apps, schema_editor):
    Material = apps.get_model("inventory", "Material")
    Unit = apps.get_model("inventory", "MaterialUnit")
    alias = schema_editor.connection.alias
    Material.objects.using(alias).filter(pk__in=Unit.objects.using(alias).values("material_id")).update(tracking="individual")


class Migration(migrations.Migration):
    dependencies = [("inventory", "0005_material_tracking_plannedmaterial_issued_quantity_and_more")]
    operations = [migrations.RunPython(preserve_devices, migrations.RunPython.noop)]
