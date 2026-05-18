import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:file_picker/file_picker.dart';
import '../models/log_entry.dart';
import '../services/api_service.dart';

/// A full-screen assignment solver page with two modes:
/// 1. Describe your assignment (text input)
/// 2. Upload an assignment file
class AssignmentSolverScreen extends StatefulWidget {
  const AssignmentSolverScreen({super.key});

  @override
  State<AssignmentSolverScreen> createState() => _AssignmentSolverScreenState();
}

class _AssignmentSolverScreenState extends State<AssignmentSolverScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;
  final TextEditingController _descCtrl = TextEditingController();
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
      setState(() {
        _resultMessage = response['result'] ?? 'No response';
        _isProcessing = false;
      });
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _isProcessing = false;
      });
    }
  }

  Future<void> _pickAndSolveFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: [
          'txt', 'pdf', 'docx', 'xlsx', 'csv', 'py', 'js',
          'html', 'css', 'json', 'md', 'java', 'cpp', 'c',
        ],
      );

      if (result == null || result.files.isEmpty) return;

      final file = result.files.first;
      setState(() {
        _selectedFileName = file.name;
        _selectedFilePath = file.path;
        _isProcessing = true;
        _resultMessage = null;
      });

      if (file.path == null) {
        setState(() {
          _resultMessage = 'Cannot access file path on this platform';
          _isProcessing = false;
        });
        return;
      }

      final response = await ApiService.solveAssignmentFile(file.path!);
      setState(() {
        _resultMessage = response['result'] ?? 'No response';
        _isProcessing = false;
      });
    } catch (e) {
      setState(() {
        _resultMessage = 'Error: $e';
        _isProcessing = false;
      });
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
        title: const Text(
          '📝 Assignment Solver',
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

  Widget _buildDescriptionTab() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Describe Your Assignment',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 16,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
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
                hintText: 'Example: "Write about Newton\'s three laws of motion '
                    'with examples and derivations for my Physics class"',
                hintStyle: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: AppColors.textSecondary.withOpacity(0.5),
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

  Widget _buildFileUploadTab() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Upload Assignment File',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 16,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Upload your assignment file (.pdf, .docx, .txt, .xlsx, .py, etc.) '
            'and the AI will read and solve it.',
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              color: AppColors.textSecondary,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 24),
          // File picker area
          GestureDetector(
            onTap: _isProcessing ? null : _pickAndSolveFile,
            child: Container(
              width: double.infinity,
              height: 180,
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
                    size: 48,
                    color: _selectedFileName != null
                        ? AppColors.successGreen
                        : AppColors.textSecondary.withOpacity(0.5),
                  ),
                  const SizedBox(height: 12),
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
                    const SizedBox(height: 6),
                    Text(
                      'Tap to pick a different file',
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 10,
                        color: AppColors.textSecondary.withOpacity(0.5),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          // Supported formats
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
                Text(
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
                    '.txt', '.pdf', '.docx', '.xlsx', '.csv',
                    '.py', '.js', '.html', '.css', '.json',
                    '.md', '.java', '.cpp', '.c',
                  ].map((ext) => Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2,
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
                  )).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultPanel() {
    final isSuccess = _resultMessage!.contains('completed') ||
        _resultMessage!.contains('solved') ||
        _resultMessage!.contains('Saved');

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(maxHeight: 240),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          top: BorderSide(
            color: isSuccess ? AppColors.successGreen : AppColors.errorRed,
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
                isSuccess ? Icons.check_circle : Icons.error,
                size: 18,
                color: isSuccess ? AppColors.successGreen : AppColors.errorRed,
              ),
              const SizedBox(width: 8),
              Text(
                isSuccess ? 'Assignment Solved!' : 'Result',
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 14,
                  color: isSuccess ? AppColors.successGreen : AppColors.errorRed,
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
