import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../models/log_entry.dart';
import '../services/api_service.dart';

/// A full-screen assignment solver page with two modes:
/// 1. Describe your assignment (text input)
/// 2. Upload an assignment file (with optional instructions chat)
class AssignmentSolverScreen extends StatefulWidget {
  const AssignmentSolverScreen({super.key});

  @override
  State<AssignmentSolverScreen> createState() => _AssignmentSolverScreenState();
}

class _AssignmentSolverScreenState extends State<AssignmentSolverScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  final TextEditingController _descCtrl = TextEditingController();
  final TextEditingController _instructionsCtrl = TextEditingController();
  bool _isProcessing = false;
  String? _resultMessage;
  String? _selectedFileName;
  String? _selectedFilePath;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _descCtrl.dispose();
    _instructionsCtrl.dispose();
    super.dispose();
  }

  Future<void> _solveFromDescription() async {
    final desc = _descCtrl.text.trim();
    if (desc.isEmpty) {
      _showSnackBar('Please describe your assignment first');
      return;
    }

    setState(() {
      _isProcessing = true;
      _resultMessage = null;
    });

    try {
      final response = await ApiService.solveAssignmentDescription(desc);
      final resultText = response['result'] ?? 'No response';

      setState(() {
        _isProcessing = false;
      });

      // Open preview screen instead of showing result panel
      _openPreviewScreen(resultText, title: desc.split(' ').take(5).join(' '));
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _isProcessing = false;
      });
    }
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: [
          'txt',
          'pdf',
          'docx',
          'xlsx',
          'csv',
          'py',
          'js',
          'html',
          'css',
          'json',
          'md',
          'java',
          'cpp',
          'c',
          'png',
          'jpg',
          'jpeg',
          'bmp',
          'webp',
        ],
      );

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;
      setState(() {
        _selectedFileName = file.name;
        _selectedFilePath = file.path;
      });
    } catch (e) {
      _showSnackBar('Error picking file: $e');
    }
  }

  Future<void> _solveFromFile() async {
    if (_selectedFilePath == null) {
      _showSnackBar('Please pick a file first');
      return;
    }

    setState(() {
      _isProcessing = true;
      _resultMessage = null;
    });

    try {
      final instructions = _instructionsCtrl.text.trim();
      final response = await ApiService.solveAssignmentFile(
        _selectedFilePath!,
        instructions: instructions.isNotEmpty ? instructions : null,
      );
      final resultText = response['result'] ?? 'No response';

      setState(() {
        _isProcessing = false;
      });

      // Open preview screen
      final title = _selectedFileName != null
          ? _selectedFileName!.replaceAll(RegExp(r'\.\w+$'), '')
          : 'Assignment';
      _openPreviewScreen(resultText, title: title);
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _isProcessing = false;
      });
    }
  }

  void _openPreviewScreen(String solutionText, {String title = 'Assignment'}) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _AssignmentPreviewScreen(
          solutionText: solutionText,
          title: title,
        ),
      ),
    );
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.surface,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        title: const Text(
          'Assignment Solver',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        bottom: TabBar(
          controller: _tabCtrl,
          labelColor: AppColors.accentBlue,
          unselectedLabelColor: AppColors.textSecondary,
          indicatorColor: AppColors.accentBlue,
          labelStyle: const TextStyle(fontFamily: 'monospace', fontSize: 13),
          tabs: const [
            Tab(text: 'Describe', icon: Icon(Icons.edit_note, size: 20)),
            Tab(text: 'Upload File', icon: Icon(Icons.upload_file, size: 20)),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: TabBarView(
              controller: _tabCtrl,
              children: [
                _buildDescriptionTab(),
                _buildFileUploadTab(),
              ],
            ),
          ),
          if (_resultMessage != null) _buildResultPanel(),
        ],
      ),
    );
  }

  // ─── DESCRIBE TAB ────────────────────────────────────────────────

  Widget _buildDescriptionTab() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Describe Your Assignment',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 16,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Tell us what your assignment is about. Be specific — include the subject, '
            'topic, questions, or any details. The AI will create a complete solution document.',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: TextField(
              controller: _descCtrl,
              maxLines: null,
              expands: true,
              textAlignVertical: TextAlignVertical.top,
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 13,
                color: AppColors.textPrimary,
                height: 1.6,
              ),
              cursorColor: AppColors.accentBlue,
              decoration: InputDecoration(
                hintText:
                    'Example: "Write about Newton\'s three laws of motion '
                    'with examples and derivations for my Physics class"',
                hintStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: AppColors.textSecondary.withValues(alpha: 0.5),
                  height: 1.6,
                ),
                filled: true,
                fillColor: AppColors.surface,
                border: const OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(10)),
                  borderSide: BorderSide(color: AppColors.border),
                ),
                enabledBorder: const OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(10)),
                  borderSide: BorderSide(color: AppColors.border),
                ),
                focusedBorder: const OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(10)),
                  borderSide: BorderSide(color: AppColors.accentBlue),
                ),
                contentPadding: const EdgeInsets.all(16),
              ),
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: _isProcessing ? null : _solveFromDescription,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accentBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                textStyle: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
              child: _isProcessing
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Solve Assignment'),
            ),
          ),
        ],
      ),
    );
  }

  // ─── FILE UPLOAD TAB (with instructions chat) ─────────────────────

  Widget _buildFileUploadTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Upload Assignment File',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 16,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Upload your assignment file and optionally describe how you want it done.',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 20),

          // ── File picker area ──
          GestureDetector(
            onTap: _isProcessing ? null : _pickFile,
            child: Container(
              width: double.infinity,
              height: 140,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _selectedFileName != null
                      ? AppColors.successGreen
                      : AppColors.border,
                  width: _selectedFileName != null ? 1.5 : 1,
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    _selectedFileName != null
                        ? Icons.check_circle
                        : Icons.cloud_upload_outlined,
                    size: 40,
                    color: _selectedFileName != null
                        ? AppColors.successGreen
                        : AppColors.textSecondary.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _selectedFileName ?? 'Tap to pick a file',
                    style: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 13,
                      color: _selectedFileName != null
                          ? AppColors.successGreen
                          : AppColors.textSecondary,
                      fontWeight: _selectedFileName != null
                          ? FontWeight.bold
                          : FontWeight.normal,
                    ),
                  ),
                  if (_selectedFileName != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Tap to change file',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        color: AppColors.textSecondary.withValues(alpha: 0.5),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Instructions / Chat input ──
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: const BoxDecoration(
                    border: Border(
                      bottom: BorderSide(color: AppColors.border),
                    ),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.chat_bubble_outline,
                        size: 16,
                        color: AppColors.accentBlue,
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'How should this assignment be done?',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: AppColors.accentBlue,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        'Optional',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 10,
                          color: AppColors.textSecondary.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
                  ),
                ),
                // Text input
                TextField(
                  controller: _instructionsCtrl,
                  maxLines: 4,
                  minLines: 3,
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: AppColors.textPrimary,
                    height: 1.5,
                  ),
                  cursorColor: AppColors.accentBlue,
                  decoration: InputDecoration(
                    hintText: 'e.g. "Focus on derivations and show all steps", '
                        '"Write in simple language", "Include real-world examples", '
                        '"Only solve questions 1, 3, and 5"...',
                    hintStyle: TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppColors.textSecondary.withValues(alpha: 0.4),
                      height: 1.5,
                    ),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.all(14),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Solve button ──
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: (_isProcessing || _selectedFilePath == null)
                  ? null
                  : _solveFromFile,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.accentBlue,
                foregroundColor: Colors.white,
                disabledBackgroundColor:
                    AppColors.accentBlue.withValues(alpha: 0.3),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
                textStyle: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
              child: _isProcessing
                  ? const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(width: 12),
                        Text('Solving...'),
                      ],
                    )
                  : const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.auto_fix_high, size: 18),
                        SizedBox(width: 8),
                        Text('Solve Assignment'),
                      ],
                    ),
            ),
          ),
          const SizedBox(height: 16),

          // ── Supported formats ──
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Supported formats:',
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11,
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    '.txt',
                    '.pdf',
                    '.docx',
                    '.xlsx',
                    '.csv',
                    '.py',
                    '.js',
                    '.html',
                    '.css',
                    '.json',
                    '.md',
                    '.java',
                    '.cpp',
                    '.c',
                    '.png',
                    '.jpg',
                    '.jpeg',
                    '.bmp',
                    '.webp',
                  ]
                      .map((ext) => Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.chipBg,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              ext,
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 10,
                                color: AppColors.accentBlue,
                              ),
                            ),
                          ))
                      .toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── RESULT PANEL (for errors only now) ───────────────────────────

  Widget _buildResultPanel() {
    final isError = !(_resultMessage!.contains('completed') ||
        _resultMessage!.contains('solved') ||
        _resultMessage!.contains('Saved'));

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 200),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(
            color: isError ? AppColors.errorRed : AppColors.successGreen,
            width: 1.5,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isError ? Icons.error : Icons.check_circle,
                size: 18,
                color: isError ? AppColors.errorRed : AppColors.successGreen,
              ),
              const SizedBox(width: 8),
              Text(
                isError ? 'Error' : 'Result',
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 14,
                  color: isError ? AppColors.errorRed : AppColors.successGreen,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _resultMessage = null),
                child: const Icon(
                  Icons.close,
                  size: 18,
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Expanded(
            child: SingleChildScrollView(
              child: Text(
                _resultMessage!,
                style: const TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: AppColors.textPrimary,
                  height: 1.5,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════════
// PREVIEW & EDIT SCREEN
// ════════════════════════════════════════════════════════════════════

class _AssignmentPreviewScreen extends StatefulWidget {
  final String solutionText;
  final String title;

  const _AssignmentPreviewScreen({
    required this.solutionText,
    required this.title,
  });

  @override
  State<_AssignmentPreviewScreen> createState() =>
      _AssignmentPreviewScreenState();
}

class _AssignmentPreviewScreenState extends State<_AssignmentPreviewScreen> {
  late TextEditingController _editCtrl;
  bool _isEditing = false;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _editCtrl = TextEditingController(text: widget.solutionText);
  }

  @override
  void dispose() {
    _editCtrl.dispose();
    super.dispose();
  }

  Future<void> _saveToDesktop() async {
    setState(() => _isSaving = true);

    try {
      final editedText = _editCtrl.text.trim();
      final response = await ApiService.saveAssignmentDocx(
        solutionText: editedText,
        title: widget.title,
      );

      if (!mounted) return;

      final result = response['result'] ?? 'Saved successfully';
      _showSnackBar(result);
      Navigator.of(context).pop(); // Go back after saving
    } catch (e) {
      _showSnackBar('Error saving: $e');
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppColors.surface,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        title: Text(
          _isEditing ? 'Edit Assignment' : 'Preview Assignment',
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        actions: [
          // Edit/View toggle
          TextButton.icon(
            onPressed: () => setState(() => _isEditing = !_isEditing),
            icon: Icon(
              _isEditing ? Icons.visibility : Icons.edit,
              size: 18,
              color: AppColors.accentBlue,
            ),
            label: Text(
              _isEditing ? 'Preview' : 'Edit',
              style: const TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: AppColors.accentBlue,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          // ── Status bar ──
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(
                bottom: BorderSide(color: AppColors.border),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _isEditing ? Icons.edit_document : Icons.remove_red_eye,
                  size: 16,
                  color: AppColors.accentBlue,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _isEditing
                        ? 'Edit the solution below. Changes will be reflected in the saved document.'
                        : 'Review the solved assignment below. Tap "Edit" to make changes before saving.',
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      color: AppColors.textSecondary,
                      height: 1.4,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // ── Content area ──
          Expanded(
            child: _isEditing ? _buildEditMode() : _buildPreviewMode(),
          ),

          // ── Bottom action bar ──
          Container(
            padding: const EdgeInsets.all(16),
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(
                top: BorderSide(color: AppColors.border),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.textSecondary,
                      side: const BorderSide(color: AppColors.border),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: const Text(
                      'Discard',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 13,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: ElevatedButton.icon(
                    onPressed: _isSaving ? null : _saveToDesktop,
                    icon: _isSaving
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.save, size: 18),
                    label: Text(
                      _isSaving ? 'Saving...' : 'Save to Desktop',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.accentBlue,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─── PREVIEW MODE (read-only, formatted display) ─────────────────

  Widget _buildPreviewMode() {
    final lines = _editCtrl.text.split('\n');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: lines.map((line) {
          final trimmed = line.trim();

          // Heading 1
          if (trimmed.startsWith('####')) {
            return _heading(trimmed.replaceFirst(RegExp(r'^####\s*'), ''), 4);
          }
          if (trimmed.startsWith('###')) {
            return _heading(trimmed.replaceFirst(RegExp(r'^###\s*'), ''), 3);
          }
          if (trimmed.startsWith('##')) {
            return _heading(trimmed.replaceFirst(RegExp(r'^##\s*'), ''), 2);
          }
          if (trimmed.startsWith('#')) {
            return _heading(trimmed.replaceFirst(RegExp(r'^#\s*'), ''), 1);
          }

          // Horizontal rule
          if (RegExp(r'^[-=_]{3,}$').hasMatch(trimmed)) {
            return const Divider(
              color: AppColors.border,
              height: 24,
            );
          }

          // Bullet list
          if (trimmed.startsWith('- ') ||
              trimmed.startsWith('* ') ||
              trimmed.startsWith('+ ')) {
            return _bulletItem(trimmed.substring(2).trim());
          }

          // Numbered list
          final numMatch = RegExp(r'^(\d+)[\.\)]\s(.*)$').firstMatch(trimmed);
          if (numMatch != null) {
            return _numberedItem(numMatch.group(1)!, numMatch.group(2)!);
          }

          // Empty line
          if (trimmed.isEmpty) {
            return const SizedBox(height: 8);
          }

          // Regular paragraph
          return _paragraph(trimmed);
        }).toList(),
      ),
    );
  }

  Widget _heading(String text, int level) {
    final sizes = {1: 20.0, 2: 17.0, 3: 15.0, 4: 13.0};
    return Padding(
      padding: EdgeInsets.only(top: level == 1 ? 16 : 12, bottom: 6),
      child: Text(
        text,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: sizes[level] ?? 14,
          color: AppColors.accentBlue,
          fontWeight: FontWeight.bold,
          height: 1.4,
        ),
      ),
    );
  }

  Widget _bulletItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, top: 2, bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '  •  ',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: AppColors.accentBlue,
            ),
          ),
          Expanded(
            child: _richText(text),
          ),
        ],
      ),
    );
  }

  Widget _numberedItem(String num, String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, top: 2, bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$num. ',
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: AppColors.accentBlue,
              fontWeight: FontWeight.bold,
            ),
          ),
          Expanded(
            child: _richText(text),
          ),
        ],
      ),
    );
  }

  Widget _paragraph(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 2, bottom: 2),
      child: _richText(text),
    );
  }

  /// Simple rich text renderer for bold/italic
  Widget _richText(String text) {
    final parts = <TextSpan>[];
    final boldRegex = RegExp(r'\*\*(.+?)\*\*');
    final italicRegex = RegExp(r'\*(.+?)\*');

    var remaining = text;
    while (remaining.isNotEmpty) {
      final boldMatch = boldRegex.firstMatch(remaining);
      final italicMatch = italicRegex.firstMatch(remaining);

      int nextSpecial = remaining.length;
      Match? nextMatch;

      if (boldMatch != null && boldMatch.start < nextSpecial) {
        nextSpecial = boldMatch.start;
        nextMatch = boldMatch;
      }
      if (italicMatch != null && italicMatch.start < nextSpecial) {
        // italic only if it starts before bold or no bold
        if (nextMatch == null || italicMatch.start < nextMatch.start) {
          nextSpecial = italicMatch.start;
          nextMatch = italicMatch;
        }
      }

      if (nextMatch == null || nextSpecial > 0) {
        parts.add(TextSpan(
          text: remaining.substring(
              0, nextSpecial > 0 ? nextSpecial : remaining.length),
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            color: AppColors.textPrimary,
            height: 1.6,
          ),
        ));
      }

      if (nextMatch != null) {
        final isBold = nextMatch.pattern == boldRegex.pattern;
        parts.add(TextSpan(
          text: nextMatch.group(1),
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            color: AppColors.textPrimary,
            height: 1.6,
            fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
            fontStyle: isBold ? FontStyle.normal : FontStyle.italic,
          ),
        ));
        remaining = remaining.substring(nextMatch.end);
      } else {
        break;
      }
    }

    return RichText(
      text: TextSpan(children: parts),
    );
  }

  // ─── EDIT MODE (full text editor) ────────────────────────────────

  Widget _buildEditMode() {
    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.accentBlue.withValues(alpha: 0.5)),
      ),
      child: TextField(
        controller: _editCtrl,
        maxLines: null,
        expands: true,
        textAlignVertical: TextAlignVertical.top,
        style: const TextStyle(
          fontFamily: 'monospace',
          fontSize: 12,
          color: AppColors.textPrimary,
          height: 1.6,
        ),
        cursorColor: AppColors.accentBlue,
        decoration: InputDecoration(
          hintText: 'Assignment solution text...',
          hintStyle: TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            color: AppColors.textSecondary.withValues(alpha: 0.3),
          ),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.all(16),
        ),
      ),
    );
  }
}
