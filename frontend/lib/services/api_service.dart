import 'dart:async';
import 'dart:convert';
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
}
