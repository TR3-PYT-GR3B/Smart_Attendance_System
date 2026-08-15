import 'dart:typed_data';

import '../platform/file_cleanup.dart';

/// A camera frame that can be uploaded on every supported Flutter platform.
///
/// Bytes are the common representation because browser captures use blob URLs,
/// while Android and iOS captures use temporary file paths.
class CapturedFrame {
  const CapturedFrame({
    required this.bytes,
    required this.filename,
    this.localPath,
  });

  final Uint8List bytes;
  final String filename;
  final String? localPath;

  Future<void> dispose() => deleteLocalFile(localPath);
}
