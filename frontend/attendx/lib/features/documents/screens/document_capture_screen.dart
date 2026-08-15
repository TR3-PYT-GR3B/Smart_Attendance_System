import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/models/captured_frame.dart';

class DocumentCaptureScreen extends StatefulWidget {
  const DocumentCaptureScreen({super.key});

  @override
  State<DocumentCaptureScreen> createState() => _DocumentCaptureScreenState();
}

class _DocumentCaptureScreenState extends State<DocumentCaptureScreen> {
  CameraController? _controller;
  CapturedFrame? _capturedFrame;
  String? _error;
  bool _initializing = true;
  bool _capturing = false;
  bool _handedOff = false;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    if (mounted) {
      setState(() {
        _initializing = true;
        _error = null;
      });
    }
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) throw Exception('No camera is available.');
      final camera = cameras.firstWhere(
        (item) => item.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        camera,
        kIsWeb ? ResolutionPreset.medium : ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() => _controller = controller);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error.toString().replaceFirst('Exception: ', ''),
        );
      }
    } finally {
      if (mounted) setState(() => _initializing = false);
    }
  }

  Future<void> _capture() async {
    final controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        controller.value.isTakingPicture ||
        _capturing) {
      return;
    }

    setState(() => _capturing = true);
    try {
      final capture = await controller.takePicture();
      final bytes = await capture.readAsBytes();
      await controller.dispose();
      if (!mounted) return;
      setState(() {
        _controller = null;
        _capturedFrame = CapturedFrame(
          bytes: bytes,
          filename: 'document-${DateTime.now().millisecondsSinceEpoch}.jpg',
          localPath: kIsWeb ? null : capture.path,
        );
      });
    } catch (_) {
      if (mounted) setState(() => _error = 'The photo could not be captured.');
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _retake() async {
    await _capturedFrame?.dispose();
    if (!mounted) return;
    setState(() => _capturedFrame = null);
    await _initializeCamera();
  }

  void _usePhoto() {
    final frame = _capturedFrame;
    if (frame == null) return;
    _handedOff = true;
    context.pop(frame);
  }

  @override
  void dispose() {
    _controller?.dispose();
    if (!_handedOff) _capturedFrame?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Capture document'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: _capturedFrame != null
          ? _buildReview()
          : _initializing
          ? const Center(child: CircularProgressIndicator())
          : _error != null || _controller == null
          ? _buildError()
          : _buildCamera(),
    );
  }

  Widget _buildCamera() {
    final controller = _controller!;
    return SafeArea(
      child: Column(
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 18, 24, 14),
            child: Text(
              'Place the whole document inside the frame. Use good lighting and avoid glare.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white70, height: 1.4),
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Center(
                child: AspectRatio(
                  aspectRatio: 0.72,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(22),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        CameraPreview(controller),
                        DecoratedBox(
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.white, width: 3),
                            borderRadius: BorderRadius.circular(22),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 24),
            child: Semantics(
              button: true,
              label: 'Take document photo',
              child: InkWell(
                onTap: _capturing ? null : _capture,
                customBorder: const CircleBorder(),
                child: Container(
                  width: 78,
                  height: 78,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white,
                    border: Border.all(color: Colors.white54, width: 5),
                  ),
                  child: _capturing
                      ? const Padding(
                          padding: EdgeInsets.all(22),
                          child: CircularProgressIndicator(strokeWidth: 3),
                        )
                      : const Icon(
                          Icons.document_scanner_outlined,
                          color: Colors.black87,
                          size: 34,
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReview() {
    return SafeArea(
      child: Column(
        children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Image.memory(
                  _capturedFrame!.bytes,
                  fit: BoxFit.contain,
                  width: double.infinity,
                ),
              ),
            ),
          ),
          const Text(
            'Make sure all text is clear and readable.',
            style: TextStyle(color: Colors.white70),
          ),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _retake,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retake'),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _usePhoto,
                    icon: const Icon(Icons.check),
                    label: const Text('Use photo'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.camera_alt_outlined,
              color: Colors.white,
              size: 54,
            ),
            const SizedBox(height: 16),
            Text(
              _error ?? 'Camera unavailable.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white),
            ),
            const SizedBox(height: 18),
            OutlinedButton(
              onPressed: _initializeCamera,
              child: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
