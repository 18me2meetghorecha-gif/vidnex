from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add bio and phone to UserProfile
        migrations.AddField(
            model_name='userprofile',
            name='bio',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='phone',
            field=models.CharField(blank=True, default='', max_length=50),
            preserve_default=False,
        ),
        # Add category and default_timeline to Project
        migrations.AddField(
            model_name='project',
            name='category',
            field=models.CharField(blank=True, default='', max_length=80),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='project',
            name='default_timeline',
            field=models.CharField(default='8 weeks', max_length=80),
        ),
        # Extend Bid status choices and add updated_at
        migrations.AlterField(
            model_name='bid',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('shortlisted', 'Shortlisted'),
                    ('selected', 'Selected'),
                    ('allocated', 'Allocated'),
                    ('in_progress', 'In Progress'),
                    ('submitted', 'Submitted'),
                    ('completed', 'Completed'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='bid',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Make VerificationDetail file fields optional
        migrations.AlterField(
            model_name='verificationdetail',
            name='resume',
            field=models.FileField(blank=True, upload_to='verification/resume/'),
        ),
        migrations.AlterField(
            model_name='verificationdetail',
            name='certificates',
            field=models.FileField(blank=True, upload_to='verification/certificates/'),
        ),
        migrations.AlterField(
            model_name='verificationdetail',
            name='id_proof',
            field=models.FileField(blank=True, upload_to='verification/id_proof/'),
        ),
        # Extend WithdrawRequest status choices
        migrations.AlterField(
            model_name='withdrawrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('completed', 'Completed'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        # Create Assignment model
        migrations.CreateModel(
            name='Assignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timeline', models.CharField(default='8 weeks', max_length=120)),
                ('project_details', models.TextField(blank=True)),
                ('expected_submission_date', models.CharField(blank=True, max_length=32)),
                ('allocated_earning', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('released_earning', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('submission_response', models.TextField(blank=True)),
                ('submission_file_name', models.CharField(blank=True, max_length=200)),
                ('submission_file', models.FileField(blank=True, null=True, upload_to='submissions/')),
                ('submission_date', models.CharField(blank=True, max_length=32)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('review_status', models.CharField(blank=True, default='pending', max_length=30)),
                ('review_comment', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(default='allocated', max_length=20)),
                ('allocated_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bid', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignment',
                    to='core.bid',
                )),
            ],
        ),
        # Create SystemMail model
        migrations.CreateModel(
            name='SystemMail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=150)),
                ('body', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('event', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='system_mails',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
