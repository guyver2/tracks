import 'package:flutter/material.dart';
import 'package:flutter_foreground_task/flutter_foreground_task.dart';
import 'package:provider/provider.dart';

import 'services/recording_service.dart';
import 'state/recording_controller.dart';
import 'ui/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterForegroundTask.initCommunicationPort();

  final recordingService = RecordingService()..init();

  runApp(GpsTrackerApp(recordingService: recordingService));
}

class GpsTrackerApp extends StatelessWidget {
  const GpsTrackerApp({super.key, required this.recordingService});

  final RecordingService recordingService;

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => RecordingController(recordingService: recordingService),
      child: MaterialApp(
        title: 'GPS Tracker',
        theme: ThemeData(
          colorSchemeSeed: const Color(0xFF2E7D32),
          useMaterial3: true,
          brightness: Brightness.light,
        ),
        darkTheme: ThemeData(
          colorSchemeSeed: const Color(0xFF2E7D32),
          useMaterial3: true,
          brightness: Brightness.dark,
        ),
        home: const WithForegroundTask(child: HomeScreen()),
      ),
    );
  }
}
