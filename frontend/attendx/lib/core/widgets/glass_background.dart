import 'dart:ui';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

class GlassBackground extends StatelessWidget {
  const GlassBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    if (kIsWeb) {
      return Stack(
        fit: StackFit.expand,
        children: [
          ColoredBox(
            color: isDark ? const Color(0xFF0A1110) : const Color(0xFFF2F4F1),
          ),
          Positioned.fill(
            child: Image.asset(
              isDark
                  ? 'assets/web_background_dark.webp'
                  : 'assets/web_background_light.webp',
              fit: BoxFit.cover,
              filterQuality: FilterQuality.low,
            ),
          ),
          Positioned.fill(
            child: ColoredBox(
              color: isDark ? const Color(0xB80A1110) : const Color(0xA8F4F7F4),
            ),
          ),
          Positioned.fill(child: child),
        ],
      );
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        const ColoredBox(color: Color(0xFFF2F4F1)),
        Positioned.fill(
          child: ImageFiltered(
            imageFilter: ImageFilter.blur(sigmaX: 30, sigmaY: 30),
            child: Transform.scale(
              scale: 1.16,
              child: Image.asset(
                'assets/glass_background.jpg',
                fit: BoxFit.cover,
                filterQuality: FilterQuality.medium,
              ),
            ),
          ),
        ),
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: isDark
                    ? const [Color(0xC90A1110), Color(0xE6121716)]
                    : const [Color(0xA6FFFFFF), Color(0xD9F4F7F4)],
              ),
            ),
          ),
        ),
        Positioned.fill(child: child),
      ],
    );
  }
}

class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding,
    this.margin,
    this.borderRadius = const BorderRadius.all(Radius.circular(16)),
  });

  final Widget child;
  final EdgeInsetsGeometry? padding;
  final EdgeInsetsGeometry? margin;
  final BorderRadius borderRadius;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final panel = DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? const [Color(0xB8161E1B), Color(0x8F0E1513)]
              : const [Color(0xD1FFFFFF), Color(0x99FFFFFF)],
        ),
        borderRadius: borderRadius,
        border: Border.all(
          color: isDark ? const Color(0x3DFFFFFF) : const Color(0xD9FFFFFF),
        ),
      ),
      child: Padding(padding: padding ?? EdgeInsets.zero, child: child),
    );

    return Container(
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: borderRadius,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: isDark ? 0.30 : 0.10),
            blurRadius: kIsWeb ? 14 : 30,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: borderRadius,
        child: kIsWeb
            ? panel
            : BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                child: panel,
              ),
      ),
    );
  }
}
