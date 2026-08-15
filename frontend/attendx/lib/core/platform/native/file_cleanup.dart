import 'dart:io';

Future<void> deleteLocalFile(String? path) async {
  if (path == null || path.isEmpty) return;
  try {
    final file = File(path);
    if (await file.exists()) await file.delete();
  } catch (_) {
    // Camera files are temporary; cleanup failure must not break the flow.
  }
}
