import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/recording_controller.dart';
import '../utils/formatting.dart';
import 'track_detail_screen.dart';
import 'widgets/stat_tile.dart';
import 'widgets/track_map.dart';

/// Live recording view. A session must already be started on the controller
/// before this screen is pushed.
class RecordingScreen extends StatelessWidget {
  const RecordingScreen({super.key});

  Future<void> _confirmAndStop(BuildContext context) async {
    final controller = context.read<RecordingController>();
    final nameController = TextEditingController();

    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Finish recording?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Save this activity with a name:'),
              const SizedBox(height: 12),
              TextField(
                controller: nameController,
                autofocus: true,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  labelText: 'Name (optional)',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Keep recording'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    if (result != true) return;

    final trackId = await controller.finish(name: nameController.text);
    if (!context.mounted) return;

    if (trackId != null) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => TrackDetailScreen(trackId: trackId),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Recording discarded (no GPS data).')),
      );
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<RecordingController>();
    final isPaused = controller.state == RecordingState.paused;

    return Scaffold(
      appBar: AppBar(
        title: Text(controller.activity?.label ?? 'Recording'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Keep recording in background',
          onPressed: () => Navigator.of(context).maybePop(),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: TrackMap(points: controller.points, live: true),
          ),
          Container(
            color: Theme.of(context).colorScheme.surface,
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
            child: Column(
              children: [
                if (isPaused)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      'PAUSED',
                      style: Theme.of(context)
                          .textTheme
                          .labelLarge
                          ?.copyWith(color: Colors.orange),
                    ),
                  ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    StatTile(
                      label: 'Time',
                      value: formatDuration(controller.elapsed),
                      icon: Icons.timer_outlined,
                    ),
                    StatTile(
                      label: 'Distance',
                      value: formatDistance(controller.distanceMeters),
                      icon: Icons.straighten,
                    ),
                    StatTile(
                      label: 'Speed',
                      value: formatSpeed(controller.currentSpeed),
                      icon: Icons.speed,
                    ),
                    StatTile(
                      label: 'Ascent',
                      value: formatElevation(controller.elevationGain),
                      icon: Icons.terrain,
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _ControlButton(
                      label: isPaused ? 'Resume' : 'Pause',
                      icon: isPaused ? Icons.play_arrow : Icons.pause,
                      color: Colors.orange,
                      onPressed: () {
                        if (isPaused) {
                          controller.resume();
                        } else {
                          controller.pause();
                        }
                      },
                    ),
                    _ControlButton(
                      label: 'Stop',
                      icon: Icons.stop,
                      color: Colors.red,
                      onPressed: () => _confirmAndStop(context),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ControlButton extends StatelessWidget {
  const _ControlButton({
    required this.label,
    required this.icon,
    required this.color,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        FloatingActionButton(
          heroTag: label,
          backgroundColor: color,
          foregroundColor: Colors.white,
          onPressed: onPressed,
          child: Icon(icon),
        ),
        const SizedBox(height: 6),
        Text(label),
      ],
    );
  }
}
