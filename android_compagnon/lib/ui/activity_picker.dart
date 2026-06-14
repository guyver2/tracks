import 'package:flutter/material.dart';

import '../models/activity_type.dart';

/// Shows a bottom sheet to pick the activity to record. Returns null if
/// dismissed.
Future<ActivityType?> showActivityPicker(BuildContext context) {
  return showModalBottomSheet<ActivityType>(
    context: context,
    showDragHandle: true,
    builder: (context) {
      return SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Choose an activity',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
            ),
            for (final activity in ActivityType.values)
              ListTile(
                leading: Icon(activity.icon),
                title: Text(activity.label),
                onTap: () => Navigator.of(context).pop(activity),
              ),
            const SizedBox(height: 8),
          ],
        ),
      );
    },
  );
}
