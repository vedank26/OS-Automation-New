import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../models/log_entry.dart';
import '../services/api_service.dart';
import '../widgets/terminal_log.dart';
import '../widgets/command_input.dart';
import '../widgets/quick_commands.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with TickerProviderStateMixin {
  final TextEditingController _inputCtrl = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  final ScrollController _scrollCtrl = ScrollController();
  final List<LogEntry> _logs = [];

  bool _isProcessing = false;
  bool _isConnected = false;
  bool _isListening = false;
  int _listenSession = 0;
  http.Client? _listenClient;

  Timer? _retryTimer;
  Timer? _clockTimer;
  String _clockStr = '';

  late final AnimationController _glowCtrl;
  late final Animation<double> _glowAnim;

  @override
  void initState() {
    super.initState();

    _glowCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _glowAnim = Tween<double>(
      begin: 0.4,
      end: 1.0,
    ).animate(_glowCtrl);

    _updateClock();

    _clockTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => _updateClock(),
    );

    _checkConnection(isStartup: true);

    _retryTimer = Timer.periodic(
      const Duration(seconds: 5),
      (_) => _retryIfNeeded(),
    );
  }

  @override
  void dispose() {
    _glowCtrl.dispose();
    _inputCtrl.dispose();
    _focusNode.dispose();
    _scrollCtrl.dispose();
    _retryTimer?.cancel();
    _clockTimer?.cancel();
    _listenClient?.close();
    super.dispose();
  }

  void _updateClock() {
    final now = DateTime.now();

    setState(() {
      _clockStr =
          '${now.hour.toString().padLeft(2, '0')}:'
          '${now.minute.toString().padLeft(2, '0')}:'
          '${now.second.toString().padLeft(2, '0')}';
    });
  }

  void _addLog(LogType type, String message) {
    setState(() {
      _logs.add(
        LogEntry.now(
          type: type,
          message: message,
        ),
      );
    });

    Future.delayed(
      const Duration(milliseconds: 60),
      _scrollToBottom,
    );
  }

  void _addWorkflowLog(String message) {
    final normalized = message.trim();
    if (normalized.isEmpty) {
      return;
    }

    final lower = normalized.toLowerCase();
    if (lower.startsWith('[ai]')) {
      _addLog(LogType.ai, normalized);
    } else if (lower.startsWith('[success]')) {
      _addLog(LogType.success, normalized);
    } else if (lower.startsWith('[error]')) {
      _addLog(LogType.error, normalized);
    } else {
      _addLog(LogType.sys, normalized);
    }
  }

  void _scrollToBottom() {
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    }
  }

  Future<void> _checkConnection({bool isStartup = false}) async {
    final ok = await ApiService.checkConnection();
    final wasConnected = _isConnected;

    setState(() {
      _isConnected = ok;
    });

    if (isStartup) {
      _addLog(LogType.sys, '⚡ FlowForge AI initialized');

      if (ok) {
        _addLog(
          LogType.success,
          '🔗 Backend connected at 127.0.0.1:8000',
        );

        _addLog(
          LogType.sys,
          'Tap mic to dictate a command',
        );
      } else {
        _addLog(
          LogType.error,
          '🔴 Backend not reachable — retrying...',
        );
      }
    } else if (ok && !wasConnected) {
      _addLog(
        LogType.success,
        '✅ Backend reconnected',
      );
    }
  }

  void _retryIfNeeded() {
    if (!_isConnected) {
      _checkConnection();
    }
  }

  // Starts one backend transcription after mic click.
  Future<void> _startListening() async {
    if (_isListening || _isProcessing || !_isConnected) {
      return;
    }

    final session = ++_listenSession;
    final client = http.Client();
    _listenClient?.close();
    _listenClient = client;

    setState(() {
      _isListening = true;
      _inputCtrl.clear();
    });

    _addLog(LogType.sys, 'Listening...');

    final response = await ApiService.listen(client: client);

    if (!mounted) {
      client.close();
      return;
    }

    if (session != _listenSession) {
      return;
    }

    client.close();

    final heard = response["text"]?.toString().trim() ?? "";
    final error = response["error"]?.toString().trim() ?? "";

    setState(() {
      _isListening = false;
      _listenClient = null;
      if (heard.isNotEmpty) {
        _inputCtrl.text = heard;
        _inputCtrl.selection = TextSelection.fromPosition(
          TextPosition(offset: _inputCtrl.text.length),
        );
      }
    });

    if (error.isNotEmpty) {
      _addLog(
        error.toLowerCase().contains('timed out')
            ? LogType.sys
            : LogType.error,
        error.toLowerCase().contains('timed out')
            ? 'Listening timed out'
            : error,
      );
      _focusNode.requestFocus();
      return;
    }

    if (heard.isEmpty) {
      _addLog(
        LogType.sys,
        'Nothing heard. Tap mic again to listen.',
      );
      _focusNode.requestFocus();
      return;
    }

    _addLog(LogType.sys, 'Processing speech...');
    _addLog(LogType.sys, 'Heard: "$heard"');
    await _sendCommand(heard, keepText: true, useSmartExecute: true);
  }

  Future<void> _sendCommand(
    String cmd, {
    bool keepText = false,
    bool useSmartExecute = false,
  }) async {
    cmd = cmd.trim();

    if (cmd.isEmpty || _isProcessing || !_isConnected) {
      return;
    }

    setState(() {
      _isProcessing = true;
      if (keepText) {
        _inputCtrl.text = cmd;
        _inputCtrl.selection = TextSelection.fromPosition(
          TextPosition(offset: _inputCtrl.text.length),
        );
      } else {
        _inputCtrl.clear();
      }
    });

    _addLog(LogType.cmd, '\$ $cmd');
    _addLog(LogType.sys, 'Executing command...');

    final response = useSmartExecute
        ? await ApiService.smartExecute(cmd)
        : await ApiService.sendCommand(cmd);

    String result = response["result"] ?? "No response";
    List options = response["options"] ?? [];
    List workflowLogs = response["logs"] ?? [];

    for (final logLine in workflowLogs) {
      _addWorkflowLog(logLine.toString());
    }

    final isError =
        result.toLowerCase().contains('not recognized') ||
            result.toLowerCase().contains('error') ||
            result.toLowerCase().startsWith('error:');

    _addLog(
      isError ? LogType.error : LogType.success,
      result,
    );

    if (options.isNotEmpty) {
      for (int i = 0; i < options.length; i++) {
        _addLog(
          LogType.sys,
          '  ${i + 1}. ${options[i]}',
        );
      }

      _addLog(
        LogType.sys,
        "👉 Say 'play 1', 'play 2'... to play",
      );
    }

    setState(() {
      _isProcessing = false;
    });

    _focusNode.requestFocus();
  }

  void _stopListening() {
    if (!_isListening) {
      return;
    }

    _listenSession++;
    ApiService.stopListening();
    _listenClient?.close();
    _listenClient = null;

    setState(() {
      _isListening = false;
    });

    _addLog(LogType.sys, 'Listening stopped');
    _focusNode.requestFocus();
  }

  Future<void> _toggleMic() async {
    if (_isListening) {
      _stopListening();
      return;
    }

    await _startListening();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildTopBar(),

            Expanded(
              child: TerminalLog(
                logs: _logs,
                scrollController: _scrollCtrl,
              ),
            ),

            QuickCommands(
              onCommand: _sendCommand,
            ),

            CommandInput(
              controller: _inputCtrl,
              focusNode: _focusNode,
              isProcessing: _isProcessing,
              isConnected: _isConnected,
              isListening: _isListening,
              onSend: () => _sendCommand(_inputCtrl.text),
              onMicTap: _toggleMic,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return AnimatedBuilder(
      animation: _glowAnim,
      builder: (_, __) => Container(
        padding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 10,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: const Border(
            bottom: BorderSide(
              color: AppColors.border,
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: AppColors.accentBlue.withValues(
                alpha: 0.06 * _glowAnim.value,
              ),
              blurRadius: 12,
            ),
          ],
        ),
        child: Row(
          children: [
            _glowingDot(
              _isConnected
                  ? AppColors.successGreen
                  : AppColors.errorRed,
            ),

            const SizedBox(width: 10),

            const Text(
              '⚡ FlowForge AI',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
                color: AppColors.accentBlue,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.2,
              ),
            ),

            const Spacer(),

            _statusPill(
              _isListening
                  ? 'Listening'
                  : 'Voice Ready',
              _isListening
                  ? AppColors.successGreen
                  : AppColors.textSecondary,
            ),

            const SizedBox(width: 8),

            _statusPill(
              _isConnected
                  ? '🟢 Connected'
                  : '🔴 Disconnected',
              _isConnected
                  ? AppColors.successGreen
                  : AppColors.errorRed,
            ),

            const SizedBox(width: 10),

            Text(
              _clockStr,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: AppColors.textSecondary.withValues(
                  alpha: 0.7,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _glowingDot(Color color) {
    return AnimatedBuilder(
      animation: _glowAnim,
      builder: (_, __) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color,
          boxShadow: [
            BoxShadow(
              color: color.withValues(
                alpha: 0.6 * _glowAnim.value,
              ),
              blurRadius: 8,
              spreadRadius: 1,
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusPill(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 3,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        color: color.withValues(alpha: 0.1),
        border: Border.all(
          color: color.withValues(alpha: 0.35),
        ),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 10.5,
          color: color,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
