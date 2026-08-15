import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeProvider extends ChangeNotifier {
  static const String _themePrefsKey = 'isDarkMode';
  bool _isDarkMode;

  ThemeProvider({required bool initialIsDarkMode})
    : _isDarkMode = initialIsDarkMode;

  bool get isDarkMode => _isDarkMode;
  ThemeMode get themeMode => _isDarkMode ? ThemeMode.dark : ThemeMode.light;

  static Future<bool> loadInitialIsDarkMode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_themePrefsKey) ??
        WidgetsBinding.instance.platformDispatcher.platformBrightness ==
            Brightness.dark;
  }

  Future<void> toggleTheme() async {
    _isDarkMode = !_isDarkMode;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_themePrefsKey, _isDarkMode);
    notifyListeners();
  }
}
