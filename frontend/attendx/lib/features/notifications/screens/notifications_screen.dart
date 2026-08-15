import 'package:flutter/material.dart';

import '../../../core/widgets/glass_background.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final notifications = [
      {
        'title': 'Check-In Successful',
        'body': 'Your face scan was verified at 08:45 AM.',
        'time': '2 hours ago',
        'icon': Icons.check_circle,
        'color': Colors.green,
      },
      {
        'title': 'Leave Approved',
        'body': 'Your sick leave request for 2 days was approved.',
        'time': '1 day ago',
        'icon': Icons.event_available,
        'color': Colors.blue,
      },
      {
        'title': 'System Alert',
        'body': 'App maintenance scheduled for this weekend.',
        'time': '3 days ago',
        'icon': Icons.info,
        'color': Colors.orange,
      },
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Notifications',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: notifications.isEmpty
          ? const Center(
              child: Text(
                'No new notifications',
                style: TextStyle(color: Colors.grey),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: notifications.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final notif = notifications[index];
                return GlassPanel(
                  borderRadius: BorderRadius.circular(16),
                  child: ListTile(
                    tileColor: Colors.transparent,
                    contentPadding: const EdgeInsets.all(16),
                    leading: CircleAvatar(
                      backgroundColor: (notif['color'] as Color).withValues(
                        alpha: 0.12,
                      ),
                      child: Icon(
                        notif['icon'] as IconData,
                        color: notif['color'] as Color,
                      ),
                    ),
                    title: Text(
                      notif['title'] as String,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const SizedBox(height: 4),
                        Text(notif['body'] as String),
                        const SizedBox(height: 8),
                        Text(
                          notif['time'] as String,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }
}
