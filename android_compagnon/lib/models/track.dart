import 'activity_type.dart';

/// A saved recording: metadata plus (when loaded) its points.
class Track {
  final int? id;
  final String name;
  final ActivityType activity;
  final DateTime startTime;
  final DateTime? endTime;
  final double distanceMeters;
  final int durationSeconds;
  final double elevationGainMeters;

  const Track({
    this.id,
    required this.name,
    required this.activity,
    required this.startTime,
    this.endTime,
    this.distanceMeters = 0,
    this.durationSeconds = 0,
    this.elevationGainMeters = 0,
  });

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'name': name,
      'activity': activity.id,
      'start_time': startTime.millisecondsSinceEpoch,
      'end_time': endTime?.millisecondsSinceEpoch,
      'distance_meters': distanceMeters,
      'duration_seconds': durationSeconds,
      'elevation_gain_meters': elevationGainMeters,
    };
  }

  factory Track.fromMap(Map<String, Object?> map) {
    return Track(
      id: map['id'] as int?,
      name: map['name'] as String,
      activity: ActivityType.fromId(map['activity'] as String),
      startTime:
          DateTime.fromMillisecondsSinceEpoch(map['start_time'] as int),
      endTime: map['end_time'] == null
          ? null
          : DateTime.fromMillisecondsSinceEpoch(map['end_time'] as int),
      distanceMeters: (map['distance_meters'] as num?)?.toDouble() ?? 0,
      durationSeconds: (map['duration_seconds'] as num?)?.toInt() ?? 0,
      elevationGainMeters:
          (map['elevation_gain_meters'] as num?)?.toDouble() ?? 0,
    );
  }

  Track copyWith({
    int? id,
    String? name,
    DateTime? endTime,
    double? distanceMeters,
    int? durationSeconds,
    double? elevationGainMeters,
  }) {
    return Track(
      id: id ?? this.id,
      name: name ?? this.name,
      activity: activity,
      startTime: startTime,
      endTime: endTime ?? this.endTime,
      distanceMeters: distanceMeters ?? this.distanceMeters,
      durationSeconds: durationSeconds ?? this.durationSeconds,
      elevationGainMeters: elevationGainMeters ?? this.elevationGainMeters,
    );
  }
}
