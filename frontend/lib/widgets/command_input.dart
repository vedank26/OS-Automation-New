import 'package:flutter/material.dart';
import '../models/log_entry.dart';

/// Bottom command input bar with mic, text field, and send button.
class CommandInput extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final bool isProcessing;
  final bool isConnected;
  final bool isListening;
  final VoidCallback onSend;
  final VoidCallback onMicTap;

  const CommandInput({
    super.key,
    required this.controller,
    required this.focusNode,
    required this.isProcessing,
    required this.isConnected,
    required this.isListening,
    required this.onSend,
    required this.onMicTap,
  });

  @override
  Widget build(BuildContext context) {
    final canSend = isConnected && !isProcessing;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(
            color: isListening
                ? AppColors.errorRed.withValues(alpha: 0.6)
                : AppColors.border,
          ),
        ),
      ),
      child: Row(
        children: [
          // ── Mic button ──────────────────────────────────────────
          _MicButton(isListening: isListening, onTap: onMicTap),
          const SizedBox(width: 10),
          // ── Text input ──────────────────────────────────────────
          Expanded(
            child: TextField(
              controller: controller,
              focusNode: focusNode,
              enabled: canSend,
              onSubmitted: canSend ? (_) => onSend() : null,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
                color: AppColors.textPrimary,
              ),
              cursorColor: AppColors.accentBlue,
              decoration: InputDecoration(
                hintText: isListening
                    ? 'Listening...'
                    : isProcessing
                        ? 'Processing...'
                        : !isConnected
                            ? 'Backend disconnected...'
                            : 'Enter command...',
                hintStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 13,
                  color: isListening
                      ? AppColors.errorRed.withValues(alpha: 0.7)
                      : AppColors.textSecondary.withValues(alpha: 0.5),
                ),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
                prefixText: '❯  ',
                prefixStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 15,
                  color: isConnected
                      ? AppColors.accentBlue
                      : AppColors.errorRed,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          // ── Send button ─────────────────────────────────────────
          _SendButton(
            canSend: canSend,
            isProcessing: isProcessing,
            onTap: onSend,
          ),
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────
// Mic button with pulsing animation when listening
// ──────────────────────────────────────────────────────────────
class _MicButton extends StatefulWidget {
  final bool isListening;
  final VoidCallback onTap;
  const _MicButton({required this.isListening, required this.onTap});

  @override
  State<_MicButton> createState() => _MicButtonState();
}

class _MicButtonState extends State<_MicButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseCtrl;
  late final Animation<double> _pulse;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _pulse = Tween<double>(begin: 1.0, end: 1.25).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );
  }

  @override
  void didUpdateWidget(_MicButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isListening) {
      _pulseCtrl.repeat(reverse: true);
    } else {
      _pulseCtrl.stop();
      _pulseCtrl.reset();
    }
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color =
        widget.isListening ? AppColors.errorRed : AppColors.textSecondary;
    return AnimatedBuilder(
      animation: _pulse,
      builder: (_, child) => Transform.scale(
        scale: widget.isListening ? _pulse.value : 1.0,
        child: child,
      ),
      child: GestureDetector(
        onTap: widget.onTap,
        child: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color.withValues(alpha: 0.1),
            border: Border.all(color: color.withValues(alpha: 0.4)),
            boxShadow: widget.isListening
                ? [
                    BoxShadow(
                      color: AppColors.errorRed.withValues(alpha: 0.35),
                      blurRadius: 12,
                      spreadRadius: 2,
                    )
                  ]
                : [],
          ),
          child: Icon(
            widget.isListening ? Icons.mic : Icons.mic_none,
            color: color,
            size: 20,
          ),
        ),
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────
// Send / loading button
// ──────────────────────────────────────────────────────────────
class _SendButton extends StatelessWidget {
  final bool canSend;
  final bool isProcessing;
  final VoidCallback onTap;

  const _SendButton({
    required this.canSend,
    required this.isProcessing,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: canSend ? onTap : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          color: canSend
              ? AppColors.accentBlue.withValues(alpha: 0.15)
              : AppColors.surface,
          border: Border.all(
            color: canSend
                ? AppColors.accentBlue.withValues(alpha: 0.6)
                : AppColors.border,
          ),
        ),
        child: isProcessing
            ? Padding(
                padding: const EdgeInsets.all(10),
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.accentBlue.withValues(alpha: 0.8),
                ),
              )
            : Icon(
                Icons.send_rounded,
                size: 18,
                color: canSend
                    ? AppColors.accentBlue
                    : AppColors.textSecondary.withValues(alpha: 0.3),
              ),
      ),
    );
  }
}
