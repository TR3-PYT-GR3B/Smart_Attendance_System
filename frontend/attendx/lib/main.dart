import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme.dart';
import 'core/router.dart';
import 'core/providers/theme_provider.dart';
import 'core/widgets/glass_background.dart';
import 'core/widgets/responsive_app_frame.dart';
import 'features/auth/providers/auth_provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final initialIsDarkMode = await ThemeProvider.loadInitialIsDarkMode();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(
          create: (_) => ThemeProvider(initialIsDarkMode: initialIsDarkMode),
        ),
      ],
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ThemeProvider>(
      builder: (context, themeProvider, child) {
        return MaterialApp.router(
          title: 'AttendX',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: themeProvider.themeMode,
          routerConfig: router,
          builder: (context, child) => GlassBackground(
            child: ResponsiveAppFrame(child: child ?? const SizedBox.shrink()),
          ),
          debugShowCheckedModeBanner: false,
        );
      },
    );
  }
}
