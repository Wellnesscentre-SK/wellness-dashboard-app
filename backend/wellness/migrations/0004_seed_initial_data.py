from django.db import migrations


def seed_users(apps, schema_editor):
    User = apps.get_model("wellness", "User")
    if not User.objects.exists():
        User.objects.create_superuser(
            username="admin",
            email="admin@wellness.local",
            password="wellness2026",
            role="super_admin",
        )
        User.objects.create_user(
            username="user",
            email="user@wellness.local",
            password="wellness2026",
            role="admin",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("wellness", "0003_rebuild_secondary_verticals"),
    ]

    operations = [
        migrations.RunPython(seed_users, migrations.RunPython.noop),
    ]
