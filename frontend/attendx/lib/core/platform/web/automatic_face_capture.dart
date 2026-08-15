import 'dart:async';
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../../models/captured_frame.dart';
import '../../widgets/automatic_face_capture_contract.dart';

export '../../widgets/automatic_face_capture_contract.dart';

/// Browser implementation that keeps expensive face analysis on the server.
/// It samples a compressed still frame rather than running an ML model or a
/// continuous image stream on the user's device.
class AutomaticFaceCapture extends StatefulWidget {
  const AutomaticFaceCapture({
    super.key,
    required this.controller,
    required this.actions,
    required this.filePrefix,
    required this.onCompleted,
    this.validateFrame,
  });

  final CameraController controller;
  final List<String> actions;
  final String filePrefix;
  final CaptureCompleted onCompleted;
  final FrameValidator? validateFrame;

  @override
  State<AutomaticFaceCapture> createState() => _AutomaticFaceCaptureState();
}

class _AutomaticFaceCaptureState extends State<AutomaticFaceCapture> {
  static const Duration _sampleInterval = Duration(milliseconds: 1350);

  final List<CapturedFrame> _capturedFrames = [];
  Timer? _captureTimer;
  bool _processing = false;
  bool _submitting = false;
  bool _framesHandedOff = false;
  String _feedback = 'Position your face inside the circle.';

  int get _actionIndex => _capturedFrames.length;
  String? get _action => _actionIndex < widget.actions.length
      ? widget.actions[_actionIndex]
      : null;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _captureTimer = Timer.periodic(
        _sampleInterval,
        (_) => _inspectCurrentPose(),
      );
    });
  }

  Future<void> _inspectCurrentPose() async {
    final action = _action;
    if (_processing || _submitting || !mounted || action == null) return;
    if (!widget.controller.value.isInitialized ||
        widget.controller.value.isTakingPicture) {
      return;
    }

    _processing = true;
    CapturedFrame? candidate;
    try {
      _updateFeedback('Checking your position…');
      final photo = await widget.controller.takePicture();
      final bytes = await photo.readAsBytes();
      candidate = CapturedFrame(
        bytes: bytes,
        filename: '${widget.filePrefix}-${_actionIndex + 1}.jpg',
      );

      final validator = widget.validateFrame;
      final validation = validator == null
          ? const CaptureValidation(
              accepted: true,
              message: 'Position confirmed.',
            )
          : await validator(action, candidate);
      if (!mounted) return;

      if (!validation.accepted) {
        _updateFeedback(validation.message);
        await candidate.dispose();
        candidate = null;
        return;
      }

      _capturedFrames.add(candidate);
      candidate = null;
      if (_capturedFrames.length == widget.actions.length) {
        _captureTimer?.cancel();
        _submitting = true;
        _framesHandedOff = true;
        setState(() => _feedback = 'Verifying on the server…');
        await widget.onCompleted(
          List<CapturedFrame>.unmodifiable(_capturedFrames),
        );
        return;
      }

      setState(() => _feedback = 'Captured. Get ready for the next position.');
      await Future.delayed(const Duration(milliseconds: 650));
      if (mounted && _action != null) {
        setState(() => _feedback = _instructionFor(_action!));
      }
    } catch (_) {
      _updateFeedback(
        'The camera could not confirm that position. Hold still and try again.',
      );
    } finally {
      await candidate?.dispose();
      _processing = false;
    }
  }

  String _titleFor(String action) {
    switch (action) {
      case 'turn_left':
        return 'Turn your head left';
      case 'turn_right':
        return 'Turn your head right';
      default:
        return 'Look straight ahead';
    }
  }

  String _instructionFor(String action) {
    if (action == 'straight') return 'Face the camera directly.';
    return _titleFor(action);
  }

  void _updateFeedback(String value) {
    if (mounted && _feedback != value) setState(() => _feedback = value);
  }

  @override
  void dispose() {
    _captureTimer?.cancel();
    if (!_framesHandedOff) {
      for (final frame in _capturedFrames) {
        frame.dispose();
      }
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final action = _action;
    final previewSize = widget.controller.value.previewSize;

    return SafeArea(
      child: SizedBox.expand(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final circleSize = math.min(constraints.maxWidth - 48, 340.0);
            return Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 18),
                Text(
                  _submitting
                      ? 'Final verification'
                      : 'Step ${_actionIndex + 1} of ${widget.actions.length}',
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 10),
                Text(
                  _submitting ? 'Please wait' : _titleFor(action!),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: Center(
                    child: Container(
                      width: circleSize,
                      height: circleSize,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 4),
                        boxShadow: const [
                          BoxShadow(
                            color: Colors.black54,
                            blurRadius: 18,
                            spreadRadius: 3,
                          ),
                        ],
                      ),
                      child: ClipOval(
                        child: previewSize == null
                            ? const ColoredBox(color: Colors.black)
                            : FittedBox(
                                alignment: Alignment.center,
                                fit: BoxFit.cover,
                                child: SizedBox(
                                  width: previewSize.height,
                                  height: previewSize.width,
                                  child: CameraPreview(widget.controller),
                                ),
                              ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 28),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 32),
                  child: Text(
                    _feedback,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 17),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Capture is automatic',
                  style: TextStyle(color: Colors.white54, fontSize: 13),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}
