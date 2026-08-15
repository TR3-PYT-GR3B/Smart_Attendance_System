import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/models/captured_frame.dart';
import '../../../core/services/camera_service.dart';
import '../../../core/platform/native/automatic_face_capture.dart'
    if (dart.library.js_interop) '../../../core/platform/web/automatic_face_capture.dart';
import '../../../core/widgets/identity_verification_view.dart';
import '../../auth/providers/auth_provider.dart';

class AttendanceScanArguments {
  const AttendanceScanArguments({
    required this.isCheckout,
    required this.latitude,
    required this.longitude,
    this.workLocationId,
  });

  final bool isCheckout;
  final double latitude;
  final double longitude;
  final int? workLocationId;
}

class FaceScanScreen extends StatefulWidget {
  const FaceScanScreen({super.key, required this.arguments});

  final AttendanceScanArguments arguments;

  @override
  State<FaceScanScreen> createState() => _FaceScanScreenState();
}

class _FaceScanScreenState extends State<FaceScanScreen> {
  bool _initializing = true;
  bool _busy = false;
  bool _verifying = false;
  String? _error;
  String? _challengeId;
  List<String> _actions = const [];
  final List<CapturedFrame> _frames = [];

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      await CameraService.instance.initialize();
      await Future.delayed(const Duration(milliseconds: 800));
      await _requestChallenge();
    } on DioException catch (error) {
      _setError(
        _messageFrom(error.response?.data) ??
            'Could not start face verification.',
      );
    } catch (error) {
      _setError(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _initializing = false);
    }
  }

  Future<void> _requestChallenge() async {
    final token = context.read<AuthProvider>().token;
    await _cleanupFrames();
    final response = await ApiConstants.getAuthenticatedDio(
      token,
    ).post(ApiConstants.livenessChallenge, data: {'purpose': 'attendance'});
    final actions = (response.data['actions'] as List)
        .map((value) => value.toString())
        .toList();
    if (actions.length != 3) {
      throw Exception('The server returned an invalid capture sequence.');
    }
    if (mounted) {
      setState(() {
        _challengeId = response.data['id'].toString();
        _actions = actions;
        _error = null;
        _busy = false;
      });
    }
  }

  Future<void> _captureCompleted(List<CapturedFrame> frames) async {
    _frames
      ..clear()
      ..addAll(frames);
    if (mounted) {
      setState(() {
        _busy = true;
        _verifying = true;
      });
      await WidgetsBinding.instance.endOfFrame;
    }
    await CameraService.instance.dispose();
    if (!mounted) {
      await _cleanupFrames();
      return;
    }
    await _submit();
  }

  Future<void> _submit() async {
    final args = widget.arguments;
    final token = context.read<AuthProvider>().token;
    try {
      final formData = FormData.fromMap({
        'challenge_id': _challengeId,
        'latitude': args.latitude,
        'longitude': args.longitude,
        if (!args.isCheckout) 'work_location_id': args.workLocationId,
      });
      for (final frame in _frames) {
        formData.files.add(
          MapEntry(
            'frames',
            MultipartFile.fromBytes(frame.bytes, filename: frame.filename),
          ),
        );
      }

      final response = await ApiConstants.getAuthenticatedDio(token).post(
        args.isCheckout ? ApiConstants.checkOut : ApiConstants.checkIn,
        data: formData,
      );
      await _cleanupFrames();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: const Icon(Icons.check_circle, color: Colors.green, size: 56),
          title: Text(args.isCheckout ? 'Checked out' : 'Checked in'),
          content: Text(
            response.data['detail']?.toString() ?? 'Attendance recorded.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Done'),
            ),
          ],
        ),
      );
      if (mounted) context.pop(true);
    } on DioException catch (error) {
      await _showFailureAndRestart(
        _messageFrom(error.response?.data) ?? 'Attendance verification failed.',
      );
    } catch (error) {
      await _showFailureAndRestart(
        error.toString().replaceFirst('Exception: ', ''),
      );
    }
  }

  Future<void> _showFailureAndRestart(String message) async {
    await _cleanupFrames();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: const Icon(Icons.error_outline, color: Colors.red, size: 52),
        title: Text(_failureTitle(message)),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Try again'),
          ),
        ],
      ),
    );
    if (!mounted) return;
    setState(() {
      _verifying = false;
      _initializing = true;
      _challengeId = null;
      _actions = const [];
    });
    try {
      await CameraService.instance.initialize();
      await Future.delayed(const Duration(milliseconds: 500));
      await _requestChallenge();
    } on DioException catch (error) {
      _setError(
        _messageFrom(error.response?.data) ??
            'Could not start another challenge.',
      );
    } catch (error) {
      _setError(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _initializing = false);
    }
  }

  String? _messageFrom(dynamic data) {
    if (data is! Map) return null;
    final verification = data['verification'];
    if (verification is Map) {
      final faceFailed = verification['face_passed'] == false;
      final hasFaceScore = verification['face_score'] is num;
      if (faceFailed && hasFaceScore) {
        return 'We could not confirm that the person in the scan matches this account’s enrolled face. Please try again in good lighting and keep your face fully visible.';
      }
      if (verification['liveness_passed'] == false) {
        return 'We could not confirm a live face from this scan. Please try again and follow each head-position instruction.';
      }
    }
    final reasons = verification is Map
        ? verification['failure_reasons']
        : null;
    if (reasons is List && reasons.isNotEmpty) return reasons.join('\n');
    if (data['detail'] != null) return data['detail'].toString();
    return null;
  }

  String _failureTitle(String message) {
    final normalized = message.toLowerCase();
    if (normalized.contains('does not match') ||
        normalized.contains('face mismatch')) {
      return 'Face mismatch';
    }
    if (normalized.contains('live face')) return 'Live face not confirmed';
    if (normalized.contains('work location') ||
        normalized.contains(' m from ')) {
      return 'Location not verified';
    }
    return 'Verification unsuccessful';
  }

  void _setError(String message) {
    if (mounted) {
      setState(() {
        _error = message;
        _busy = false;
        _verifying = false;
        _initializing = false;
      });
    }
  }

  Future<CaptureValidation> _validateWebFrame(
    String action,
    CapturedFrame frame,
  ) async {
    try {
      final response =
          await ApiConstants.getAuthenticatedDio(
            context.read<AuthProvider>().token,
          ).post(
            ApiConstants.livenessPoseCheck,
            data: FormData.fromMap({
              'challenge_id': _challengeId,
              'action': action,
              'frame': MultipartFile.fromBytes(
                frame.bytes,
                filename: frame.filename,
              ),
            }),
          );
      return CaptureValidation(
        accepted: response.data['accepted'] == true,
        message:
            response.data['message']?.toString() ?? 'Hold still and try again.',
      );
    } on DioException catch (error) {
      return CaptureValidation(
        accepted: false,
        message:
            _messageFrom(error.response?.data) ??
            'Could not confirm your position. Check your connection.',
      );
    }
  }

  Future<void> _cleanupFrames() async {
    for (final frame in List<CapturedFrame>.from(_frames)) {
      await frame.dispose();
    }
    _frames.clear();
  }

  @override
  void dispose() {
    for (final frame in _frames) {
      frame.dispose();
    }
    CameraService.instance.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_verifying) {
      return Scaffold(
        appBar: AppBar(
          title: Text(
            widget.arguments.isCheckout
                ? 'Verify check-out'
                : 'Verify check-in',
          ),
        ),
        body: IdentityVerificationView(
          message:
              'Your captures are being uploaded securely while AttendX verifies your liveness and face match.',
        ),
      );
    }

    final controller = CameraService.instance.controller;
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(
          widget.arguments.isCheckout ? 'Verify check-out' : 'Verify check-in',
        ),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: _initializing
          ? const Center(child: CircularProgressIndicator())
          : controller == null ||
                !controller.value.isInitialized ||
                _actions.isEmpty
          ? _buildUnavailable()
          : AutomaticFaceCapture(
              key: ValueKey(_challengeId),
              controller: controller,
              actions: _actions,
              filePrefix: 'attendance',
              onCompleted: _captureCompleted,
              validateFrame: _validateWebFrame,
            ),
    );
  }

  Widget _buildUnavailable() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _error ?? 'Camera unavailable.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white),
            ),
            const SizedBox(height: 18),
            OutlinedButton(
              onPressed: _busy ? null : _initialize,
              child: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
