from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='attendancerecord',
            constraint=models.UniqueConstraint(
                condition=models.Q(('check_out_time__isnull', True)),
                fields=('user',),
                name='unique_open_attendance_session_per_user',
            ),
        ),
    ]
