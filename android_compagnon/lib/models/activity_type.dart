import 'package:flutter/material.dart';

/// The kinds of activities the tracker supports.
enum ActivityType {
  bike,
  hike,
  skitouring;

  String get label {
    switch (this) {
      case ActivityType.bike:
        return 'Bike';
      case ActivityType.hike:
        return 'Hike';
      case ActivityType.skitouring:
        return 'Ski touring';
    }
  }

  IconData get icon {
    switch (this) {
      case ActivityType.bike:
        return Icons.directions_bike;
      case ActivityType.hike:
        return Icons.hiking;
      case ActivityType.skitouring:
        return Icons.downhill_skiing;
    }
  }

  /// Stable identifier persisted in the database and GPX files.
  String get id => name;

  static ActivityType fromId(String id) {
    return ActivityType.values.firstWhere(
      (a) => a.name == id,
      orElse: () => ActivityType.hike,
    );
  }
}
