/// Human-readable formatting helpers for stats shown across the UI.
String formatDuration(Duration d) {
  final hours = d.inHours;
  final minutes = d.inMinutes.remainder(60);
  final seconds = d.inSeconds.remainder(60);
  String two(int n) => n.toString().padLeft(2, '0');
  if (hours > 0) {
    return '$hours:${two(minutes)}:${two(seconds)}';
  }
  return '${two(minutes)}:${two(seconds)}';
}

String formatDistance(double meters) {
  if (meters < 1000) {
    return '${meters.toStringAsFixed(0)} m';
  }
  return '${(meters / 1000).toStringAsFixed(2)} km';
}

String formatElevation(double meters) {
  return '${meters.toStringAsFixed(0)} m';
}

/// Speed in m/s -> km/h string.
String formatSpeed(double? metersPerSecond) {
  if (metersPerSecond == null || metersPerSecond <= 0) {
    return '0.0 km/h';
  }
  return '${(metersPerSecond * 3.6).toStringAsFixed(1)} km/h';
}

/// Average speed from distance and duration.
String formatAvgSpeed(double meters, Duration duration) {
  if (duration.inSeconds == 0) return '0.0 km/h';
  final mps = meters / duration.inSeconds;
  return formatSpeed(mps);
}
