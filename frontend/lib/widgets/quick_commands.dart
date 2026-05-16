import 'package:flutter/material.dart';
import '../models/log_entry.dart';

/// A horizontally scrollable row of quick-command chips.
/// Chips that need user input show a dialog; others fire immediately.
class QuickCommands extends StatelessWidget {
  /// Called when a chip fires with a ready-to-send command string.
  final void Function(String command) onCommand;

  const QuickCommands({super.key, required this.onCommand});

  // ── chip definitions ────────────────────────────────────────────
  static const List<_ChipDef> _chips = [
    _ChipDef('⚡', 'Session',       'start coding session', false),
    _ChipDef('🖥️', 'VS Code',       'open vscode',          false),
    _ChipDef('🌐', 'Chrome',        'open chrome',          false),
    _ChipDef('🎬', 'YouTube',       'open youtube',         false),
    _ChipDef('📁', 'New Folder',    '',                     true,  _DialogKind.folder),
    _ChipDef('📸', 'Screenshot',    'take screenshot',      false),
    _ChipDef('🔍', 'Search',        '',                     true,  _DialogKind.search),
    _ChipDef('🖱️', 'Click',         'click',                false),
    _ChipDef('⌨️', 'Type',          '',                     true,  _DialogKind.type),
    _ChipDef('🗂️', 'Explorer',      'open explorer',        false),
    _ChipDef('📝', 'Notepad',       'open notepad',         false),
    _ChipDef('🔄', 'Switch Window', 'switch window',        false),
    _ChipDef('🖥', 'Task Mgr',      'open task manager',    false),
    _ChipDef('⬇️', 'Scroll Down',   'scroll down',          false),
    _ChipDef('⬆️', 'Scroll Up',     'scroll up',            false),
    _ChipDef('🖥', 'Show Desktop',  'show desktop',         false),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 48,
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: const Border(
          top: BorderSide(color: AppColors.border),
          bottom: BorderSide(color: AppColors.border),
        ),
      ),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        itemCount: _chips.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (ctx, i) => _QuickChip(
          def: _chips[i],
          onTap: () => _handleTap(ctx, _chips[i]),
        ),
      ),
    );
  }

  Future<void> _handleTap(BuildContext context, _ChipDef chip) async {
    if (!chip.needsInput) {
      onCommand(chip.command);
      return;
    }
    // Show appropriate dialog
    final result = await _showInputDialog(context, chip.dialogKind!);
    if (result != null && result.trim().isNotEmpty) {
      switch (chip.dialogKind!) {
        case _DialogKind.folder:
          onCommand('create folder named ${result.trim()}');
          break;
        case _DialogKind.search:
          onCommand('search ${result.trim()}');
          break;
        case _DialogKind.type:
          onCommand('type ${result.trim()}');
          break;
      }
    }
  }

  Future<String?> _showInputDialog(
      BuildContext context, _DialogKind kind) async {
    final ctrl = TextEditingController();
    final titles = {
      _DialogKind.folder: 'Create New Folder',
      _DialogKind.search: 'Search Google',
      _DialogKind.type:   'Type Text',
    };
    final hints = {
      _DialogKind.folder: 'Folder name...',
      _DialogKind.search: 'Search query...',
      _DialogKind.type:   'Text to type...',
    };
    final buttonLabels = {
      _DialogKind.folder: 'Create',
      _DialogKind.search: 'Search',
      _DialogKind.type:   'Type',
    };

    return showDialog<String>(
      context: context,
      barrierColor: Colors.black.withOpacity(0.7),
      builder: (ctx) => Dialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: AppColors.border),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                titles[kind]!,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 15,
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: ctrl,
                autofocus: true,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  color: AppColors.textPrimary,
                ),
                cursorColor: AppColors.accentBlue,
                decoration: InputDecoration(
                  hintText: hints[kind],
                  hintStyle: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: AppColors.textSecondary.withOpacity(0.5),
                  ),
                  enabledBorder: const OutlineInputBorder(
                    borderSide: BorderSide(color: AppColors.border),
                    borderRadius: BorderRadius.all(Radius.circular(6)),
                  ),
                  focusedBorder: const OutlineInputBorder(
                    borderSide: BorderSide(color: AppColors.accentBlue),
                    borderRadius: BorderRadius.all(Radius.circular(6)),
                  ),
                  filled: true,
                  fillColor: AppColors.background,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
                onSubmitted: (v) => Navigator.of(ctx).pop(v),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(ctx).pop(null),
                    child: const Text(
                      'Cancel',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentBlue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                      textStyle: const TextStyle(fontFamily: 'monospace'),
                    ),
                    onPressed: () => Navigator.of(ctx).pop(ctrl.text),
                    child: Text(buttonLabels[kind]!),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────
// Internal data structures
// ──────────────────────────────────────────────────────────────
enum _DialogKind { folder, search, type }

class _ChipDef {
  final String emoji;
  final String label;
  final String command;
  final bool needsInput;
  final _DialogKind? dialogKind;

  const _ChipDef(
    this.emoji,
    this.label,
    this.command,
    this.needsInput, [
    this.dialogKind,
  ]);
}

// ──────────────────────────────────────────────────────────────
// Single chip widget
// ──────────────────────────────────────────────────────────────
class _QuickChip extends StatefulWidget {
  final _ChipDef def;
  final VoidCallback onTap;
  const _QuickChip({required this.def, required this.onTap});

  @override
  State<_QuickChip> createState() => _QuickChipState();
}

class _QuickChipState extends State<_QuickChip> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onTap();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
        decoration: BoxDecoration(
          color: _pressed
              ? AppColors.accentBlue.withOpacity(0.15)
              : AppColors.chipBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: _pressed ? AppColors.accentBlue : AppColors.border,
            width: _pressed ? 1.2 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.def.emoji, style: const TextStyle(fontSize: 13)),
            const SizedBox(width: 5),
            Text(
              widget.def.label,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 11.5,
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
