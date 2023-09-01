/*import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/widgets.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'package:http/http.dart' as http;

class ProviderService with Disposable {
  var client = http.Client();
  Future<Map<String, dynamic>?> get(String baseUrl,
      {String bodyUrl = "", Map<String, dynamic>? queryParameters}) async {
    final http.Response response;
    try {
      if (queryParameters != null) {
        queryParameters.removeWhere((key, value) => value == null);
      }
      response = await client.get(
        Uri.http(baseUrl, bodyUrl, queryParameters),
        headers: <String, String>{
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Headers": "Origin, X-Requested-With, Content-Type, Accept",
          "Access-Control-Allow-Methods": "GET,PUT,PATCH,POST,DELETE",
          //'Authorization': 'Basic $credential'
        },
      ).timeout(
        const Duration(seconds: 100),
        onTimeout: () {
          // Time has run out, do what you wanted to do.
          return http.Response(
              'Error', 408); // Request Timeout response status code
        },
      );
      return jsonDecode(utf8.decode(response.bodyBytes));
    } catch (e) {
      debugPrint("ProviderService - get - $e");
      return null;
    }
  }

  Future<Map<String, dynamic>?> post(String baseUrl,
      {String bodyUrl = "",
      Map<String, dynamic>? queryParameters,
      required Uint8List body}) async {
    final http.Response response, response1;
    try {
      if (queryParameters != null) {
        queryParameters.removeWhere((key, value) => value == null);
      }
      response = await client
          .post(
        Uri.https(baseUrl, bodyUrl, queryParameters),
        headers: <String, String>{
          //"Content-Encoding": "gzip",
          "Content-Type": "application/json",
          'connection': 'keep-alive',
        }, //gzip.encode(body),
        body: jsonEncode({'p3': base64.encode(body)}),
      )
          .timeout(
        const Duration(seconds: 2),
        onTimeout: () {
          // Time has run out, do what you wanted to do.
          return http.Response(
              'Error', 408); // Request Timeout response status code
        },
      );
      response1 = await client.get(Uri.parse(response.headers["location"]!));
      return jsonDecode(utf8.decode(response1.bodyBytes));
    } catch (e) {
      debugPrint("ProviderInterface - $e");
      return null;
    }
  }

  @override
  void dispose() {
    client.close();
  }
}*/
