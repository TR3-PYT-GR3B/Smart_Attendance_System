import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:attendx/core/providers/theme_provider.dart';

void main() {
  test('starts in dark mode without an asynchronous light-mode frame', () {
    final provider = ThemeProvider(initialIsDarkMode: true);

    expect(provider.themeMode, ThemeMode.dark);
  });

  test('starts in light mode when light mode was selected', () {
    final provider = ThemeProvider(initialIsDarkMode: false);

    expect(provider.themeMode, ThemeMode.light);
  });
}
