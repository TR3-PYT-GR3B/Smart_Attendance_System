import '../models/captured_frame.dart';

typedef CaptureCompleted = Future<void> Function(List<CapturedFrame> frames);
typedef FrameValidator =
    Future<CaptureValidation> Function(String action, CapturedFrame frame);

class CaptureValidation {
  const CaptureValidation({required this.accepted, required this.message});

  final bool accepted;
  final String message;
}

class AutomaticFacePoseRules {
  static const double straightYawLimit = 8;
  static const double turnYawMinimum = 16;
  static const double pitchLimit = 12;
  static const double rollLimit = 12;

  static String? failureFor({
    required String action,
    required double pitch,
    required double yaw,
    required double roll,
  }) {
    if (pitch.abs() > pitchLimit) return 'Keep your chin level.';
    if (roll.abs() > rollLimit) return 'Keep your head upright.';

    // ML Kit defines positive Y as turning toward the processed image's right.
    // For a front-facing person that corresponds to turning their head left.
    switch (action) {
      case 'turn_left':
        if (yaw < turnYawMinimum) {
          return 'Turn your head farther to the left.';
        }
        return null;
      case 'turn_right':
        if (yaw > -turnYawMinimum) {
          return 'Turn your head farther to the right.';
        }
        return null;
      default:
        if (yaw.abs() > straightYawLimit) {
          return 'Look straight at the camera.';
        }
        return null;
    }
  }
}
