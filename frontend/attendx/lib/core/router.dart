import 'package:go_router/go_router.dart';
import '../features/auth/screens/login_screen.dart';
import '../features/dashboard/screens/dashboard_screen.dart';
import '../features/splash/screens/splash_screen.dart';
import '../features/auth/screens/face_registration_screen.dart';
import '../features/auth/screens/change_password_screen.dart';
import '../features/auth/screens/account_waiting_screen.dart';
import '../features/attendance/screens/face_scan_screen.dart';
import '../features/attendance/screens/history_screen.dart';
import '../features/requests/screens/requests_screen.dart';
import '../features/profile/screens/profile_screen.dart';
import '../features/notifications/screens/notifications_screen.dart';
import '../features/settings/screens/more_screen.dart';
import '../features/documents/screens/document_capture_screen.dart';
import '../features/documents/screens/document_requests_screen.dart';

final router = GoRouter(
  initialLocation: '/',
  routes: [
    GoRoute(path: '/', builder: (context, state) => const SplashScreen()),
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(
      path: '/change-password',
      builder: (context, state) => const ChangePasswordScreen(),
    ),
    GoRoute(
      path: '/account-waiting',
      builder: (context, state) => const AccountWaitingScreen(),
    ),
    GoRoute(
      path: '/face-registration',
      builder: (context, state) => const FaceRegistrationScreen(),
    ),
    GoRoute(
      path: '/dashboard',
      builder: (context, state) => const DashboardScreen(),
    ),
    GoRoute(
      path: '/face-scan',
      builder: (context, state) {
        final arguments = state.extra as AttendanceScanArguments;
        return FaceScanScreen(arguments: arguments);
      },
    ),
    GoRoute(
      path: '/history',
      builder: (context, state) => const HistoryScreen(),
    ),
    GoRoute(
      path: '/requests',
      builder: (context, state) => const RequestsScreen(),
    ),
    GoRoute(
      path: '/profile',
      builder: (context, state) => const ProfileScreen(),
    ),
    GoRoute(
      path: '/notifications',
      builder: (context, state) => const NotificationsScreen(),
    ),
    GoRoute(path: '/more', builder: (context, state) => const MoreScreen()),
    GoRoute(
      path: '/documents',
      builder: (context, state) => const DocumentRequestsScreen(),
    ),
    GoRoute(
      path: '/document-capture',
      builder: (context, state) => const DocumentCaptureScreen(),
    ),
  ],
);
