import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:intl/intl.dart';

import '../data/database.dart';
import '../models/activity_type.dart';
import '../models/track.dart';
import '../models/track_point.dart';
import '../services/location_service.dart';
import '../services/recording_service.dart';

enum RecordingState { idle, recording, paused }

/// Owns the live recording session: GPS subscription, running stats, periodic
/// persistence, and the foreground service lifecycle.
class RecordingController extends ChangeNotifier {
  RecordingController({
    LocationService? locationService,
    RecordingService? recordingService,
    TrackDatabase? database,
  })  : _location = locationService ?? LocationService(),
        _service = recordingService ?? RecordingService(),
        _db = database ?? TrackDatabase.instance;

  final LocationService _location;
  final RecordingService _service;
  final TrackDatabase _db;

  static const double _maxAcceptableAccuracy = 30; // meters
  static const double _minElevationDelta = 1.5; // meters, noise filter
  static const Duration _flushInterval = Duration(seconds: 10);

  RecordingState _state = RecordingState.idle;
  RecordingState get state => _state;
  bool get isActive => _state != RecordingState.idle;

  ActivityType? _activity;
  ActivityType? get activity => _activity;

  int? _trackId;
  DateTime? _startTime;

  final List<TrackPoint> _points = [];
  List<TrackPoint> get points => List.unmodifiable(_points);

  final List<TrackPoint> _pendingFlush = [];

  double _distanceMeters = 0;
  double get distanceMeters => _distanceMeters;

  double _elevationGain = 0;
  double get elevationGain => _elevationGain;

  Duration _elapsed = Duration.zero;
  Duration get elapsed => _elapsed;

  double? _currentSpeed;
  double? get currentSpeed => _currentSpeed;

  TrackPoint? get lastPoint => _points.isEmpty ? null : _points.last;

  Duration _pausedAccum = Duration.zero;
  DateTime? _pauseStarted;

  StreamSubscription<Position>? _sub;
  Timer? _ticker;
  Timer? _flushTimer;

  String get _defaultName {
    final label = _activity?.label ?? 'Activity';
    final when = DateFormat('MMM d, HH:mm').format(_startTime ?? DateTime.now());
    return '$label - $when';
  }

  /// Requests the permissions required before recording. Returns true when
  /// foreground location is available (background + notifications are
  /// best-effort upgrades).
  Future<bool> prepare() async {
    final ok = await _location.ensureForegroundPermission();
    if (!ok) return false;
    _service.init();
    await _service.requestPermissions();
    await _location.requestBackgroundPermission();
    return true;
  }

  /// Begins a new recording for [activity]. Permissions must already be granted.
  Future<void> start(ActivityType activity) async {
    if (isActive) return;

    _activity = activity;
    _startTime = DateTime.now();
    _points.clear();
    _pendingFlush.clear();
    _distanceMeters = 0;
    _elevationGain = 0;
    _elapsed = Duration.zero;
    _pausedAccum = Duration.zero;
    _pauseStarted = null;
    _currentSpeed = null;

    final track = Track(
      name: _defaultName,
      activity: activity,
      startTime: _startTime!,
    );
    _trackId = await _db.createTrack(track);

    _state = RecordingState.recording;
    notifyListeners();

    await _service.start(
      title: 'Recording ${activity.label}',
      text: 'Tracking your activity...',
    );

    _sub = _location.positionStream().listen(_onPosition);
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
    _flushTimer = Timer.periodic(_flushInterval, (_) => _flush());
  }

  void pause() {
    if (_state != RecordingState.recording) return;
    _state = RecordingState.paused;
    _pauseStarted = DateTime.now();
    _currentSpeed = null;
    _service.updateNotification(
      title: 'Paused - ${_activity?.label ?? ''}',
      text: _statsLine,
    );
    notifyListeners();
  }

