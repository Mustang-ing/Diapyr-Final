# Generated by Django 5.1.7 on 2025-07-07 08:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0703_participant_age_participant_domaine_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="debat",
            name="criteres",
        ),
    ]
