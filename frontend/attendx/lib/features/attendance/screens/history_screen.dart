import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/api_constants.dart';
import '../../auth/providers/auth_provider.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> _history = [];
  bool _isLoading = true;
  String? _error;
  late DateTime _selectedMonth;

  DateTime get _currentMonth {
    final now = DateTime.now();
    return DateTime(now.year, now.month);
  }

  @override
  void initState() {
    super.initState();
    _selectedMonth = _currentMonth;
    _fetchHistory();
  }

  Future<void> _fetchHistory() async {
    if (mounted) {
      setState(() {
        _isLoading = true;
        _error = null;
      });
    }

    try {
      final token = context.read<AuthProvider>().token;
      final dio = ApiConstants.getAuthenticatedDio(token);
      final monthStart = DateTime(_selectedMonth.year, _selectedMonth.month);
      final monthEnd = DateTime(
        _selectedMonth.year,
        _selectedMonth.month + 1,
        0,
      );
      final records = <dynamic>[];
      String? nextUrl = ApiConstants.attendanceHistory;
      Map<String, dynamic>? query = {
        'from': DateFormat('yyyy-MM-dd').format(monthStart),
        'to': DateFormat('yyyy-MM-dd').format(monthEnd),
      };

      while (nextUrl != null) {
        final response = await dio.get(
          nextUrl,
          queryParameters: query,
          options: Options(validateStatus: (status) => true),
        );
        if (response.statusCode != 200) {
          throw Exception('Failed to load history');
        }

        final payload = response.data;
        if (payload is List) {
          records.addAll(payload);
          nextUrl = null;
        } else if (payload is Map) {
          final page = payload['results'];
          if (page is List) records.addAll(page);
          nextUrl = payload['next']?.toString();
          if (nextUrl?.isEmpty ?? false) nextUrl = null;
        } else {
          nextUrl = null;
        }
        query = null;
      }

      if (!mounted) return;
      setState(() {
        _history = records;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load attendance for this month.';
        _isLoading = false;
      });
    }
  }

  void _changeMonth(int offset) {
    final candidate = DateTime(
      _selectedMonth.year,
      _selectedMonth.month + offset,
    );
    if (candidate.isAfter(_currentMonth)) return;
    setState(() => _selectedMonth = candidate);
    _fetchHistory();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Attendance History',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: Column(
        children: [
          _buildMonthNavigator(),
          Expanded(child: _buildHistoryBody()),
        ],
      ),
    );
  }

  Widget _buildMonthNavigator() {
    final isCurrentMonth = _selectedMonth == _currentMonth;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 2),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            children: [
              IconButton(
                tooltip: 'Previous month',
                onPressed: _isLoading ? null : () => _changeMonth(-1),
                icon: const Icon(Icons.chevron_left),
              ),
              Expanded(
                child: Column(
                  children: [
                    Text(
                      DateFormat('MMMM yyyy').format(_selectedMonth),
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    Text(
                      isCurrentMonth
                          ? 'Current month'
                          : 'Previous attendance backlog',
                      style: const TextStyle(color: Colors.grey, fontSize: 12),
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Next month',
                onPressed: _isLoading || isCurrentMonth
                    ? null
                    : () => _changeMonth(1),
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHistoryBody() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.red),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _fetchHistory,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    if (_history.isEmpty) {
      return RefreshIndicator(
        onRefresh: _fetchHistory,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(height: MediaQuery.sizeOf(context).height * 0.22),
            const Icon(Icons.event_busy_outlined, size: 52, color: Colors.grey),
            const SizedBox(height: 12),
            const Text(
              'No attendance records for this month.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _fetchHistory,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _history.length,
        itemBuilder: (context, index) => _buildHistoryCard(_history[index]),
      ),
    );
  }

  Widget _buildHistoryCard(dynamic item) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final statusText = item['status_display']?.toString() ?? 'Unknown';
    final isAbsent = statusText == 'Absent';
    final isLate = statusText == 'Late';
    var statusColor = Colors.green;
    if (isAbsent) statusColor = Colors.red;
    if (isLate) statusColor = Colors.orange;

    var displayDate = 'Unknown Date';
    var checkIn = '--:--';
    var checkOut = '--:--';
    final checkInRaw = item['check_in_time']?.toString() ?? '';
    if (checkInRaw.isNotEmpty) {
      try {
        final date = DateTime.parse(checkInRaw).toLocal();
        displayDate = DateFormat('EEE, MMM d, yyyy').format(date);
        checkIn = DateFormat('hh:mm a').format(date);
      } catch (_) {}
    }
    final checkOutRaw = item['check_out_time']?.toString() ?? '';
    if (checkOutRaw.isNotEmpty) {
      try {
        checkOut = DateFormat(
          'hh:mm a',
        ).format(DateTime.parse(checkOutRaw).toLocal());
      } catch (_) {}
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.dividerColor),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    displayDate,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    statusText,
                    style: TextStyle(
                      color: statusColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _buildTimeBox(
                    'Check In',
                    checkIn,
                    Icons.login,
                    Colors.blue,
                    isDark,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildTimeBox(
                    'Check Out',
                    checkOut,
                    Icons.logout,
                    Colors.orange,
                    isDark,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeBox(
    String label,
    String time,
    IconData icon,
    Color iconColor,
    bool isDark,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.black.withValues(alpha: 0.18)
            : Colors.white.withValues(alpha: 0.32),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isDark
              ? Colors.white.withValues(alpha: 0.10)
              : Colors.white.withValues(alpha: 0.55),
        ),
      ),
      child: Row(
        children: [
          Icon(icon, size: 20, color: iconColor),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                ),
                Text(
                  time,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
