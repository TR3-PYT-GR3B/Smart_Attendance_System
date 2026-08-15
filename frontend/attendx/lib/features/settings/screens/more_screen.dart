import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../../../core/providers/theme_provider.dart';
import '../../../core/widgets/glass_background.dart';
import '../../auth/providers/auth_provider.dart';

class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final themeProvider = context.watch<ThemeProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'More',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildMenuSection(
            title: 'Account',
            items: [
              _buildMenuItem(
                Icons.person_outline,
                'My Profile',
                () => context.push('/profile'),
              ),
              _buildMenuItem(
                Icons.folder_copy_outlined,
                'Office Documents',
                () => context.push('/documents'),
              ),
            ],
          ),
          const SizedBox(height: 24),
          _buildMenuSection(
            title: 'Preferences',
            items: [
              _buildMenuItem(
                Icons.dark_mode_outlined,
                'Dark Mode',
                () => themeProvider.toggleTheme(),
                trailing: Switch(
                  value: themeProvider.isDarkMode,
                  onChanged: (_) => themeProvider.toggleTheme(),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          _buildMenuSection(
            title: 'Support',
            items: [
              _buildMenuItem(Icons.help_outline, 'Help Center', () {}),
              _buildMenuItem(Icons.info_outline, 'About App', () {
                showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: Row(
                      children: [
                        const Icon(
                          Icons.face,
                          size: 30,
                          color: Color(0xFF096D47),
                        ),
                        const SizedBox(width: 12),
                        const Text('AttendX'),
                      ],
                    ),
                    content: const Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Version 1.0.0',
                          style: TextStyle(color: Colors.grey),
                        ),
                        SizedBox(height: 16),
                        Text('Smart Face Recognition Attendance System.'),
                      ],
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Close'),
                      ),
                    ],
                  ),
                );
              }),
            ],
          ),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () async {
              await context.read<AuthProvider>().logout();
              if (context.mounted) context.go('/login');
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red.withValues(alpha: 0.12),
              foregroundColor: Colors.red,
              elevation: 0,
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
            child: const Text(
              'Log Out',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMenuSection({
    required String title,
    required List<Widget> items,
  }) {
    return Builder(
      builder: (context) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 8, bottom: 8),
              child: Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.grey,
                ),
              ),
            ),
            GlassPanel(
              borderRadius: BorderRadius.circular(12),
              child: Column(children: items),
            ),
          ],
        );
      },
    );
  }

  Widget _buildMenuItem(
    IconData icon,
    String title,
    VoidCallback onTap, {
    Widget? trailing,
  }) {
    return Builder(
      builder: (context) {
        final isDark = Theme.of(context).brightness == Brightness.dark;
        return ListTile(
          leading: Icon(icon, color: isDark ? Colors.white70 : Colors.black87),
          title: Text(
            title,
            style: TextStyle(color: isDark ? Colors.white : Colors.black87),
          ),
          trailing:
              trailing ??
              Icon(
                Icons.chevron_right,
                color: isDark ? Colors.grey.shade600 : Colors.grey,
              ),
          onTap: onTap,
        );
      },
    );
  }
}
