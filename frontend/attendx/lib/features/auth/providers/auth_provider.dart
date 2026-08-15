import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/constants/api_constants.dart';

class AuthProvider extends ChangeNotifier {
  String _userName = 'Staff Member';
  String? _token;
  String? _refreshToken;
  String _nextStep = 'contact_administrator';
  Map<String, dynamic> _profile = {};

  String get userName => _userName;
  String? get token => _token;
  String get nextStep => _nextStep;
  Map<String, dynamic> get profile => Map.unmodifiable(_profile);

  String get nextRoute {
    switch (_nextStep) {
      case 'change_password':
        return '/change-password';
      case 'enroll_face':
        return '/face-registration';
      case 'ready_to_check_in':
        return '/dashboard';
      default:
        return '/account-waiting';
    }
  }

  String get firstName {
    if (_userName.trim().isEmpty) return '';
    return _userName.trim().split(' ')[0];
  }

  Future<void> login(
    String email,
    String password, {
    bool rememberMe = false,
  }) async {
    final dio = Dio();
    try {
      final response = await dio.post(
        ApiConstants.login,
        data: {'email': email, 'password': password},
      );

      if (response.statusCode == 200) {
        _token = response.data['access'];
        _refreshToken = response.data['refresh'];
        _applyUser(response.data['user']);
        _nextStep = response.data['next_step'] ?? _nextStep;

        final prefs = await SharedPreferences.getInstance();
        if (rememberMe && _token != null && _refreshToken != null) {
          await prefs.setString('jwt_token', _token!);
          await prefs.setString('refresh_token', _refreshToken!);
        } else {
          await prefs.remove('jwt_token');
          await prefs.remove('refresh_token');
        }
        notifyListeners();
      } else {
        throw Exception('Invalid credentials');
      }
    } catch (e) {
      if (e is DioException && e.response?.statusCode == 401) {
        throw Exception('Invalid email or password');
      }
      if (e is DioException) {
        throw Exception(
          _responseMessage(e.response?.data) ??
              'Network error or server unavailable',
        );
      }
      rethrow;
    }
  }

  Future<bool> tryAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    _refreshToken = prefs.getString('refresh_token');
    if (_refreshToken == null) {
      return false;
    }

    try {
      final dio = Dio();
      final refreshResponse = await dio.post(
        ApiConstants.tokenRefresh,
        data: {'refresh': _refreshToken},
      );
      _token = refreshResponse.data['access'];
      await prefs.setString('jwt_token', _token!);

      final profileResponse = await ApiConstants.getAuthenticatedDio(
        _token,
      ).get(ApiConstants.me);
      _applyUser(profileResponse.data);
      notifyListeners();
      return true;
    } catch (_) {
      await logout();
      return false;
    }
  }

  Future<void> changePassword(
    String currentPassword,
    String newPassword,
    String confirmation,
  ) async {
    try {
      final response = await ApiConstants.getAuthenticatedDio(_token).post(
        ApiConstants.changePassword,
        data: {
          'current_password': currentPassword,
          'new_password': newPassword,
          'new_password_confirm': confirmation,
        },
      );
      _nextStep = response.data['next_step'] ?? _nextStep;
      _applyUser(response.data['user']);
      notifyListeners();
    } on DioException catch (error) {
      throw Exception(
        _responseMessage(error.response?.data) ?? 'Password change failed.',
      );
    }
  }

  Future<void> refreshProfile() async {
    final response = await ApiConstants.getAuthenticatedDio(
      _token,
    ).get(ApiConstants.me);
    _applyUser(response.data);
    notifyListeners();
  }

  void markReadyForAttendance() {
    _nextStep = 'ready_to_check_in';
    notifyListeners();
  }

  void _applyUser(dynamic rawUser) {
    if (rawUser is! Map) return;
    _profile = Map<String, dynamic>.from(rawUser);
    final fullName = (rawUser['full_name'] ?? '').toString().trim();
    if (fullName.isNotEmpty) {
      _userName = fullName;
    } else if ((rawUser['email'] ?? '').toString().isNotEmpty) {
      _userName = rawUser['email'].toString().split('@').first;
    }
    _nextStep = (rawUser['next_step'] ?? _nextStep).toString();
  }

  String? _responseMessage(dynamic data) {
    if (data is! Map) return null;
    if (data['detail'] != null) return data['detail'].toString();
    for (final value in data.values) {
      if (value is List && value.isNotEmpty) return value.first.toString();
      if (value is String) return value;
    }
    return null;
  }

  Future<void> logout() async {
    _token = null;
    _refreshToken = null;
    _userName = 'Staff Member';
    _nextStep = 'contact_administrator';
    _profile = {};
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jwt_token');
    await prefs.remove('refresh_token');
    notifyListeners();
  }
}
