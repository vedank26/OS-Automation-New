import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../models/log_entry.dart';
import '../services/api_service.dart';
import '../widgets/terminal_log.dart';
import '../widgets/command_input.dart';
import '../widgets/quick_commands.dart';
import 'assignment_solver_screen.dart';
import 'project_creation_screen.dart';

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

  // View state: 0 = Dashboard, 1 = Terminal
  int _currentView = 0;

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
    if (normalized.isEmpty) return;

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

  Future<void> _startListening() async {
    if (_isListening || _isProcessing || !_isConnected) return;

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
    if (session != _listenSession) return;
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
        error.toLowerCase().contains('timed out') ? LogType.sys : LogType.error,
        error.toLowerCase().contains('timed out') ? 'Listening timed out' : error,
      );
      _focusNode.requestFocus();
      return;
    }

    if (heard.isEmpty) {
      _addLog(LogType.sys, 'Nothing heard. Tap mic again to listen.');
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

    if (cmd.isEmpty || _isProcessing || !_isConnected) return;

    // Switch view to terminal immediately so logs display in real-time
    setState(() {
      _currentView = 1;
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

    _addLog(isError ? LogType.error : LogType.success, result);

    if (options.isNotEmpty) {
      for (int i = 0; i < options.length; i++) {
        _addLog(LogType.sys, '  ${i + 1}. ${options[i]}');
      }
      _addLog(LogType.sys, "👉 Say 'play 1', 'play 2'... to play");
    }

    setState(() {
      _isProcessing = false;
    });

    _focusNode.requestFocus();
  }

  void _stopListening() {
    if (!_isListening) return;

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
    _isListening ? _stopListening() : await _startListening();
  }

  void _openAssignmentSolver() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const AssignmentSolverScreen()),
    );
  }

  void _openProjectCreation() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ProjectCreationScreen(
          onGenerate: (prompt) {
            _sendCommand(prompt);
          },
        ),
      ),
    );
  }

  Future<void> _showQuickInputDialog(
      String title, String hint, String buttonLabel, void Function(String) onSubmit) async {
    final ctrl = TextEditingController();
    await showDialog(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.7),
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
                title,
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
                  fontSize: 13.5,
                  color: AppColors.textPrimary,
                ),
                cursorColor: AppColors.accentBlue,
                decoration: InputDecoration(
                  hintText: hint,
                  hintStyle: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: AppColors.textSecondary.withValues(alpha: 0.5),
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
                onSubmitted: (v) {
                  Navigator.of(ctx).pop();
                  if (v.trim().isNotEmpty) onSubmit(v.trim());
                },
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(ctx).pop(),
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
                    onPressed: () {
                      Navigator.of(ctx).pop();
                      if (ctrl.text.trim().isNotEmpty) {
                        onSubmit(ctrl.text.trim());
                      }
                    },
                    child: Text(buttonLabel),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Row(
          children: [
            // Persistent left sidebar
            _buildSidebar(),
            const VerticalDivider(width: 1, color: AppColors.border, thickness: 1),
            // Right content area
            Expanded(
              child: Column(
                children: [
                  _buildTopBar(),
                  Expanded(
                    child: _currentView == 0
                        ? _buildDashboardView()
                        : _buildTerminalView(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Persistent Left Sidebar ─────────────────────────────────
  Widget _buildSidebar() {
    return Container(
      width: 72,
      color: const Color(0xFF090D13),
      child: Column(
        children: [
          const SizedBox(height: 16),
          // Sidebar items (Home, Terminal active, others decorative)
          _buildSidebarItem(0, Icons.home_rounded, isActive: _currentView == 0),
          _buildSidebarItem(1, Icons.terminal_rounded, isActive: _currentView == 1),
          _buildSidebarItem(2, Icons.code_rounded, isDecorative: true),
          _buildSidebarItem(3, Icons.bug_report_rounded, isDecorative: true),
          _buildSidebarItem(4, Icons.school_rounded, isDecorative: true),
          _buildSidebarItem(5, Icons.language_rounded, isDecorative: true),
          _buildSidebarItem(6, Icons.smart_toy_rounded, isDecorative: true),
          _buildSidebarItem(7, Icons.folder_open_rounded, isDecorative: true),
          _buildSidebarItem(8, Icons.settings_rounded, isDecorative: true),
          const Spacer(),
          // Bottom profile avatar
          Container(
            width: 36,
            height: 36,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: Color(0xFF2563eb),
            ),
            child: const Center(
              child: Text(
                'F',
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 16,
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildSidebarItem(int index, IconData icon,
      {bool isActive = false, bool isDecorative = false}) {
    return GestureDetector(
      onTap: isDecorative
          ? null
          : () {
              setState(() {
                _currentView = index;
              });
            },
      child: Container(
        height: 48,
        margin: const EdgeInsets.symmetric(vertical: 4),
        child: Stack(
          children: [
            if (isActive)
              Positioned(
                left: 0,
                top: 4,
                bottom: 4,
                width: 3,
                child: Container(
                  decoration: const BoxDecoration(
                    color: AppColors.accentBlue,
                    borderRadius: BorderRadius.only(
                      topRight: Radius.circular(3),
                      bottomRight: Radius.circular(3),
                    ),
                  ),
                ),
              ),
            Center(
              child: Icon(
                icon,
                color: isActive
                    ? AppColors.accentBlue
                    : AppColors.textSecondary.withValues(alpha: 0.5),
                size: 22,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Dashboard View ──────────────────────────────────────────
  Widget _buildDashboardView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const SizedBox(height: 16),
          const Text(
            'Welcome to FlowForge AI 👋',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 26,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Your AI-powered automation and development companion',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 13.5,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 32),
          // Centered wide command input field
          Container(
            constraints: const BoxConstraints(maxWidth: 800),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border),
            ),
            child: Row(
              children: [
                GestureDetector(
                  onTap: _toggleMic,
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isListening
                          ? AppColors.errorRed.withValues(alpha: 0.15)
                          : AppColors.textSecondary.withValues(alpha: 0.08),
                    ),
                    child: Icon(
                      _isListening ? Icons.mic : Icons.mic_none,
                      color: _isListening ? AppColors.errorRed : AppColors.textSecondary,
                      size: 20,
                    ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: TextField(
                    controller: _inputCtrl,
                    onSubmitted: (v) {
                      if (v.trim().isNotEmpty) _sendCommand(v.trim());
                    },
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 14,
                      color: AppColors.textPrimary,
                    ),
                    cursorColor: AppColors.accentBlue,
                    decoration: InputDecoration(
                      hintText: _isListening ? 'Listening...' : 'Enter command...',
                      hintStyle: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 13.5,
                        color: AppColors.textSecondary.withValues(alpha: 0.5),
                      ),
                      border: InputBorder.none,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                GestureDetector(
                  onTap: () {
                    if (_inputCtrl.text.trim().isNotEmpty) {
                      _sendCommand(_inputCtrl.text.trim());
                    }
                  },
                  child: Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: AppColors.accentBlue,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.arrow_forward_rounded,
                      color: Colors.white,
                      size: 18,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 48),
          // Quick Actions section
          Align(
            alignment: Alignment.centerLeft,
            child: const Text(
              'Quick Actions',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 16,
                color: AppColors.textPrimary,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(height: 20),
          // 3-column Grid of cards
          LayoutBuilder(
            builder: (ctx, constraints) {
              final double cardWidth = (constraints.maxWidth - 32) / 3;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.layers_rounded,
                    iconBg: const Color(0xFF2563eb).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF2563eb),
                    title: 'Project Creation',
                    subtitle: 'Create new AI projects with detailed requirements',
                    isHighlighted: true,
                    onTap: _openProjectCreation,
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.edit_note_rounded,
                    iconBg: const Color(0xFF3b82f6).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF3b82f6),
                    title: 'Assignment Solver',
                    subtitle: 'Solve assignments with AI assistance',
                    onTap: _openAssignmentSolver,
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.code_rounded,
                    iconBg: const Color(0xFF58a6ff).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF58a6ff),
                    title: 'Open VS Code',
                    subtitle: 'Open Visual Studio Code in current directory',
                    onTap: () => _sendCommand('open vscode'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.play_circle_fill_rounded,
                    iconBg: const Color(0xFFf85149).withValues(alpha: 0.15),
                    iconColor: const Color(0xFFf85149),
                    title: 'Search YouTube',
                    subtitle: 'Search for tutorials and videos',
                    onTap: () {
                      _showQuickInputDialog(
                        'Search YouTube',
                        'Search query...',
                        'Search',
                        (q) => _sendCommand('search youtube for $q'),
                      );
                    },
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.language_rounded,
                    iconBg: const Color(0xFF3fb950).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF3fb950),
                    title: 'Open Chrome',
                    subtitle: 'Open Google Chrome browser',
                    onTap: () => _sendCommand('open chrome'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.create_new_folder_rounded,
                    iconBg: const Color(0xFFd29922).withValues(alpha: 0.15),
                    iconColor: const Color(0xFFd29922),
                    title: 'Create Folder',
                    subtitle: 'Create a new folder in workspace',
                    onTap: () {
                      _showQuickInputDialog(
                        'Create New Folder',
                        'Folder name...',
                        'Create',
                        (f) => _sendCommand('create folder named $f'),
                      );
                    },
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.camera_alt_rounded,
                    iconBg: const Color(0xFF8a63d2).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF8a63d2),
                    title: 'Screenshot',
                    subtitle: 'Take a screenshot of the screen',
                    onTap: () => _sendCommand('take screenshot'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.mouse_rounded,
                    iconBg: const Color(0xFF2ea043).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF2ea043),
                    title: 'Click',
                    subtitle: 'Simulate mouse click',
                    onTap: () => _sendCommand('click'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.keyboard_rounded,
                    iconBg: const Color(0xFF1f6feb).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF1f6feb),
                    title: 'Type',
                    subtitle: 'Type text in active window',
                    onTap: () {
                      _showQuickInputDialog(
                        'Type Text',
                        'Text to type...',
                        'Type',
                        (t) => _sendCommand('type $t'),
                      );
                    },
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.analytics_rounded,
                    iconBg: const Color(0xFF56e3b5).withValues(alpha: 0.15),
                    iconColor: const Color(0xFF56e3b5),
                    title: 'Task Manager',
                    subtitle: 'Open Windows Task Manager',
                    onTap: () => _sendCommand('open task manager'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.arrow_upward_rounded,
                    iconBg: const Color(0xFFdb61a2).withValues(alpha: 0.15),
                    iconColor: const Color(0xFFdb61a2),
                    title: 'Scroll Up',
                    subtitle: 'Scroll up in active window',
                    onTap: () => _sendCommand('scroll up'),
                  ),
                  _quickActionCard(
                    cardWidth,
                    icon: Icons.arrow_downward_rounded,
                    iconBg: const Color(0xFFe0823d).withValues(alpha: 0.15),
                    iconColor: const Color(0xFFe0823d),
                    title: 'Scroll Down',
                    subtitle: 'Scroll down in active window',
                    onTap: () => _sendCommand('scroll down'),
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 48),
          // Recent Activity panel
          _buildRecentActivity(),
        ],
      ),
    );
  }

  Widget _quickActionCard(double width,
      {required IconData icon,
      required Color iconBg,
      required Color iconColor,
      required String title,
      required String subtitle,
      bool isHighlighted = false,
      required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: width,
        height: 84,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isHighlighted ? const Color(0xFF2563eb) : AppColors.border,
            width: isHighlighted ? 1.4 : 1,
          ),
          boxShadow: isHighlighted
              ? [
                  BoxShadow(
                    color: const Color(0xFF2563eb).withValues(alpha: 0.2),
                    blurRadius: 10,
                  )
                ]
              : [],
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: iconBg,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: iconColor, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 13.5,
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppColors.textSecondary.withValues(alpha: 0.8),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentActivity() {
    // Show last 4 lines of terminal logs
    final recentLogs = _logs.length > 4 ? _logs.sublist(_logs.length - 4) : _logs;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Recent Activity',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14.5,
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                GestureDetector(
                  onTap: () {
                    setState(() {
                      _currentView = 1;
                    });
                  },
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'View Terminal',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12.5,
                          color: AppColors.accentBlue,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      SizedBox(width: 4),
                      Icon(Icons.arrow_forward_ios_rounded, size: 10, color: AppColors.accentBlue),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: AppColors.border),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            color: AppColors.background.withValues(alpha: 0.3),
            child: recentLogs.isEmpty
                ? const Text(
                    'No activity yet.',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 12,
                      color: AppColors.textSecondary,
                    ),
                  )
                : Column(
                    children: recentLogs.map((entry) => _buildRecentLogLine(entry)).toList(),
                  ),
          ),
          const Divider(height: 1, color: AppColors.border),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Text(
              'See all activity in terminal above',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: AppColors.textSecondary.withValues(alpha: 0.5),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentLogLine(LogEntry entry) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            entry.timestamp,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 11,
              color: AppColors.textSecondary.withValues(alpha: 0.5),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 0.5),
            decoration: BoxDecoration(
              color: entry.tagColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(3),
              border: Border.all(color: entry.tagColor.withValues(alpha: 0.25), width: 0.8),
            ),
            child: Text(
              '[${entry.tagLabel}]',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 10,
                color: entry.tagColor,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              entry.message,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Terminal View ───────────────────────────────────────────
  Widget _buildTerminalView() {
    return Column(
      children: [
        Expanded(
          child: TerminalLog(
            logs: _logs,
            scrollController: _scrollCtrl,
          ),
        ),
        QuickCommands(
          onCommand: _sendCommand,
          onAssignmentSolver: _openAssignmentSolver,
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
    );
  }

  Widget _buildTopBar() {
    return AnimatedBuilder(
      animation: _glowAnim,
      builder: (_, __) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: const Border(bottom: BorderSide(color: AppColors.border)),
          boxShadow: [
            BoxShadow(
              color: AppColors.accentBlue.withValues(alpha: 0.05 * _glowAnim.value),
              blurRadius: 10,
            ),
          ],
        ),
        child: Row(
          children: [
            _glowingDot(_isConnected ? AppColors.successGreen : AppColors.errorRed),
            const SizedBox(width: 10),
            const Text(
              '⚡ FlowForge AI',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
                color: AppColors.accentBlue,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.0,
              ),
            ),
            const Spacer(),
            _statusPill(
              _isListening ? 'Listening' : 'Voice Ready',
              _isListening ? AppColors.successGreen : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            _statusPill(
              _isConnected ? '🟢 Connected' : '🔴 Disconnected',
              _isConnected ? AppColors.successGreen : AppColors.errorRed,
            ),
            const SizedBox(width: 14),
            Text(
              _clockStr,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: AppColors.textSecondary.withValues(alpha: 0.6),
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
              color: color.withValues(alpha: 0.5 * _glowAnim.value),
              blurRadius: 6,
              spreadRadius: 1,
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusPill(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        color: color.withValues(alpha: 0.1),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 11,
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
