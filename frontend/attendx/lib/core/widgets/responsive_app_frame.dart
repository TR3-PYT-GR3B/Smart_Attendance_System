import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

/// Keeps the browser experience visually consistent with the mobile app while
/// avoiding extremely wide cards and camera previews on desktop monitors.
class ResponsiveAppFrame extends StatelessWidget {
  const ResponsiveAppFrame({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb) return child;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720),
        child: SizedBox(
          width: double.infinity,
          height: double.infinity,
          child: child,
        ),
      ),
    );
  }
}
