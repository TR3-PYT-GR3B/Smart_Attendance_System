import 'package:dio/dio.dart';

class ApiConstants {
  // Override for local/web/production builds with
  // --dart-define=API_BASE_URL=https://api.example.com
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://reboot-campfire-mantra.ngrok-free.dev',
  );

  static const String login = '$baseUrl/api/auth/login/';
  static const String tokenRefresh = '$baseUrl/api/auth/token/refresh/';
  static const String me = '$baseUrl/api/auth/me/';
  static const String changePassword = '$baseUrl/api/auth/change-password/';
  static const String enrollmentStatus = '$baseUrl/api/enrollment/status/';
  static const String livenessChallenge = '$baseUrl/api/enrollment/challenge/';
  static const String livenessPoseCheck = '$baseUrl/api/enrollment/pose-check/';
  static const String livenessCapture =
      '$baseUrl/api/enrollment/liveness-capture/';
  static const String checkIn = '$baseUrl/api/attendance/check-in/';
  static const String checkOut = '$baseUrl/api/attendance/check-out/';
  static const String currentSession = '$baseUrl/api/attendance/current/';
  static const String attendanceHistory = '$baseUrl/api/attendance/history/';
  static const String workLocations = '$baseUrl/api/attendance/locations/';
  static const String leaveTypes = '$baseUrl/api/leave/types/';
  static const String leaveRequests = '$baseUrl/api/leave/requests/';
  static const String documentRequests = '$baseUrl/api/documents/requests/';

  static String submitDocumentRequest(int requestId) =>
      '$baseUrl/api/documents/requests/$requestId/submit/';

  static Dio getAuthenticatedDio(String? token) {
    final dio = Dio();
    if (token != null) {
      dio.options.headers['Authorization'] = 'Bearer $token';
    }
    return dio;
  }
}
