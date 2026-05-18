import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  static Future<bool> checkConnection() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/'))
          .timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<Map<String, dynamic>> sendCommand(String text) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/execute"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"text": text}),
      ).timeout(const Duration(seconds: 300));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is Map) {
          return {
            "result": data["result"]?.toString() ?? "Done",
            "options": data["options"] ?? [],
            "logs": data["logs"] ?? [],
          };
        }
        return {"result": data.toString(), "options": [], "logs": []};
      }
      return {
        "result": "Server error: ${response.statusCode}",
        "options": [],
        "logs": [],
      };
    } on TimeoutException {
      return {"result": "Still working...", "options": [], "logs": []};
    } catch (e) {
      return {"result": "Error: ${e.toString()}", "options": [], "logs": []};
    }
  }

  static Future<Map<String, dynamic>> smartExecute(String text) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/smart-execute"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"text": text}),
      ).timeout(const Duration(seconds: 300));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is Map) {
          return {
            "result": data["result"]?.toString() ?? "Done",
            "options": data["options"] ?? [],
            "logs": data["logs"] ?? [],
          };
        }
        return {"result": data.toString(), "options": [], "logs": []};
      }
      return {"result": "Server error: ${response.statusCode}", "options": [], "logs": []};
    } on TimeoutException {
      return {"result": "Still working...", "options": [], "logs": []};
    } catch (e) {
      return {"result": "Error: ${e.toString()}", "options": [], "logs": []};
    }
  }

  static Future<Map<String, dynamic>> listen({http.Client? client}) async {
    final activeClient = client ?? http.Client();
    final shouldCloseClient = client == null;

    try {
      final response = await activeClient.post(
        Uri.parse("$baseUrl/listen"),
        headers: {"Content-Type": "application/json"},
      ).timeout(const Duration(seconds: 140));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {
          "text": data["text"]?.toString() ?? "",
          "error": "",
        };
      }
      return {
        "text": "",
        "error": "Server error: ${response.statusCode}",
      };
    } on TimeoutException {
      return {
        "text": "",
        "error": "Listening timed out",
      };
    } catch (e) {
      return {
        "text": "",
        "error": "Error: $e",
      };
    } finally {
      if (shouldCloseClient) {
        activeClient.close();
      }
    }
  }

  static Future<void> stopListening() async {
    try {
      await http.post(
        Uri.parse("$baseUrl/listen-stop"),
        headers: {"Content-Type": "application/json"},
      ).timeout(const Duration(seconds: 3));
    } catch (_) {}
  }

  // ─────────────────────────────────────────
  // 📝 ASSIGNMENT SOLVER API CALLS
  // ─────────────────────────────────────────

  /// Solve an assignment from a text description
  static Future<Map<String, dynamic>> solveAssignmentDescription(
      String description) async {
    try {
      final response = await http
          .post(
            Uri.parse("$baseUrl/solve-assignment/description"),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"description": description}),
          )
          .timeout(const Duration(seconds: 300));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {
        "result": "Server error: ${response.statusCode}",
        "status": "error",
      };
    } on TimeoutException {
      return {"result": "Request timed out. The AI is still working.", "status": "timeout"};
    } catch (e) {
      return {"result": "Error: ${e.toString()}", "status": "error"};
    }
  }

  /// Solve an assignment by uploading a file
  static Future<Map<String, dynamic>> solveAssignmentFile(
      String filePath) async {
    try {
      final file = File(filePath);
      if (!await file.exists()) {
        return {"result": "File not found: $filePath", "status": "error"};
      }

      final fileName = filePath.split(Platform.pathSeparator).last;
      final request = http.MultipartRequest(
        'POST',
        Uri.parse("$baseUrl/solve-assignment/file"),
      );

      request.files.add(
        await http.MultipartFile.fromPath('file', filePath),
      );

      final streamedResponse =
          await request.send().timeout(const Duration(seconds: 300));
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {
        "result": "Server error: ${response.statusCode}",
        "status": "error",
      };
    } on TimeoutException {
      return {"result": "Request timed out. The AI is still working.", "status": "timeout"};
    } catch (e) {
      return {"result": "Error: ${e.toString()}", "status": "error"};
    }
  }

  /// Get list of recently solved assignment files
  static Future<Map<String, dynamic>> getAssignmentHistory() async {
    try {
      final response = await http
          .get(Uri.parse("$baseUrl/solve-assignment/history"))
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
      return {"files": [], "status": "error"};
    } catch (e) {
      return {"files": [], "status": "error"};
    }
  }
}
