import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../models/track_point.dart';

/// Renders a track polyline over OpenStreetMap tiles.
///
/// In [live] mode the camera follows the latest point; otherwise it fits the
/// whole track on first build.
class TrackMap extends StatefulWidget {
  const TrackMap({
    super.key,
    required this.points,
    this.live = false,
  });

  final List<TrackPoint> points;
  final bool live;

  @override
  State<TrackMap> createState() => _TrackMapState();
}

class _TrackMapState extends State<TrackMap> {
  final MapController _controller = MapController();
  bool _ready = false;

  List<LatLng> get _latLngs =>
      widget.points.map((p) => LatLng(p.latitude, p.longitude)).toList();

  @override
  void didUpdateWidget(covariant TrackMap oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.live && _ready && _latLngs.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _controller.move(_latLngs.last, _controller.camera.zoom);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final points = _latLngs;

    if (points.isEmpty) {
      return Container(
        color: theme.colorScheme.surfaceContainerHighest,
        alignment: Alignment.center,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.satellite_alt, size: 40),
            const SizedBox(height: 8),
            Text('Waiting for GPS fix...', style: theme.textTheme.bodyMedium),
          ],
        ),
      );
    }

    final fit = points.length == 1
        ? null
        : CameraFit.bounds(
            bounds: LatLngBounds.fromPoints(points),
            padding: const EdgeInsets.all(40),
          );

    return FlutterMap(
      mapController: _controller,
      options: MapOptions(
        initialCenter: points.last,
        initialZoom: 15,
        initialCameraFit: widget.live ? null : fit,
        onMapReady: () => _ready = true,
        interactionOptions: const InteractionOptions(
          flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
        ),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.gps_tracker',
          maxZoom: 19,
        ),
        PolylineLayer(
          polylines: [
            Polyline(
              points: points,
              strokeWidth: 5,
              color: theme.colorScheme.primary,
            ),
          ],
        ),
        MarkerLayer(
          markers: [
            Marker(
              point: points.first,
              width: 18,
              height: 18,
              child: const _Dot(color: Colors.green),
            ),
            Marker(
              point: points.last,
              width: 18,
              height: 18,
              child: _Dot(color: widget.live ? Colors.blue : Colors.red),
            ),
          ],
        ),
      ],
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 3),
      ),
    );
  }
}
