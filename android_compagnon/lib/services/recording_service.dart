import 'package:flutter_foreground_task/flutter_foreground_task.dart';

/// Entry point for the foreground service isolate.
///
/// We keep the actual GPS collection in the main isolate (the foreground
/// service merely keeps the app process alive). This handler only needs to
/// exist so Android shows the persistent notification.
@pragma('vm:entry-point')
void startCallback() {
  FlutterForegroundTask.setTaskHandler(_RecordingTaskHandler());
}

class _RecordingTaskHandler extends TaskHandler {
  @override
  Future<void> onStart(DateTime timestamp, TaskStarter starter) async {}

  @override
  void onRepeatEvent(DateTime timestamp) {}

  @override
  Future<void> onDestroy(DateTime timestamp, bool isTimeout) async {}
}

/// Manages the Android foreground service that keeps recording alive in the
/// background and shows the persistent notification.
class RecordingService {
  bool _initialized = false;

  void init() {
    if (_initialized) return;
    FlutterForegroundTask.init(
      androidNotificationOptions: AndroidNotificationOptions(
        channelId: 'gps_tracker_recording',
        channelName: 'GPS Recording',
        channelDescription: 'Keeps your activity recording while in background.',
        channelImportance: NotificationChannelImportance.LOW,
        priority: NotificationPriority.LOW,
      ),
      iosNotificationOptions: const IOSNotificationOptions(),
      foregroundTaskOptions: ForegroundTaskOptions(
        eventAction: ForegroundTaskEventAction.nothing(),
        autoRunOnBoot: false,
        autoRunOnMyPackageReplaced: false,
        allowWakeLock: true,
        allowWifiLock: true,
      ),
    );
    _initialized = true;
  }

  Future<void> requestPermissions() async {
    final notification =
        await FlutterForegroundTask.checkNotificationPermission();
    if (notification != NotificationPermission.granted) {
      await FlutterForegroundTask.requestNotificationPermission();
    }
  }

  Future<void> start({required String title, required String text}) async {
    init();
    if (await FlutterForegroundTask.isRunningService) {
      await updateNotification(title: title, text: text);
      return;
    }
    await FlutterForegroundTask.startService(
      serviceId: 1001,
      notificationTitle: title,
      notificationText: text,
      callback: startCallback,
    );
  }

  Future<void> updateNotification({
    required String title,
    required String text,
  }) async {
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.updateService(
        notificationTitle: title,
        notificationText: text,
      );
    }
  }

  Future<void> stop() async {
    if (await FlutterForegroundTask.isRunningService) {
      await FlutterForegroundTask.stopService();
    }
  }
}
