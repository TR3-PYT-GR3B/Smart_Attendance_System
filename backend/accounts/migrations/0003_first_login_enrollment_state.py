from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='biometric_consent_version',
            field=models.CharField(
                blank=True,
                help_text='Version of the biometric notice accepted by the worker.',
                max_length=50,
                verbose_name='biometric consent version',
            ),
        ),
        # Existing development accounts keep working. The following AlterField
        # operations make the secure first-login state the default for every
        # account created after this migration is applied.
        migrations.AddField(
            model_name='user',
            name='face_enrollment_allowed',
            field=models.BooleanField(default=False, verbose_name='face enrollment allowed'),
        ),
        migrations.AddField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(default=False, verbose_name='must change password'),
        ),
        migrations.AlterField(
            model_name='user',
            name='face_enrollment_allowed',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'One-time authorization to bind a face. Cleared after enrollment; '
                    'an administrator must explicitly reset it before re-enrollment.'
                ),
                verbose_name='face enrollment allowed',
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(
                default=True,
                help_text='Require the administrator-issued password to be replaced on first login.',
                verbose_name='must change password',
            ),
        ),
    ]
