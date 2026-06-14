/// A single recorded GPS sample belonging to a track.
class TrackPoint {
  final int? id;
  final int? trackId;
  final double latitude;
  final double longitude;
  final double? elevation;
  final DateTime timestamp;
  final double? accuracy;
  final double? speed;

  const TrackPoint({
    this.id,
    this.trackId,
    required this.latitude,
    required this.longitude,
    this.elevation,
    required this.timestamp,
    this.accuracy,
    this.speed,
  });

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'track_id': trackId,
      'latitude': latitude,
      'longitude': longitude,
      'elevation': elevation,
      'timestamp': timestamp.millisecondsSinceEpoch,
      'accuracy': accuracy,
      'speed': speed,
    };
  }

  factory TrackPoint.fromMap(Map<String, Object?> map) {
    return TrackPoint(
      id: map['id'] as int?,
      trackId: map['track_id'] as int?,
      latitude: (map['latitude'] as num).toDouble(),
      longitude: (map['longitude'] as num).toDouble(),
      elevation: (map['elevation'] as num?)?.toDouble(),
      timestamp:
          DateTime.fromMillisecondsSinceEpoch(map['timestamp'] as int),
      accuracy: (map['accuracy'] as num?)?.toDouble(),
      speed: (map['speed'] as num?)?.toDouble(),
    );
  }

  TrackPoint copyWith({int? id, int? trackId}) {
    return TrackPoint(
      id: id ?? this.id,
      trackId: trackId ?? this.trackId,
      latitude: latitude,
      longitude: longitude,
      elevation: elevation,
      timestamp: timestamp,
      accuracy: accuracy,
      speed: speed,
    );
  }
}
