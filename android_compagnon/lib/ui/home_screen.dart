import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../data/database.dart';
import '../models/track.dart';
import '../state/recording_controller.dart';
import '../utils/formatting.dart';
import 'activity_picker.dart';
import 'recording_screen.dart';
import 'track_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<Track>> _tracksFuture;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _tracksFuture = TrackDatabase.instance.getTracks();
  }

  Future<void> _openRecording() async {
    final controller = context.read<RecordingController>();

    if (controller.isActive) {
      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const RecordingScreen()),
      );
      if (mounted) setState(_reload);
      return;
    }

    final activity = await showActivityPicker(context);
    if (activity == null || !mounted) return;

    final granted = await controller.prepare();
    if (!mounted) return;
    if (!granted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Location permission is required. Enable it in settings and ensure '
            'location services are on.',
          ),
        ),
      );
      return;
    }

    await controller.start(activity);
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const RecordingScreen()),
    );
    if (mounted) setState(_reload);
  }

  Future<void> _openDetail(Track track) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TrackDetailScreen(trackId: track.id!),
      ),
    );
    if (mounted) setState(_reload);
  }

  @override
  Widget build(BuildContext context) {
    final recording = context.watch<RecordingController>();

    return Scaffold(
      appBar: AppBar(title: const Text('GPS Tracker')),
      body: Column(
        children: [
          if (recording.isActive)
            Material(
              color: Theme.of(context).colorScheme.primaryContainer,
              child: ListTile(
                leading: const Icon(Icons.fiber_manual_record,
                    color: Colors.red),
                title: Text(
                  'Recording ${recording.activity?.label ?? ''}',
                ),
                subtitle: Text(
                  '${formatDuration(recording.elapsed)} - '
                  '${formatDistance(recording.distanceMeters)}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: _openRecording,
              ),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async => setState(_reload),
              child: FutureBuilder<List<Track>>(
                future: _tracksFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final tracks = snapshot.data ?? [];
                  if (tracks.isEmpty) {
                    return ListView(
                      children: [
                        const SizedBox(height: 120),
                        Icon(
                          Icons.map_outlined,
                          size: 64,
                          color: Theme.of(context).colorScheme.outline,
                        ),
                        const SizedBox(height: 16),
                        const Center(
                          child: Text('No recordings yet.\nTap + to start.',
                              textAlign: TextAlign.center),
                        ),
                      ],
                    );
                  }
                  return ListView.separated(
                    itemCount: tracks.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final track = tracks[index];
                      return _TrackTile(
                        track: track,
                        onTap: () => _openDetail(track),
                      );
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openRecording,
        icon: Icon(recording.isActive ? Icons.fiber_manual_record : Icons.add),
        label: Text(recording.isActive ? 'Resume' : 'Record'),
      ),
    );
  }
}

class _TrackTile extends StatelessWidget {
  const _TrackTile({required this.track, required this.onTap});

  final Track track;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final date = DateFormat('EEE, MMM d - HH:mm').format(track.startTime);
    return ListTile(
      leading: CircleAvatar(child: Icon(track.activity.icon)),
      title: Text(track.name),
      subtitle: Text(
        '$date\n'
        '${formatDistance(track.distanceMeters)}  -  '
        '${formatDuration(Duration(seconds: track.durationSeconds))}  -  '
        '${formatElevation(track.elevationGainMeters)} ascent',
      ),
      isThreeLine: true,
      onTap: onTap,
    );
  }
}
