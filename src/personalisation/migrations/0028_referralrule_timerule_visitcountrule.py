# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-18 13:45
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import modelcluster.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('wagtailcore', '0030_index_on_pagerevision_created_at'),
        ('personalisation', '0027_auto_20161118_1443'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralRule',
            fields=[
                ('referral_rule_id', models.AutoField(default=0, primary_key=True, serialize=False)),
                ('regex_string', models.TextField(verbose_name='Regex string to match the referer with')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_personalisation.referralrule_set+', to='contenttypes.ContentType')),
                ('segment', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalisation_referralrule_related', related_query_name='personalisation_referralrules', to='personalisation.Segment')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TimeRule',
            fields=[
                ('time_rule_id', models.AutoField(default=0, primary_key=True, serialize=False)),
                ('start_time', models.TimeField(verbose_name='Starting time')),
                ('end_time', models.TimeField(verbose_name='Ending time')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_personalisation.timerule_set+', to='contenttypes.ContentType')),
                ('segment', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalisation_timerule_related', related_query_name='personalisation_timerules', to='personalisation.Segment')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='VisitCountRule',
            fields=[
                ('visit_count_rule_id', models.AutoField(default=0, primary_key=True, serialize=False)),
                ('operator', models.CharField(choices=[('more_than', 'More than'), ('less_than', 'Less than'), ('equal_to', 'Equal to')], default='ht', max_length=20)),
                ('count', models.PositiveSmallIntegerField(default=0, null=True)),
                ('counted_page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='wagtailcore.Page')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_personalisation.visitcountrule_set+', to='contenttypes.ContentType')),
                ('segment', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='personalisation_visitcountrule_related', related_query_name='personalisation_visitcountrules', to='personalisation.Segment')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]