import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/models/captured_frame.dart';
import '../../../core/services/camera_service.dart';
import '../../../core/platform/native/automatic_face_capture.dart'
    if (dart.library.js_interop) '../../../core/platform/web/automatic_face_capture.dart';
import '../../../core/widgets/glass_background.dart';
import '../../../core/widgets/identity_verification_view.dart';
import '../providers/auth_provider.dart';

class FaceRegistrationScreen extends StatefulWidget {
  const FaceRegistrationScreen({super.key});

  @override
  State<FaceRegistrationScreen> createState() => _FaceRegistrationScreenState();
}

class _FaceRegistrationScreenState extends State<FaceRegistrationScreen> {
  bool _consented = false;
  bool _started = false;
  bool _busy = false;
  bool _verifying = false;
  String? _error;
  String? _challengeId;
  List<String> _actions = const [];
  final List<CapturedFrame> _frames = [];

  Future<void> _startEnrollment() async {
    if (!_consented || _busy) return;
    final token = context.read<AuthProvider>().token;
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await CameraService.instance.initialize();
      await Future.delayed(const Duration(milliseconds: 800));
      final response = await ApiConstants.getAuthenticatedDio(
        token,
      ).post(ApiConstants.livenessChallenge, data: {'purpose': 'enrollment'});
      final actions = (response.data['actions'] as List)
          .map((value) => value.toString())
          .toList();
      if (actions.length != 3) {
        throw Exception('The server returned an invalid capture sequence.');
      }
      if (!mounted) return;
      setState(() {
        _challengeId = response.data['id'].toString();
        _actions = actions;
        _started = true;
      });
    } on DioException catch (error) {
      _setError(
        _messageFrom(error.response?.data) ??
            'Could not start face enrollment.',
      );
    } catch (error) {
      _setError(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
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
    await _submitEnrollment();
  }

  Future<void> _submitEnrollment() async {
    final token = context.read<AuthProvider>().token;
    try {
      final formData = FormData.fromMap({
        'challenge_id': _challengeId,
        'biometric_consent': true,
      });
      for (final frame in _frames) {
        formData.files.add(
          MapEntry(
            'frames',
            MultipartFile.fromBytes(frame.bytes, filename: frame.filename),
          ),
        );
      }

      final response = await ApiConstants.getAuthenticatedDio(
        token,
      ).post(ApiConstants.livenessCapture, data: formData);
      if (response.statusCode != 201) {
        throw Exception('Face enrollment was not accepted.');
      }

      await _cleanupFrames();
      if (!mounted) return;
      context.read<AuthProvider>().markReadyForAttendance();
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: const Icon(Icons.check_circle, color: Colors.green, size: 56),
          title: const Text('Face enrolled'),
          content: const Text(
            'Your encrypted face template is now stored on the server and will be used for attendance verification.',
            textAlign: TextAlign.center,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Continue'),
            ),
          ],
        ),
      );
      if (mounted) context.go('/dashboard');
    } on DioException catch (error) {
      await _restartAfterFailure(
        _messageFrom(error.response?.data) ?? 'Enrollment verification failed.',
      );
    } catch (error) {
      await _restartAfterFailure(
        error.toString().replaceFirst('Exception: ', ''),
      );
    }
  }

  Future<void> _restartAfterFailure(String message) async {
    await _cleanupFrames();
    if (!mounted) return;
    setState(() {
      _started = false;
      _busy = false;
      _verifying = false;
      _challengeId = null;
      _actions = const [];
      _error = message;
    });
  }

  String? _messageFrom(dynamic data) {
    if (data is Map && data['liveness_reason'] != null) {
      return 'We could not confirm a live face throughout the capture. Please try again in good lighting and follow each position prompt.';
    }
    if (data is Map && data['detail'] != null) return data['detail'].toString();
    return null;
  }

  void _setError(String message) {
    if (mounted) setState(() => _error = message);
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
    if (!_started) return _buildConsent();

    if (_verifying) {
      return Scaffold(
        appBar: AppBar(title: const Text('Face enrollment')),
        body: const IdentityVerificationView(
          message:
              'Your enrollment captures are being uploaded securely and checked for liveness and identity consistency.',
        ),
      );
    }

    final controller = CameraService.instance.controller;
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Face enrollment'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: controller == null || !controller.value.isInitialized
          ? const Center(child: CircularProgressIndicator())
          : AutomaticFaceCapture(
              key: ValueKey(_challengeId),
              controller: controller,
              actions: _actions,
              filePrefix: 'enrollment',
              onCompleted: _captureCompleted,
              validateFrame: _validateWebFrame,
            ),
    );
  }

  Widget _buildConsent() {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Face enrollment')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: GlassPanel(
                borderRadius: BorderRadius.circular(28),
                padding: const EdgeInsets.fromLTRB(26, 28, 26, 26),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Align(
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 7,
                        ),
                        decoration: BoxDecoration(
                          color: colorScheme.primary.withValues(alpha: 0.11),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'FIRST-TIME SETUP',
                          style: TextStyle(
                            color: colorScheme.primary,
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.1,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 22),
                    Align(
                      child: Container(
                        width: 92,
                        height: 92,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [
                              colorScheme.primary,
                              colorScheme.secondary,
                            ],
                          ),
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.75),
                            width: 2,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: colorScheme.primary.withValues(
                                alpha: 0.28,
                              ),
                              blurRadius: 26,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.face_retouching_natural,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'Set up attendance verification',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                        height: 1.15,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'AttendX will guide you through three quick, automatic captures for secure check-in and check-out.',
                      textAlign: TextAlign.center,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 26),
                    _setupPoint(
                      Icons.center_focus_strong,
                      'Hands-free capture',
                      'The camera captures automatically when your face is positioned correctly.',
                    ),
                    const SizedBox(height: 14),
                    _setupPoint(
                      Icons.threesixty,
                      'Three guided angles',
                      'Look straight, then turn left and right when prompted.',
                    ),
                    const SizedBox(height: 22),
                    Container(
                      decoration: BoxDecoration(
                        color: colorScheme.surface.withValues(alpha: 0.28),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: theme.dividerColor),
                      ),
                      child: CheckboxListTile(
                        value: _consented,
                        onChanged: _busy
                            ? null
                            : (value) =>
                                  setState(() => _consented = value ?? false),
                        controlAffinity: ListTileControlAffinity.leading,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        title: const Text(
                          'I consent to biometric processing for attendance verification.',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: colorScheme.error.withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          _error!,
                          style: TextStyle(color: colorScheme.error),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ],
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: !_consented || _busy ? null : _startEnrollment,
                      icon: _busy
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : const Icon(Icons.camera_alt_outlined),
                      label: Text(
                        _busy ? 'Preparing camera' : 'Begin face capture',
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.lock_outline,
                          size: 15,
                          color: colorScheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            'Your biometric data is used only for attendance verification.',
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _setupPoint(IconData icon, String title, String description) {
    final colorScheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(9),
          decoration: BoxDecoration(
            color: colorScheme.primary.withValues(alpha: 0.11),
            borderRadius: BorderRadius.circular(11),
          ),
          child: Icon(icon, color: colorScheme.primary, size: 21),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 3),
              Text(
                description,
                style: TextStyle(
                  color: colorScheme.onSurfaceVariant,
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
