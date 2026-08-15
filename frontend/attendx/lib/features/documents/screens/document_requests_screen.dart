import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/models/captured_frame.dart';
import '../../auth/providers/auth_provider.dart';

class DocumentRequestsScreen extends StatefulWidget {
  const DocumentRequestsScreen({super.key});

  @override
  State<DocumentRequestsScreen> createState() => _DocumentRequestsScreenState();
}

class _DocumentRequestsScreenState extends State<DocumentRequestsScreen> {
  List<dynamic> _requests = [];
  bool _loading = true;
  int? _uploadingRequestId;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchRequests();
  }

  Future<void> _fetchRequests() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final dio = ApiConstants.getAuthenticatedDio(
        context.read<AuthProvider>().token,
      );
      final rows = <dynamic>[];
      String? nextUrl = ApiConstants.documentRequests;
      while (nextUrl != null) {
        final response = await dio.get(nextUrl);
        final payload = response.data;
        if (payload is List) {
          rows.addAll(payload);
          nextUrl = null;
        } else if (payload is Map) {
          if (payload['results'] is List) rows.addAll(payload['results']);
          nextUrl = payload['next']?.toString();
          if (nextUrl?.isEmpty ?? false) nextUrl = null;
        } else {
          nextUrl = null;
        }
      }
      if (!mounted) return;
      setState(() {
        _requests = rows;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load document requests.';
        _loading = false;
      });
    }
  }

  Future<void> _captureAndSubmit(Map<String, dynamic> request) async {
    final frame = await context.push<CapturedFrame>('/document-capture');
    if (frame == null || !mounted) return;
    final requestId = (request['id'] as num).toInt();
    final token = context.read<AuthProvider>().token;
    setState(() => _uploadingRequestId = requestId);

    try {
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(frame.bytes, filename: frame.filename),
      });
      await ApiConstants.getAuthenticatedDio(
        token,
      ).post(ApiConstants.submitDocumentRequest(requestId), data: formData);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Document sent for office review.'),
          backgroundColor: Colors.green,
        ),
      );
      await _fetchRequests();
    } on DioException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _messageFrom(error.response?.data) ?? 'Document upload failed.',
          ),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      await frame.dispose();
      if (mounted) setState(() => _uploadingRequestId = null);
    }
  }

  String? _messageFrom(dynamic data) {
    if (data is Map && data['detail'] != null) return data['detail'].toString();
    if (data is Map && data['file'] is List && data['file'].isNotEmpty) {
      return data['file'].first.toString();
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Office Documents',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
          ? _buildError()
          : _requests.isEmpty
          ? _buildEmpty()
          : RefreshIndicator(
              onRefresh: _fetchRequests,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _requests.length,
                itemBuilder: (context, index) => _buildRequestCard(
                  Map<String, dynamic>.from(_requests[index] as Map),
                ),
              ),
            ),
    );
  }

  Widget _buildRequestCard(Map<String, dynamic> request) {
    final status = request['status']?.toString() ?? 'pending';
    final isPending = status == 'pending';
    final isSubmitted = status == 'submitted';
    final isCompleted = status == 'completed';
    final isCancelled = status == 'cancelled';
    final isClosed = status == 'closed';
    final isOverdue = request['is_overdue'] == true;
    final requestId = (request['id'] as num).toInt();
    final isUploading = _uploadingRequestId == requestId;
    final latest = request['latest_submission'];
    final rejectionReason = latest is Map
        ? latest['rejection_reason']?.toString() ?? ''
        : '';

    final Color statusColor;
    final IconData statusIcon;
    if (isCompleted) {
      statusColor = Colors.green;
      statusIcon = Icons.verified_outlined;
    } else if (isSubmitted) {
      statusColor = Colors.blue;
      statusIcon = Icons.hourglass_top;
    } else if (isCancelled || isClosed) {
      statusColor = Colors.grey;
      statusIcon = isClosed ? Icons.lock_outline : Icons.cancel_outlined;
    } else if (isOverdue) {
      statusColor = Colors.red;
      statusIcon = Icons.warning_amber;
    } else {
      statusColor = Colors.orange;
      statusIcon = Icons.upload_file_outlined;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(statusIcon, color: statusColor),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request['title']?.toString() ?? 'Document request',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        request['document_type_display']?.toString() ??
                            'Document',
                        style: const TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if ((request['instructions']?.toString() ?? '').isNotEmpty) ...[
              const SizedBox(height: 14),
              Text(
                request['instructions'].toString(),
                style: const TextStyle(height: 1.45),
              ),
            ],
            if (request['due_date'] != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(
                    Icons.event_outlined,
                    size: 18,
                    color: isOverdue ? Colors.red : Colors.grey,
                  ),
                  const SizedBox(width: 7),
                  Text(
                    '${isOverdue ? 'Overdue' : 'Due'} ${_formatDate(request['due_date'])}',
                    style: TextStyle(
                      color: isOverdue ? Colors.red : Colors.grey,
                      fontWeight: isOverdue
                          ? FontWeight.bold
                          : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ],
            if (rejectionReason.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text('Please retake: $rejectionReason'),
              ),
            ],
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Text(
                    request['status_display']?.toString() ?? 'Awaiting Upload',
                    style: TextStyle(
                      color: statusColor,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                if (isPending)
                  ElevatedButton.icon(
                    onPressed: isUploading
                        ? null
                        : () => _captureAndSubmit(request),
                    icon: isUploading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.camera_alt_outlined),
                    label: Text(isUploading ? 'Sending' : 'Snap & send'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmpty() {
    return RefreshIndicator(
      onRefresh: _fetchRequests,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          SizedBox(height: MediaQuery.sizeOf(context).height * 0.24),
          const Icon(Icons.task_alt, size: 62, color: Colors.green),
          const SizedBox(height: 16),
          const Text(
            'No documents are required from you.',
            textAlign: TextAlign.center,
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 17),
          ),
          const SizedBox(height: 6),
          const Text(
            'New office requests will appear here.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(_error!, style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: _fetchRequests, child: const Text('Retry')),
        ],
      ),
    );
  }

  String _formatDate(dynamic raw) {
    try {
      return DateFormat('MMM d, yyyy').format(DateTime.parse(raw.toString()));
    } catch (_) {
      return raw.toString();
    }
  }
}
