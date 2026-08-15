class AppLinks {
  AppLinks._();

  /// Supply at build time with:
  /// --dart-define=MOBILE_APP_DOWNLOAD_URL=https://example.com/attendx.apk
  static const mobileAppDownloadUrl = String.fromEnvironment(
    'MOBILE_APP_DOWNLOAD_URL',
    defaultValue: '',
  );
}
