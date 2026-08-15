import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enrollment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LivenessChallenge',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('purpose', models.CharField(choices=[('enrollment', 'Face enrollment'), ('attendance', 'Attendance verification')], max_length=20)),
                ('actions', models.JSONField(default=list)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='liveness_challenges', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'purpose', '-created_at'], name='enrollment_user_id_e1751d_idx'),
                    models.Index(fields=['expires_at', 'used_at'], name='enrollment_expires_10841d_idx'),
                ],
            },
        ),
    ]