  void resume() {
    if (_state != RecordingState.paused) return;
    if (_pauseStarted != null) {
      _pausedAccum += DateTime.now().difference(_pauseStarted!);
      _pauseStarted = null;
    }
    _state = RecordingState.recording;
    _service.updateNotification(
      title: 'Recording ${_activity?.label ?? ''}',
      text: _statsLine,
    );
    notifyListeners();
  }

  /// Finalizes the recording, persists remaining data and stops the service.
  /// Returns the saved track id, or null if there was nothing to save.
  Future<int?> finish({String? name, bool discardIfEmpty = true}) async {
    if (!isActive) return null;

    await _sub?.cancel();
    _sub = null;
    _ticker?.cancel();
    _ticker = null;
    _flushTimer?.cancel();
    _flushTimer = null;

    final trackId = _trackId;
    await _flush();

    if (trackId != null) {
      if (discardIfEmpty && _points.length < 2) {
        await _db.deleteTrack(trackId);
        await _service.stop();
        _reset();
        return null;
      }

      final endTime = DateTime.now();
      final finalTrack = Track(
        id: trackId,
        name: (name == null || name.trim().isEmpty) ? _defaultName : name.trim(),
        activity: _activity!,
        startTime: _startTime!,
        endTime: endTime,
        distanceMeters: _distanceMeters,
        durationSeconds: _elapsed.inSeconds,
        elevationGainMeters: _elevationGain,
      );
      await _db.updateTrack(finalTrack);
    }

    await _service.stop();
    _reset();
    return trackId;
  }

  void _onPosition(Position position) {
    if (_state != RecordingState.recording) return;
    if (position.accuracy > _maxAcceptableAccuracy) return;

    final point = TrackPoint(
      trackId: _trackId,
      latitude: position.latitude,
      longitude: position.longitude,
      elevation: position.altitude,
      timestamp: DateTime.now(),
      accuracy: position.accuracy,
      speed: position.speed >= 0 ? position.speed : null,
    );

    final previous = _points.isEmpty ? null : _points.last;
    if (previous != null) {
      final segment = Geolocator.distanceBetween(
        previous.latitude,
        previous.longitude,
        point.latitude,
        point.longitude,
      );
      _distanceMeters += segment;

      final prevEle = previous.elevation;
      final newEle = point.elevation;
      if (prevEle != null && newEle != null) {
        final delta = newEle - prevEle;
        if (delta > _minElevationDelta) {
          _elevationGain += delta;
        }
      }
    }

    _currentSpeed = point.speed;
    _points.add(point);
    _pendingFlush.add(point);
    notifyListeners();
  }

  void _tick() {
    if (_state != RecordingState.recording || _startTime == null) return;
    final now = DateTime.now();
    _elapsed = now.difference(_startTime!) - _pausedAccum;
    if (_elapsed.isNegative) _elapsed = Duration.zero;
    notifyListeners();
  }

  Future<void> _flush() async {
    final trackId = _trackId;
    if (trackId == null || _pendingFlush.isEmpty) return;
    final toSave = List<TrackPoint>.from(_pendingFlush);
    _pendingFlush.clear();
    await _db.insertPoints(trackId, toSave);
    await _db.updateTrack(
      Track(
        id: trackId,
        name: _defaultName,
        activity: _activity!,
        startTime: _startTime!,
        distanceMeters: _distanceMeters,
        durationSeconds: _elapsed.inSeconds,
        elevationGainMeters: _elevationGain,
      ),
    );
  }

  String get _statsLine {
    final km = (_distanceMeters / 1000).toStringAsFixed(2);
    return '$km km';
  }

  void _reset() {
    _state = RecordingState.idle;
    _activity = null;
    _trackId = null;
    _startTime = null;
    _points.clear();
    _pendingFlush.clear();
    _distanceMeters = 0;
    _elevationGain = 0;
    _elapsed = Duration.zero;
    _pausedAccum = Duration.zero;
    _pauseStarted = null;
    _currentSpeed = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _ticker?.cancel();
    _flushTimer?.cancel();
    super.dispose();
  }
}
