# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-12-07 09:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_personalisation", "0003_auto_20161206_1005"),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="persistent",
            field=models.BooleanField(
                default=False, help_text="Should the segment persist between visits?"
            ),
        ),
    ]
