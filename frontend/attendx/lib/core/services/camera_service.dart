import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';

class CameraService {
  static CameraService? _instance;
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];

  CameraService._();

  static CameraService get instance {
    _instance ??= CameraService._();
    return _instance!;
  }

  CameraController? get controller => _cameraController;

  Future<void> initialize() async {
    if (_cameraController != null) return; // Already initialized

    _cameras = await availableCameras();

    // Default to the first camera, but try to find the front-facing one
    CameraDescription? selectedCamera = _cameras.isNotEmpty
        ? _cameras.first
        : null;

    for (var camera in _cameras) {
      if (camera.lensDirection == CameraLensDirection.front) {
        selectedCamera = camera;
        break;
      }
    }

    if (selectedCamera != null) {
      _cameraController = CameraController(
        selectedCamera,
        kIsWeb ? ResolutionPreset.low : ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: kIsWeb
            ? ImageFormatGroup.unknown
            : defaultTargetPlatform == TargetPlatform.android
            ? ImageFormatGroup.yuv420
            : ImageFormatGroup.bgra8888,
      );

      try {
        await _cameraController!.initialize();
      } catch (_) {
        await _cameraController?.dispose();
        _cameraController = null;
        rethrow;
      }
    } else {
      throw Exception('No cameras found on this device.');
    }
  }

  Future<void> startImageStream(void Function(CameraImage) onAvailable) async {
    if (_cameraController != null &&
        !_cameraController!.value.isStreamingImages) {
      await _cameraController!.startImageStream(onAvailable);
    }
  }

  Future<void> stopImageStream() async {
    if (_cameraController != null &&
        _cameraController!.value.isStreamingImages) {
      await _cameraController!.stopImageStream();
    }
  }

  Future<void> dispose() async {
    await stopImageStream();
    await _cameraController?.dispose();
    _cameraController = null;
  }
}
