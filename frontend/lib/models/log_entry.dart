import 'package:flutter/material.dart';

// ──────────────────────────────────────────────────────────────────
// App-wide colour palette
// ──────────────────────────────────────────────────────────────────
class AppColors {
  static const Color background    = Color(0xFF0D1117);
  static const Color surface       = Color(0xFF161B22);
  static const Color border        = Color(0xFF30363D);
  static const Color accentBlue    = Color(0xFF58A6FF);
  static const Color successGreen  = Color(0xFF3FB950);
  static const Color errorRed      = Color(0xFFF85149);
  static const Color warningYellow = Color(0xFFD29922);
  static const Color textPrimary   = Color(0xFFE6EDF3);
  static const Color textSecondary = Color(0xFF8B949E);
  static const Color cyan          = Color(0xFF79C0FF);
  static const Color chipBg        = Color(0xFF21262D);
}

// ──────────────────────────────────────────────────────────────────
// Log entry type
// ──────────────────────────────────────────────────────────────────
enum LogType { cmd, sys, success, error, ai }

class LogEntry {
  final String timestamp;
  final LogType type;
  final String message;

  LogEntry({
    required this.timestamp,
    required this.type,
    required this.message,
  });

  factory LogEntry.now({required LogType type, required String message}) {
    final now = DateTime.now();
    final ts =
        '${now.hour.toString().padLeft(2, '0')}:'
        '${now.minute.toString().padLeft(2, '0')}:'
        '${now.second.toString().padLeft(2, '0')}';
    return LogEntry(timestamp: ts, type: type, message: message);
  }

  String get tagLabel {
    switch (type) {
      case LogType.cmd:     return 'CMD';
      case LogType.sys:     return 'SYS';
      case LogType.success: return 'SUCCESS';
      case LogType.error:   return 'ERROR';
      case LogType.ai:      return 'AI';
    }
  }

  Color get tagColor {
    switch (type) {
      case LogType.cmd:     return AppColors.cyan;
      case LogType.sys:     return AppColors.warningYellow;
      case LogType.success: return AppColors.successGreen;
      case LogType.error:   return AppColors.errorRed;
      case LogType.ai:      return AppColors.accentBlue;
    }
  }
}
