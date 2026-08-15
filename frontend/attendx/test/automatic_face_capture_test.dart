import 'package:flutter_test/flutter_test.dart';
import 'package:attendx/core/widgets/automatic_face_capture_contract.dart';

void main() {
  group('AutomaticFacePoseRules', () {
    test('accepts a centred straight face', () {
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'straight',
          pitch: 1,
          yaw: 2,
          roll: 1,
        ),
        isNull,
      );
    });

    test('requires the requested left and right turn directions', () {
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'turn_left',
          pitch: 0,
          yaw: 20,
          roll: 0,
        ),
        isNull,
      );
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'turn_left',
          pitch: 0,
          yaw: -20,
          roll: 0,
        ),
        isNotNull,
      );
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'turn_right',
          pitch: 0,
          yaw: -20,
          roll: 0,
        ),
        isNull,
      );
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'turn_right',
          pitch: 0,
          yaw: 20,
          roll: 0,
        ),
        isNotNull,
      );
    });

    test('rejects excessive pitch and roll', () {
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'straight',
          pitch: 20,
          yaw: 0,
          roll: 0,
        ),
        contains('chin'),
      );
      expect(
        AutomaticFacePoseRules.failureFor(
          action: 'straight',
          pitch: 0,
          yaw: 0,
          roll: 20,
        ),
        contains('upright'),
      );
    });
  });
}
