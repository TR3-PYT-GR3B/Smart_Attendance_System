import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:image/image.dart' as img;

import '../../models/captured_frame.dart';
import '../../widgets/automatic_face_capture_contract.dart';

export '../../widgets/automatic_face_capture_contract.dart';

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
  static const int _stableDetectionsRequired = 2;

  late final FaceDetector _faceDetector;
  Timer? _captureTimer;
  final List<CapturedFrame> _capturedFrames = [];

  bool _processing = false;
  bool _submitting = false;
  bool _framesHandedOff = false;
  int _stableDetections = 0;
  String _feedback = 'Position your face inside the circle.';

  int get _actionIndex => _capturedFrames.length;
  String? get _action => _actionIndex < widget.actions.length
      ? widget.actions[_actionIndex]
      : null;

  @override
  void initState() {
    super.initState();
    _faceDetector = FaceDetector(
      options: FaceDetectorOptions(
        performanceMode: FaceDetectorMode.fast,
        enableContours: false,
        enableLandmarks: false,
        enableClassification: false,
        minFaceSize: 0.18,
      ),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) => _startDetection());
  }

  void _startDetection() {
    _captureTimer?.cancel();
    _captureTimer = Timer.periodic(
      const Duration(milliseconds: 850),
      (_) => _inspectCurrentPose(),
    );
  }

  Future<void> _inspectCurrentPose() async {
    if (_processing || _submitting || !mounted || _action == null) return;
    if (!widget.controller.value.isInitialized ||
        widget.controller.value.isTakingPicture) {
      return;
    }

    _processing = true;
    String? rawPath;
    String? correctedPath;
    try {
      final XFile photo = await widget.controller.takePicture();
      rawPath = photo.path;
      final bytes = await File(photo.path).readAsBytes();
      final decoded = img.decodeImage(bytes);
      if (decoded == null) {
        _updateFeedback('Camera image could not be read. Hold still.');
        await _deleteIfPresent(photo.path);
        rawPath = null;
        return;
      }

      final oriented = img.bakeOrientation(decoded);
      correctedPath =
          '${File(photo.path).parent.path}/${widget.filePrefix}_${DateTime.now().microsecondsSinceEpoch}.jpg';
      final correctedBytes = img.encodeJpg(oriented, quality: 86);
      await File(correctedPath).writeAsBytes(correctedBytes, flush: true);
      await _deleteIfPresent(photo.path);
      rawPath = null;

      final faces = await _faceDetector.processImage(
        InputImage.fromFilePath(correctedPath),
      );
      if (!mounted) return;

      final failure = _poseFailure(
        faces,
        Size(oriented.width.toDouble(), oriented.height.toDouble()),
        _action!,
      );
      if (failure != null) {
        _stableDetections = 0;
        _updateFeedback(failure);
        await _deleteIfPresent(correctedPath);
        return;
      }

      _stableDetections += 1;
      if (_stableDetections < _stableDetectionsRequired) {
        _updateFeedback('Good. Hold that position…');
        await _deleteIfPresent(correctedPath);
        return;
      }

      _stableDetections = 0;
      _capturedFrames.add(
        CapturedFrame(
          bytes: correctedBytes,
          filename: '${widget.filePrefix}-${_actionIndex + 1}.jpg',
          localPath: correctedPath,
        ),
      );
      correctedPath = null;
      if (_capturedFrames.length == widget.actions.length) {
        _captureTimer?.cancel();
        _submitting = true;
        _framesHandedOff = true;
        if (mounted) setState(() => _feedback = 'Verifying on the server…');
        await widget.onCompleted(
          List<CapturedFrame>.unmodifiable(_capturedFrames),
        );
      } else {
        if (mounted) {
          setState(
            () => _feedback = 'Captured. Get ready for the next position.',
          );
        }
        await Future.delayed(const Duration(milliseconds: 700));
        if (mounted) setState(() => _feedback = _instructionFor(_action!));
      }
    } catch (_) {
      _stableDetections = 0;
      _updateFeedback('Hold still while the camera refocuses.');
    } finally {
      if (rawPath != null) await _deleteIfPresent(rawPath);
      if (correctedPath != null) await _deleteIfPresent(correctedPath);
      _processing = false;
    }
  }

  String? _poseFailure(List<Face> faces, Size imageSize, String action) {
    if (faces.isEmpty) return 'No face detected. Move into the circle.';
    if (faces.length > 1) return 'Only one person should be visible.';

    final face = faces.first;
    final centre = face.boundingBox.center;
    final horizontalOffset = (centre.dx - imageSize.width / 2).abs();
    final verticalOffset = (centre.dy - imageSize.height / 2).abs();
    if (horizontalOffset > imageSize.width * 0.18 ||
        verticalOffset > imageSize.height * 0.20) {
      return 'Centre your face inside the circle.';
    }

    final imageArea = imageSize.width * imageSize.height;
    final faceRatio =
        face.boundingBox.width * face.boundingBox.height / imageArea;
    if (faceRatio < 0.09) return 'Move a little closer.';
    if (faceRatio > 0.62) return 'Move a little farther away.';

    final pitch = face.headEulerAngleX ?? 0;
    final yaw = face.headEulerAngleY ?? 0;
    final roll = face.headEulerAngleZ ?? 0;
    return AutomaticFacePoseRules.failureFor(
      action: action,
      pitch: pitch,
      yaw: yaw,
      roll: roll,
    );
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

  Future<void> _deleteIfPresent(String path) async {
    try {
      final file = File(path);
      if (await file.exists()) await file.delete();
    } catch (_) {}
  }

  @override
  void dispose() {
    _captureTimer?.cancel();
    _faceDetector.close();
    if (!_framesHandedOff) {
      for (final frame in _capturedFrames) {
        final path = frame.localPath;
        if (path == null) continue;
        try {
          File(path).deleteSync();
        } catch (_) {}
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
                        border: Border.all(
                          color: _stableDetections > 0
                              ? Colors.greenAccent
                              : Colors.white,
                          width: 4,
                        ),
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
                SizedBox(
                  width: double.infinity,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 32),
                    child: Text(
                      _feedback,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: _stableDetections > 0
                            ? Colors.greenAccent
                            : Colors.white,
                        fontSize: 17,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Capture is automatic',
                  textAlign: TextAlign.center,
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
