import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:dio/dio.dart';
import 'package:intl/intl.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/constants/api_constants.dart';

class RequestsScreen extends StatefulWidget {
  const RequestsScreen({super.key});

  @override
  State<RequestsScreen> createState() => _RequestsScreenState();
}

class _RequestsScreenState extends State<RequestsScreen> {
  List<dynamic> _requests = [];
  List<dynamic> _leaveTypes = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  Future<void> _fetchData() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final token = context.read<AuthProvider>().token;
      final dio = ApiConstants.getAuthenticatedDio(token);

      // Fetch leave types and requests concurrently
      final responses = await Future.wait([
        dio.get(
          ApiConstants.leaveTypes,
          options: Options(validateStatus: (status) => true),
        ),
        dio.get(
          ApiConstants.leaveRequests,
          options: Options(validateStatus: (status) => true),
        ),
      ]);

      final typesResponse = responses[0];
      final requestsResponse = responses[1];

      if (typesResponse.statusCode == 200 &&
          requestsResponse.statusCode == 200) {
        setState(() {
          _leaveTypes = typesResponse.data['results'] ?? typesResponse.data;
          _requests = requestsResponse.data['results'] ?? requestsResponse.data;
          _isLoading = false;
        });
      } else {
        setState(() {
          _error = 'Failed to load data';
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Network error occurred';
        _isLoading = false;
      });
    }
  }

  void _showRequestModal() {
    if (_leaveTypes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No leave types available.')),
      );
      return;
    }

    int? selectedTypeId = _leaveTypes.first['id'];
    DateTimeRange? selectedDateRange;
    final reasonController = TextEditingController();
    bool isSubmitting = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                bottom: MediaQuery.of(context).viewInsets.bottom,
                left: 24,
                right: 24,
                top: 24,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    'New Leave Request',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 24),
                  DropdownButtonFormField<int>(
                    initialValue: selectedTypeId,
                    decoration: const InputDecoration(
                      labelText: 'Leave Type',
                      border: OutlineInputBorder(),
                    ),
                    items: _leaveTypes.map((type) {
                      return DropdownMenuItem<int>(
                        value: type['id'],
                        child: Text(type['name']),
                      );
                    }).toList(),
                    onChanged: (val) {
                      setModalState(() {
                        selectedTypeId = val;
                      });
                    },
                  ),
                  const SizedBox(height: 16),
                  InkWell(
                    onTap: () async {
                      final now = DateTime.now();
                      final result = await showDateRangePicker(
                        context: context,
                        firstDate: now,
                        lastDate: now.add(const Duration(days: 365)),
                      );
                      if (result != null) {
                        setModalState(() {
                          selectedDateRange = result;
                        });
                      }
                    },
                    child: InputDecorator(
                      decoration: const InputDecoration(
                        labelText: 'Date Range',
                        border: OutlineInputBorder(),
                      ),
                      child: Text(
                        selectedDateRange == null
                            ? 'Select dates'
                            : '${DateFormat('MMM dd').format(selectedDateRange!.start)} - ${DateFormat('MMM dd, yyyy').format(selectedDateRange!.end)}',
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: reasonController,
                    decoration: const InputDecoration(
                      labelText: 'Reason for Leave',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 3,
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: isSubmitting
                        ? null
                        : () async {
                            if (selectedTypeId == null ||
                                selectedDateRange == null ||
                                reasonController.text.trim().isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Please fill out all fields.'),
                                ),
                              );
                              return;
                            }

                            setModalState(() {
                              isSubmitting = true;
                            });

                            try {
                              final navigator = Navigator.of(context);
                              final messenger = ScaffoldMessenger.of(context);
                              final token = context.read<AuthProvider>().token;
                              final dio = ApiConstants.getAuthenticatedDio(
                                token,
                              );
                              final response = await dio.post(
                                ApiConstants.leaveRequests,
                                data: {
                                  'leave_type': selectedTypeId,
                                  'start_date': DateFormat(
                                    'yyyy-MM-dd',
                                  ).format(selectedDateRange!.start),
                                  'end_date': DateFormat(
                                    'yyyy-MM-dd',
                                  ).format(selectedDateRange!.end),
                                  'reason': reasonController.text.trim(),
                                },
                                options: Options(
                                  validateStatus: (status) => true,
                                ),
                              );

                              if (!context.mounted) return;
                              if (response.statusCode == 201) {
                                navigator.pop();
                                _fetchData(); // Refresh list
                                messenger.showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      'Leave request submitted successfully.',
                                    ),
                                  ),
                                );
                              } else {
                                messenger.showSnackBar(
                                  SnackBar(
                                    content: Text('Error: ${response.data}'),
                                  ),
                                );
                                setModalState(() {
                                  isSubmitting = false;
                                });
                              }
                            } catch (e) {
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Network error. Failed to submit.',
                                  ),
                                ),
                              );
                              setModalState(() {
                                isSubmitting = false;
                              });
                            }
                          },
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: isSubmitting
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2,
                            ),
                          )
                        : const Text('Submit Request'),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'My Requests',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showRequestModal,
        icon: const Icon(Icons.add),
        label: const Text('Request Leave'),
        backgroundColor: theme.primaryColor,
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? Center(
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            )
          : _requests.isEmpty
          ? const Center(child: Text('No leave requests found.'))
          : RefreshIndicator(
              onRefresh: _fetchData,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _requests.length,
                itemBuilder: (context, index) {
                  final req = _requests[index];
                  final status = req['status'] ?? 'pending';
                  final statusDisplay = status.toString().toUpperCase();

                  Color statusColor = Colors.orange;
                  if (status == 'approved') statusColor = Colors.green;
                  if (status == 'rejected') statusColor = Colors.red;

                  String dateStr = req['created_at'] ?? '';
                  String displayDate = '';
                  if (dateStr.isNotEmpty) {
                    try {
                      displayDate = DateFormat(
                        'MMM dd, yyyy',
                      ).format(DateTime.parse(dateStr).toLocal());
                    } catch (_) {}
                  }

                  return Card(
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 12),
                    color: theme.cardColor,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: BorderSide(color: theme.dividerColor),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                req['leave_type_name'] ?? 'Leave',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: statusColor.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(20),
                                ),
                                child: Text(
                                  statusDisplay,
                                  style: TextStyle(
                                    color: statusColor,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Submitted: $displayDate',
                            style: const TextStyle(
                              color: Colors.grey,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 12),
                          Text('Reason: ${req['reason']}'),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              _buildInfoBadge(
                                'Requested',
                                '${req['total_days'] ?? 0} Days',
                                Colors.blue,
                                isDark,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
    );
  }

  Widget _buildInfoBadge(String label, String value, Color color, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.2 : 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Text('$label: ', style: TextStyle(fontSize: 12, color: color)),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 12,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
