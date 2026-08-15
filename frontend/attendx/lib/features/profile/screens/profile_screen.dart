import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/widgets/glass_background.dart';
import '../../auth/providers/auth_provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    Future.microtask(_refreshProfile);
  }

  Future<void> _refreshProfile() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      await context.read<AuthProvider>().refreshProfile();
    } catch (_) {
      if (mounted) _error = 'Could not refresh your account details.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final profile = auth.profile;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'My Profile',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: _loading && profile.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refreshProfile,
              child: ListView(
                padding: const EdgeInsets.all(24),
                children: [
                  _buildIdentityHeader(context, profile, auth.userName),
                  const SizedBox(height: 24),
                  if (_error != null) ...[
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.red),
                    ),
                    const SizedBox(height: 16),
                  ],
                  _buildProfileField(
                    'Full Name',
                    _value(profile['full_name']),
                    Icons.badge_outlined,
                  ),
                  _buildProfileField(
                    'Email',
                    _value(profile['email']),
                    Icons.email_outlined,
                  ),
                  _buildProfileField(
                    'Phone Number',
                    _value(profile['phone']),
                    Icons.phone_outlined,
                  ),
                  _buildProfileField(
                    'Employee ID',
                    _value(profile['employee_id']),
                    Icons.assignment_ind_outlined,
                  ),
                  _buildProfileField(
                    'Department',
                    _nestedValue(profile, 'department', 'name'),
                    Icons.apartment_outlined,
                  ),
                  _buildProfileField(
                    'Organization',
                    _nestedValue(profile, 'department', 'organization_name'),
                    Icons.business_outlined,
                  ),
                  _buildProfileField(
                    'Role',
                    _displayChoice(profile['role']),
                    Icons.work_outline,
                  ),
                  _buildProfileField(
                    'Employment Status',
                    _displayChoice(profile['employment_status']),
                    Icons.verified_user_outlined,
                  ),
                  _buildProfileField(
                    'Account Created',
                    _dateValue(profile['date_joined']),
                    Icons.calendar_today_outlined,
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'These details come directly from your employee account. Contact an administrator if anything is incorrect.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.grey, fontSize: 12),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildIdentityHeader(
    BuildContext context,
    Map<String, dynamic> profile,
    String fallbackName,
  ) {
    final name = _value(profile['full_name'], fallback: fallbackName);
    final initials = name
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .take(2)
        .map((part) => part[0].toUpperCase())
        .join();

    return Column(
      children: [
        CircleAvatar(
          radius: 50,
          backgroundColor: Theme.of(context).colorScheme.primary,
          child: Text(
            initials.isEmpty ? '?' : initials,
            style: const TextStyle(
              fontSize: 32,
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(height: 14),
        Text(
          name,
          textAlign: TextAlign.center,
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 4),
        Text(
          _value(profile['email']),
          style: Theme.of(
            context,
          ).textTheme.bodyMedium?.copyWith(color: Colors.grey),
        ),
      ],
    );
  }

  Widget _buildProfileField(String label, String value, IconData icon) {
    return GlassPanel(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(16),
      borderRadius: BorderRadius.circular(14),
      child: Row(
        children: [
          Icon(icon, color: Theme.of(context).colorScheme.primary),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(color: Colors.grey, fontSize: 12),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 15,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _value(dynamic raw, {String fallback = 'Not provided'}) {
    final value = raw?.toString().trim() ?? '';
    return value.isEmpty ? fallback : value;
  }

  String _nestedValue(
    Map<String, dynamic> profile,
    String parent,
    String child,
  ) {
    final nested = profile[parent];
    if (nested is! Map) return 'Not assigned';
    return _value(nested[child], fallback: 'Not assigned');
  }

  String _displayChoice(dynamic raw) {
    final value = _value(raw);
    if (value == 'Not provided') return value;
    return value
        .split('_')
        .map(
          (word) => word.isEmpty
              ? word
              : '${word[0].toUpperCase()}${word.substring(1)}',
        )
        .join(' ');
  }

  String _dateValue(dynamic raw) {
    final value = raw?.toString() ?? '';
    if (value.isEmpty) return 'Not provided';
    try {
      return DateFormat('MMMM d, yyyy').format(DateTime.parse(value).toLocal());
    } catch (_) {
      return value;
    }
  }
}
