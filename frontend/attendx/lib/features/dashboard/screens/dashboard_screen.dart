import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';
import 'package:geolocator/geolocator.dart';
import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/services/location_service.dart';
import '../../../core/constants/api_constants.dart';
import '../../attendance/screens/face_scan_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isVerifyingLocation = false;
  bool _isLoadingSession = true;
  bool _hasOpenSession = false;
  String? _shiftEndTimeStr;
  Map<String, dynamic>? _currentWorkLocation;
  BuildContext? _locationVerificationDialogContext;
  DateTime? _locationVerificationShownAt;

  @override
  void initState() {
    super.initState();
    _fetchCurrentSession();
  }

  Future<void> _fetchCurrentSession() async {
    try {
      final token = context.read<AuthProvider>().token;
      final dio = ApiConstants.getAuthenticatedDio(token);
      final response = await dio.get(
        ApiConstants.currentSession,
        options: Options(validateStatus: (status) => true),
      );
      if (response.statusCode == 200 && mounted) {
        setState(() {
          _hasOpenSession = response.data['has_open_session'] ?? false;
          if (_hasOpenSession) {
            _shiftEndTimeStr =
                response.data['record']['work_location']['shift_end_time'];
            _currentWorkLocation = Map<String, dynamic>.from(
              response.data['record']['work_location'],
            );
          } else {
            _shiftEndTimeStr = null;
            _currentWorkLocation = null;
          }
          _isLoadingSession = false;
        });
      } else if (mounted) {
        setState(() => _isLoadingSession = false);
      }
    } catch (e) {
      if (mounted) setState(() => _isLoadingSession = false);
    }
  }

  Future<void> _handleCheckInOut({required bool isCheckout}) async {
    setState(() => _isVerifyingLocation = true);
    await _showLocationVerificationPopup(isCheckout: isCheckout);
    try {
      final position = await LocationService.determinePosition();
      Map<String, dynamic>? location;

      if (isCheckout) {
        location = _currentWorkLocation;
      } else {
        final locations = await _fetchAvailableLocations();
        if (!mounted) {
          await _hideLocationVerificationPopup();
          return;
        }
        if (locations.isEmpty) {
          await _hideLocationVerificationPopup();
          if (mounted) setState(() => _isVerifyingLocation = false);
          await _showStatusPopup(
            isSuccess: false,
            message: 'No active work location is assigned to your department.',
          );
          return;
        }

        if (locations.length == 1) {
          location = locations.first;
        } else {
          await _hideLocationVerificationPopup();
          if (!mounted) return;
          location = await _chooseLocation(locations, position);
          if (location != null && mounted) {
            await _showLocationVerificationPopup(isCheckout: isCheckout);
          }
        }
      }

      if (location == null) {
        await _hideLocationVerificationPopup();
        if (mounted) setState(() => _isVerifyingLocation = false);
        return;
      }

      final distance = Geolocator.distanceBetween(
        position.latitude,
        position.longitude,
        (location['latitude'] as num).toDouble(),
        (location['longitude'] as num).toDouble(),
      );
      final allowedRadiusInMeters = (location['radius_meters'] as num)
          .toDouble();

      await _hideLocationVerificationPopup();
      if (mounted) setState(() => _isVerifyingLocation = false);

      if (distance <= allowedRadiusInMeters) {
        if (mounted) {
          await _showStatusPopup(
            isSuccess: true,
            message:
                'Work location verified!\n\nPlease scan your face to ${isCheckout ? 'clock out' : 'clock in'}.',
          );
          if (mounted) {
            await context.push(
              '/face-scan',
              extra: AttendanceScanArguments(
                isCheckout: isCheckout,
                workLocationId: (location['id'] as num).toInt(),
                latitude: position.latitude,
                longitude: position.longitude,
              ),
            );
            await _fetchCurrentSession();
          }
        }
      } else {
        if (mounted) {
          String distanceStr = distance > 1000
              ? '${(distance / 1000).toStringAsFixed(1)} km'
              : '${distance.toStringAsFixed(0)} meters';

          await _showStatusPopup(
            isSuccess: false,
            message:
                "You're not in the work location.\nYou are $distanceStr away from the office.",
          );
        }
      }
    } catch (e) {
      await _hideLocationVerificationPopup();
      if (mounted) setState(() => _isVerifyingLocation = false);
      if (mounted) {
        await _showStatusPopup(
          isSuccess: false,
          message: 'Failed to verify location.\nPlease ensure GPS is enabled.',
        );
      }
    }
  }

  Future<void> _showLocationVerificationPopup({
    required bool isCheckout,
  }) async {
    if (!mounted || _locationVerificationDialogContext != null) return;

    _locationVerificationShownAt = DateTime.now();
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        _locationVerificationDialogContext = dialogContext;
        return PopScope(
          canPop: false,
          child: Dialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      const SizedBox(
                        width: 72,
                        height: 72,
                        child: CircularProgressIndicator(strokeWidth: 3),
                      ),
                      Icon(
                        Icons.location_on_rounded,
                        color: Theme.of(dialogContext).colorScheme.primary,
                        size: 34,
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Verifying work location',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 21, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Verifying that you are at the work location before ${isCheckout ? 'check-out' : 'check-in'}.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Theme.of(
                        dialogContext,
                      ).colorScheme.onSurfaceVariant,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );

    await WidgetsBinding.instance.endOfFrame;
  }

  Future<void> _hideLocationVerificationPopup() async {
    final shownAt = _locationVerificationShownAt;
    if (shownAt != null) {
      const minimumVisibleTime = Duration(milliseconds: 900);
      final remaining = minimumVisibleTime - DateTime.now().difference(shownAt);
      if (remaining > Duration.zero) await Future.delayed(remaining);
    }

    final dialogContext = _locationVerificationDialogContext;
    _locationVerificationDialogContext = null;
    _locationVerificationShownAt = null;
    if (dialogContext != null && dialogContext.mounted) {
      Navigator.of(dialogContext).pop();
    }
  }

  Future<List<Map<String, dynamic>>> _fetchAvailableLocations() async {
    final token = context.read<AuthProvider>().token;
    final response = await ApiConstants.getAuthenticatedDio(
      token,
    ).get(ApiConstants.workLocations);
    final dynamic payload = response.data;
    final List<dynamic> rows = payload is List
        ? payload
        : (payload is Map && payload['results'] is List
              ? payload['results'] as List
              : const []);
    return rows.map((row) => Map<String, dynamic>.from(row as Map)).toList();
  }

  Future<Map<String, dynamic>?> _chooseLocation(
    List<Map<String, dynamic>> locations,
    Position position,
  ) async {
    if (locations.isEmpty) {
      await _showStatusPopup(
        isSuccess: false,
        message: 'No active work location is assigned to your department.',
      );
      return null;
    }
    if (locations.length == 1) return locations.first;

    return showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        title: const Text('Choose work location'),
        children: locations.map((location) {
          final distance = Geolocator.distanceBetween(
            position.latitude,
            position.longitude,
            (location['latitude'] as num).toDouble(),
            (location['longitude'] as num).toDouble(),
          );
          final distanceText = distance >= 1000
              ? '${(distance / 1000).toStringAsFixed(1)} km away'
              : '${distance.toStringAsFixed(0)} m away';
          return SimpleDialogOption(
            onPressed: () => Navigator.pop(dialogContext, location),
            child: ListTile(
              title: Text(location['name'].toString()),
              subtitle: Text('${location['department_name']} · $distanceText'),
            ),
          );
        }).toList(),
      ),
    );
  }

  Future<void> _showStatusPopup({
    required bool isSuccess,
    required String message,
  }) async {
    bool dialogIsVisible = true;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => PopScope(
        canPop: false,
        child: Dialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isSuccess ? Icons.check_circle : Icons.cancel,
                  color: isSuccess ? Colors.green : Colors.red,
                  size: 80,
                ),
                const SizedBox(height: 24),
                Text(
                  isSuccess ? 'Success' : 'Access Denied',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16, color: Colors.grey),
                ),
              ],
            ),
          ),
        ),
      ),
    );

    // Wait for 4 seconds
    await Future.delayed(const Duration(seconds: 4));

    // Close the dialog
    if (mounted && dialogIsVisible && Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Dashboard'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => context.push('/notifications'),
          ),
        ],
      ),
      body: _buildBody(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: 0,
        onTap: (index) {
          if (index == 1) context.push('/history');
          if (index == 2) context.push('/requests');
          if (index == 3) context.push('/more');
        },
        type: BottomNavigationBarType.fixed,
        selectedItemColor: theme.primaryColor,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
          BottomNavigationBarItem(
            icon: Icon(Icons.assignment),
            label: 'Requests',
          ),
          BottomNavigationBarItem(icon: Icon(Icons.more_horiz), label: 'More'),
        ],
      ),
    );
  }

  Widget _buildBody() {
    final theme = Theme.of(context);
    final firstName = context.watch<AuthProvider>().firstName;
    final hour = DateTime.now().hour;
    String greeting = 'Good evening';
    if (hour < 12) {
      greeting = 'Good morning';
    } else if (hour < 17) {
      greeting = 'Good afternoon';
    }

    // Home Screen
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '$greeting,\n$firstName \uD83D\uDC4B',
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            'Have a productive day!',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 24),
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.dividerColor),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                children: [
                  Icon(
                    _hasOpenSession ? Icons.work : Icons.access_time,
                    color: _hasOpenSession ? Colors.green : Colors.orange,
                    size: 32,
                  ),
                  const SizedBox(width: 16),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _hasOpenSession
                            ? 'Session Active'
                            : 'No Active Session',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                      Text(
                        _hasOpenSession
                            ? 'You are checked in.'
                            : 'You are not currently checked in.',
                        style: const TextStyle(
                          color: Colors.grey,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _buildActionButton(),
          const SizedBox(height: 32),
          const Text(
            'Quick Actions',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildQuickAction(
                Icons.history,
                'History',
                () => context.push('/history'),
              ),
              _buildQuickAction(
                Icons.person_outline,
                'My Profile',
                () => context.push('/profile'),
              ),
              _buildQuickAction(
                Icons.folder_copy_outlined,
                'Documents',
                () => context.push('/documents'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton() {
    if (_isLoadingSession) {
      return const Center(child: CircularProgressIndicator());
    }

    bool isCheckoutDisabled = false;
    String hintText = '';

    if (_hasOpenSession && _shiftEndTimeStr != null) {
      try {
        final now = DateTime.now();
        final format = DateFormat("HH:mm:ss");
        final shiftEndTime = format.parse(_shiftEndTimeStr!);
        final shiftEndToday = DateTime(
          now.year,
          now.month,
          now.day,
          shiftEndTime.hour,
          shiftEndTime.minute,
          shiftEndTime.second,
        );

        if (now.isBefore(shiftEndToday)) {
          isCheckoutDisabled = true;
          hintText =
              'Checkout is available from ${DateFormat("hh:mm a").format(shiftEndToday)}';
        }
      } catch (e) {
        // Fallback if parsing fails
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ElevatedButton(
          onPressed: (_isVerifyingLocation || isCheckoutDisabled)
              ? null
              : () => _handleCheckInOut(isCheckout: _hasOpenSession),
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 20),
            backgroundColor: _hasOpenSession ? Colors.red : null,
          ),
          child: _isVerifyingLocation
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : Text(
                  _hasOpenSession ? 'Check Out' : 'Check In',
                  style: TextStyle(
                    fontSize: 18,
                    color: _hasOpenSession ? Colors.white : null,
                  ),
                ),
        ),
        if (isCheckoutDisabled)
          Padding(
            padding: const EdgeInsets.only(top: 8.0),
            child: Text(
              hintText,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.red, fontSize: 12),
            ),
          ),
      ],
    );
  }

  Widget _buildQuickAction(IconData icon, String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          children: [
            CircleAvatar(
              radius: 28,
              backgroundColor: Theme.of(context).cardColor,
              child: Icon(
                icon,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                size: 28,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              label,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),
    );
  }
}
