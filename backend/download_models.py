import os
import django
from django.conf import settings

# Setup minimum Django config to read settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SAS.settings')
django.setup()

import insightface
from insightface.app import FaceAnalysis

print("Initializing InsightFace to trigger model download...")
print(f"Target directory: {settings.FACE_MODEL_DIR}")

try:
    # This will download the buffalo_l model zip and extract it to the root dir
    app = FaceAnalysis(name='buffalo_l', root=str(settings.FACE_MODEL_DIR), providers=['CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    print("Models successfully downloaded and initialized!")
except Exception as e:
    print(f"Error during download/initialization: {e}")
