from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_unique ON auth_user (email);",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_unique;",
        ),
    ]
