"""Download and verify the exact InsightFace assets used by AttendX."""

import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SAS.settings')

import django

django.setup()

from django.conf import settings
from insightface.app import FaceAnalysis


def main():
    target = Path(settings.FACE_MODEL_DIR)
    print(f'Preparing InsightFace models in {target}')

    app = FaceAnalysis(
        name='buffalo_l',
        root=str(target),
        allowed_modules=['detection', 'recognition', 'landmark_3d_68'],
        providers=['CPUExecutionProvider'],
    )
    app.prepare(
        ctx_id=0,
        det_size=(settings.FACE_DETECTION_SIZE, settings.FACE_DETECTION_SIZE),
    )

    missing = [
        relative_path
        for relative_path in settings.FACE_MODEL_REQUIRED_FILES
        if not (target / relative_path).is_file()
    ]
    if missing:
        raise RuntimeError(
            'InsightFace initialization completed without required files: '
            + ', '.join(missing)
        )

    print('InsightFace models downloaded and verified.')


if __name__ == '__main__':
    main()
