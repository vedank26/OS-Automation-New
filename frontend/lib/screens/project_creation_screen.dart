import 'dart:async';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../models/log_entry.dart';
import '../services/api_service.dart';

class ProjectCreationScreen extends StatefulWidget {
  final void Function(String command) onGenerate;

  const ProjectCreationScreen({
    super.key,
    required this.onGenerate,
  });

  @override
  State<ProjectCreationScreen> createState() => _ProjectCreationScreenState();
}

class _ProjectCreationScreenState extends State<ProjectCreationScreen>
    with TickerProviderStateMixin {
  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _descCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();

  String _selectedFramework = 'Auto Detect';
  bool _isListening = false;
  bool _isGenerating = false;

  http.Client? _listenClient;
  int _listenSession = 0;

  late final AnimationController _btnPulse;
  late final Animation<double> _btnScale;

  static const _frameworks = [
    'Auto Detect',
    'React',
    'Next.js',
    'Flutter',
    'Python',
    'Node.js',
    'ASP.NET',
    'HTML CSS JS',
    'Electron',
  ];

  static const _exampleChips = [
    ('🛒', 'Ecommerce Website'),
    ('💼', 'Portfolio Website'),
    ('🏥', 'Hospital Management'),
    ('🎓', 'School ERP'),
    ('🍽️', 'Restaurant Website'),
    ('📱', 'Social Media App'),
    ('📊', 'SaaS Dashboard'),
    ('🛠️', 'Admin Dashboard'),
  ];

  @override
  void initState() {
    super.initState();
    _btnPulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 150),
    );
    _btnScale = Tween<double>(begin: 1.0, end: 0.96).animate(
      CurvedAnimation(parent: _btnPulse, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _scrollCtrl.dispose();
    _listenClient?.close();
    _btnPulse.dispose();
    super.dispose();
  }

  Future<void> _startVoice() async {
    if (_isListening || _isGenerating) return;

    final session = ++_listenSession;
    final client = http.Client();
    _listenClient?.close();
    _listenClient = client;
    setState(() => _isListening = true);

    final response = await ApiService.listen(client: client);

    if (!mounted) {
      client.close();
      return;
    }
    if (session != _listenSession) return;
    client.close();

    final heard = response['text']?.toString().trim() ?? '';
    setState(() {
      _isListening = false;
      _listenClient = null;
    });

    if (heard.isNotEmpty) {
      _descCtrl.text = _descCtrl.text.isEmpty
          ? heard
          : '${_descCtrl.text}\n$heard';
      _descCtrl.selection = TextSelection.fromPosition(
        TextPosition(offset: _descCtrl.text.length),
      );
    }
  }

  void _stopVoice() {
    if (!_isListening) return;
    _listenSession++;
    ApiService.stopListening();
    _listenClient?.close();
    _listenClient = null;
    setState(() => _isListening = false);
  }

  void _toggleMic() {
    _isListening ? _stopVoice() : _startVoice();
  }

  void _appendChip(String label) {
    final current = _descCtrl.text.trim();
    _descCtrl.text = current.isEmpty ? label : '$current\n$label';
    _descCtrl.selection = TextSelection.fromPosition(
      TextPosition(offset: _descCtrl.text.length),
    );
  }

  Future<void> _generate() async {
    final name = _nameCtrl.text.trim();
    final desc = _descCtrl.text.trim();

    if (desc.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text(
            'Please describe your project first.',
            style: TextStyle(fontFamily: 'monospace', fontSize: 13),
          ),
          backgroundColor: AppColors.surface,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: AppColors.border),
          ),
        ),
      );
      return;
    }

    await _btnPulse.forward();
    await _btnPulse.reverse();

    final parts = <String>[];
    if (name.isNotEmpty) parts.add('Project Name: $name');
    if (_selectedFramework != 'Auto Detect') {
      parts.add('Framework: $_selectedFramework');
    }
    parts.add('Description: $desc');

    final prompt = 'create ai project ${parts.join('. ')}';

    setState(() => _isGenerating = true);

    if (mounted) Navigator.of(context).pop();
    widget.onGenerate(prompt);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildTopBar(context),
            Expanded(
              child: Scrollbar(
                controller: _scrollCtrl,
                child: SingleChildScrollView(
                  controller: _scrollCtrl,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildSubtitle(),
                      const SizedBox(height: 24),
                      // Enclosing the entire form inside one single padded Card/Container
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: AppColors.surface,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Project Name and Framework side by side in a Row
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      _label('Project Name'),
                                      const SizedBox(height: 8),
                                      _textField(
                                        controller: _nameCtrl,
                                        hint: 'Enter your project name...',
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      _label('Framework / Technology'),
                                      const SizedBox(height: 8),
                                      _dropdown(),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 24),
                            // Describe label & Speak instead button
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      _label('Describe your project in detail'),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Mention pages, features, theme, colors, animations, APIs, database, authentication, dashboard, libraries, or anything else...',
                                        style: TextStyle(
                                          fontFamily: 'monospace',
                                          fontSize: 11,
                                          color: AppColors.textSecondary.withValues(alpha: 0.8),
                                          height: 1.4,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                _buildMicButton(),
                              ],
                            ),
                            const SizedBox(height: 16),
                            // Description text field
                            Container(
                              height: 380, // Fixed height to prevent overflow and enforce min size
                              decoration: BoxDecoration(
                                color: AppColors.background,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: AppColors.border),
                              ),
                              child: TextField(
                                controller: _descCtrl,
                                maxLines: null,
                                expands: true,
                                textAlignVertical: TextAlignVertical.top,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 13.5,
                                  color: AppColors.textPrimary,
                                  height: 1.5,
                                ),
                                cursorColor: AppColors.accentBlue,
                                decoration: InputDecoration(
                                  hintText: 'Write your project description here...\nThe more details you provide, the better the result.',
                                  hintStyle: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 12.5,
                                    color: AppColors.textSecondary.withValues(alpha: 0.4),
                                    height: 1.5,
                                  ),
                                  border: InputBorder.none,
                                  contentPadding: const EdgeInsets.all(16),
                                ),
                              ),
                            ),
                            const SizedBox(height: 8),
                            // Character counter
                            Align(
                              alignment: Alignment.centerRight,
                              child: ValueListenableBuilder(
                                valueListenable: _descCtrl,
                                builder: (_, __, ___) => Text(
                                  '${_descCtrl.text.length} / 10000 characters',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 11,
                                    color: AppColors.textSecondary.withValues(alpha: 0.6),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(height: 24),
                            // Example chips section
                            const Text(
                              'Need inspiration? Try these examples',
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 12,
                                color: AppColors.textSecondary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: _exampleChips
                                  .map((c) => _ExampleChip(
                                        emoji: c.$1,
                                        label: c.$2,
                                        onTap: () => _appendChip(c.$2),
                                      ))
                                  .toList(),
                            ),
                            const SizedBox(height: 32),
                            // Generate button
                            _buildGenerateButton(),
                            const SizedBox(height: 16),
                            // Security / Privacy note
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.lock_outline_rounded,
                                  size: 13,
                                  color: AppColors.textSecondary.withValues(alpha: 0.5),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Your project details are private and secure',
                                  style: TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 11,
                                    color: AppColors.textSecondary.withValues(alpha: 0.5),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: const Icon(
              Icons.arrow_back_rounded,
              color: AppColors.accentBlue,
              size: 22,
            ),
          ),
          const SizedBox(width: 16),
          const Text(
            'Project Creation',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 18,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSubtitle() {
    return const Text(
      'Describe your project in detail and let AI build it for you',
      style: TextStyle(
        fontFamily: 'monospace',
        fontSize: 13,
        color: AppColors.textSecondary,
        height: 1.5,
      ),
    );
  }

  Widget _label(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontFamily: 'monospace',
        fontSize: 13,
        color: AppColors.textPrimary,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  Widget _textField({
    required TextEditingController controller,
    required String hint,
  }) {
    return TextField(
      controller: controller,
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
          fontSize: 12.5,
          color: AppColors.textSecondary.withValues(alpha: 0.4),
        ),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: AppColors.border),
          borderRadius: BorderRadius.all(Radius.circular(6)),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: AppColors.accentBlue, width: 1.2),
          borderRadius: BorderRadius.all(Radius.circular(6)),
        ),
        filled: true,
        fillColor: AppColors.background,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      ),
    );
  }

  Widget _dropdown() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.border),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedFramework,
          dropdownColor: AppColors.surface,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 13.5,
            color: AppColors.textPrimary,
          ),
          icon: const Icon(
            Icons.keyboard_arrow_down_rounded,
            color: AppColors.textSecondary,
            size: 22,
          ),
          isExpanded: true,
          items: _frameworks
              .map((f) => DropdownMenuItem(value: f, child: Text(f)))
              .toList(),
          onChanged: (v) {
            if (v != null) setState(() => _selectedFramework = v);
          },
        ),
      ),
    );
  }

  Widget _buildMicButton() {
    return GestureDetector(
      onTap: _toggleMic,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: _isListening ? const Color(0xFF22c55e).withValues(alpha: 0.1) : AppColors.accentBlue.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: _isListening ? const Color(0xFF22c55e) : AppColors.accentBlue,
            width: 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              _isListening ? Icons.stop_rounded : Icons.mic_rounded,
              size: 15,
              color: _isListening ? const Color(0xFF22c55e) : AppColors.accentBlue,
            ),
            const SizedBox(width: 6),
            Text(
              _isListening ? 'Stop' : 'Speak instead',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: _isListening ? const Color(0xFF22c55e) : AppColors.accentBlue,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGenerateButton() {
    return ScaleTransition(
      scale: _btnScale,
      child: GestureDetector(
        onTap: _isGenerating ? null : _generate,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF2563eb), Color(0xFF3b82f6)],
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
            ),
            borderRadius: BorderRadius.circular(8),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF2563eb).withValues(alpha: 0.35),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (_isGenerating) ...[
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    color: Colors.white,
                    strokeWidth: 2,
                  ),
                ),
                const SizedBox(width: 12),
                const Text(
                  'Generating...',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 15,
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ] else ...[
                const Text('⚡', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 8),
                const Text(
                  'Generate Project',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 15,
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ExampleChip extends StatefulWidget {
  final String emoji;
  final String label;
  final VoidCallback onTap;

  const _ExampleChip({
    required this.emoji,
    required this.label,
    required this.onTap,
  });

  @override
  State<_ExampleChip> createState() => _ExampleChipState();
}

class _ExampleChipState extends State<_ExampleChip> {
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
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: _pressed
              ? AppColors.accentBlue.withValues(alpha: 0.1)
              : AppColors.chipBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: _pressed
                ? AppColors.accentBlue
                : AppColors.border,
            width: 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.emoji, style: const TextStyle(fontSize: 13)),
            const SizedBox(width: 6),
            Text(
              widget.label,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: _pressed
                    ? AppColors.accentBlue
                    : AppColors.textSecondary,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
