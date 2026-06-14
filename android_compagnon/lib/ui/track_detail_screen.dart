import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../data/database.dart';
import '../data/gpx_exporter.dart';
import '../models/track.dart';
import '../models/track_point.dart';
import '../utils/formatting.dart';
import 'widgets/stat_tile.dart';
import 'widgets/track_map.dart';

class TrackDetailScreen extends StatefulWidget {
  const TrackDetailScreen({super.key, required this.trackId});

  final int trackId;

  @override
  State<TrackDetailScreen> createState() => _TrackDetailScreenState();
}

class _TrackDetailScreenState extends State<TrackDetailScreen> {
  Track? _track;
  List<TrackPoint> _points = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final track = await TrackDatabase.instance.getTrack(widget.trackId);
    final points = await TrackDatabase.instance.getPoints(widget.trackId);
    if (!mounted) return;
    setState(() {
      _track = track;
      _points = points;
      _loading = false;
    });
  }

  Future<void> _rename() async {
    final track = _track;
    if (track == null) return;
    final controller = TextEditingController(text: track.name);
    final name = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename'),
        content: TextField(
          controller: controller,
          autofocus: true,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(border: OutlineInputBorder()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(controller.text.trim()),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    await TrackDatabase.instance.renameTrack(track.id!, name);
    await _load();
  }

  Future<void> _delete() async {
    final track = _track;
    if (track == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete recording?'),
        content: Text('"${track.name}" will be permanently removed.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await TrackDatabase.instance.deleteTrack(track.id!);
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _export() async {
    final track = _track;
    if (track == null) return;
    if (_points.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No GPS points to export.')),
      );
      return;
    }
    await GpxExporter().share(track, _points);
  }

  @override
  Widget build(BuildContext context) {
    final track = _track;
    return Scaffold(
      appBar: AppBar(
        title: Text(track?.name ?? 'Recording'),
        actions: [
          IconButton(
            tooltip: 'Rename',
            icon: const Icon(Icons.edit_outlined),
            onPressed: _loading ? null : _rename,
          ),
          IconButton(
            tooltip: 'Export GPX',
            icon: const Icon(Icons.ios_share),
            onPressed: _loading ? null : _export,
          ),
          IconButton(
            tooltip: 'Delete',
            icon: const Icon(Icons.delete_outline),
            onPressed: _loading ? null : _delete,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : track == null
              ? const Center(child: Text('Recording not found.'))
              : Column(
                  children: [
                    Expanded(child: TrackMap(points: _points)),
                    _StatsPanel(track: track),
                  ],
                ),
    );
  }
}

class _StatsPanel extends StatelessWidget {
  const _StatsPanel({required this.track});

  final Track track;

  @override
  Widget build(BuildContext context) {
    final duration = Duration(seconds: track.durationSeconds);
    final date = DateFormat('EEEE, MMM d, yyyy - HH:mm').format(track.startTime);

    return Container(
      width: double.infinity,
      color: Theme.of(context).colorScheme.surface,
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(track.activity.icon, size: 18),
              const SizedBox(width: 6),
              Text(track.activity.label),
              const SizedBox(width: 12),
              Text(date, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              StatTile(
                label: 'Distance',
                value: formatDistance(track.distanceMeters),
                icon: Icons.straighten,
              ),
              StatTile(
                label: 'Time',
                value: formatDuration(duration),
                icon: Icons.timer_outlined,
              ),
              StatTile(
                label: 'Avg speed',
                value: formatAvgSpeed(track.distanceMeters, duration),
                icon: Icons.speed,
              ),
              StatTile(
                label: 'Ascent',
                value: formatElevation(track.elevationGainMeters),
                icon: Icons.terrain,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
