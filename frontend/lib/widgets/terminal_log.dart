import 'package:flutter/material.dart';
import '../models/log_entry.dart';

/// Scrollable terminal log area.
class TerminalLog extends StatelessWidget {
  final List<LogEntry> logs;
  final ScrollController scrollController;

  const TerminalLog({
    super.key,
    required this.logs,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.background,
      child: logs.isEmpty
          ? _buildEmpty()
          : ListView.builder(
              controller: scrollController,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              itemCount: logs.length,
              itemBuilder: (_, i) => _LogLine(entry: logs[i]),
            ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.terminal,
              size: 48, color: AppColors.textSecondary.withOpacity(0.3)),
          const SizedBox(height: 12),
          Text(
            'No logs yet',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 13,
              color: AppColors.textSecondary.withOpacity(0.4),
            ),
          ),
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────
// Single log line widget
// ──────────────────────────────────────────────────────────────
class _LogLine extends StatelessWidget {
  final LogEntry entry;
  const _LogLine({required this.entry});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timestamp
          Text(
            entry.timestamp,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 11.5,
              color: AppColors.textSecondary.withOpacity(0.6),
            ),
          ),
          const SizedBox(width: 8),
          // Tag pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: entry.tagColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(3),
              border: Border.all(
                  color: entry.tagColor.withOpacity(0.35), width: 0.8),
            ),
            child: Text(
              '[${entry.tagLabel}]',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: entry.tagColor,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 10),
          // Message — supports multi-line
          Expanded(
            child: Text(
              entry.message,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12.5,
                color: AppColors.textPrimary,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
