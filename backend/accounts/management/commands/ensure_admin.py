"""Create the initial administrator once, without exposing a CLI password."""

import os

from django.core.management.base import BaseCommand, CommandError

from accounts.models import EmploymentStatus, User, UserRole


class Command(BaseCommand):
    help = 'Create or repair the administrator configured in environment variables.'

    def handle(self, *args, **options):
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', '').strip().lower()
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', '')
        reset_password = os.getenv(
            'DJANGO_SUPERUSER_RESET_PASSWORD',
            '',
        ).strip().lower() in {'1', 'true', 'yes', 'on'}

        if not email or not password:
            raise CommandError(
                'DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD are required.'
            )

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            User.objects.create_superuser(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Created administrator {email}.'))
            return

        changed_fields = []
        desired_values = {
            'role': UserRole.ADMIN,
            'employment_status': EmploymentStatus.ACTIVE,
            'is_active': True,
            'is_approved': True,
            'is_staff': True,
            'is_superuser': True,
            'must_change_password': False,
            'face_enrollment_allowed': False,
        }
        for field, desired_value in desired_values.items():
            if getattr(user, field) != desired_value:
                setattr(user, field, desired_value)
                changed_fields.append(field)

        if reset_password:
            user.set_password(password)
            changed_fields.append('password')

        if changed_fields:
            user.save(update_fields=changed_fields)
            self.stdout.write(self.style.SUCCESS(f'Updated administrator {email}.'))
        else:
            self.stdout.write(f'Administrator {email} is already configured.')
