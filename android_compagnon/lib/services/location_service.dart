import 'package:geolocator/geolocator.dart';

/// Wraps geolocator: permission handling and the high-accuracy position stream.
class LocationService {
  /// Requests the permissions needed to record while in the foreground.
  ///
  /// Returns true if at least "while in use" location access was granted and
  /// location services are enabled.
  Future<bool> ensureForegroundPermission() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return false;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    return permission == LocationPermission.always ||
        permission == LocationPermission.whileInUse;
  }

  /// Asks for "always" (background) location. Best-effort; recording still works
  /// in the foreground / under the foreground service without it, but granting
  /// it improves reliability when the screen is off.
  Future<void> requestBackgroundPermission() async {
    final permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.whileInUse) {
      await Geolocator.requestPermission();
    }
  }

  /// A stream of position updates suitable for tracking.
  Stream<Position> positionStream() {
    const settings = LocationSettings(
      accuracy: LocationAccuracy.best,
      distanceFilter: 3,
    );
    return Geolocator.getPositionStream(locationSettings: settings);
  }

  Future<Position> currentPosition() {
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
      ),
    );
  }
}
