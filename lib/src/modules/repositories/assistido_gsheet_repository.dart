import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../interfaces/asssistido_remote_storage_interface.dart';

class AssistidoRemoteStorageRepository
    implements AssistidoRemoteStorageInterface {
  Dio? provider;
  final String baseUrl = 'https://script.google.com';

  AssistidoRemoteStorageRepository({this.provider}) {
    provider = provider ?? Modular.get<Dio>();
  }

  Future<dynamic> sendGet(
      {String table = "BDados",
      required String func,
      required String type,
      dynamic p1,
      dynamic p2,
      dynamic p3}) async {
    var response = await provider?.get(
        '$baseUrl/macros/s/AKfycbzQgJBXevX86H1Q_M9csBasJEi5dSQrUJNlANkRmo5MWQenrYvp1p69Wb63-YBdW0QYaQ/exec',
        queryParameters: {
          "table": table,
          "func": func,
          "type": type,
          "p1": p1,
          "p2": p2,
          "p3": p3,
        });
    if (response?.data != null) {
      if ((response?.data?["status"] ?? "Error") == "SUCCESS") {
        return response?.data!["items"];
      } else {
        debugPrint(
            "AssistidoRemoteStorageRepository - sendUrl - ${response?.data}");
      }
    }
    return null;
  }

  @override
  Future<dynamic> addData(List<dynamic>? value, {String table = "BDados"}) async {
    if (value != null) {
      var resp = sendGet(table: table, func: 'add', type: 'data', p1: value);
      return resp;
    }
    return null;
  }

  @override
  Future sendEmail(String value) async {
    return sendGet(func: 'email', type: value);
  }

  @override
  Future<List<dynamic>?> getChanges({String table = "BDados"}) async {
    List<dynamic>? response =
        await sendGet(table: table, func: 'get', type: 'changes');
    return response;
    /*if (response != null) {
        if ((response as List).isNotEmpty) {
        return response.map((e) => Assistido.fromList(e)).toList();
      }
    }
    return null;*/
  }

  @override
  Future<List<dynamic>?> getRow(String rowId, {String table = "BDados"}) async {
    final List<dynamic> response =
        await sendGet(func: 'get', type: 'datas', p1: rowId);
    return response;
  }

  @override
  Future<String?> setData(String rowsId, List<dynamic> data,
      {String table = "BDados"}) async {
    final String? response = await sendGet(
        table: table, func: 'set', type: 'data', p1: rowsId, p2: data);
    return response;
  }

  @override
  Future<dynamic> deleteData(String row, {String table = "BDados"}) async {
    final response =
        await sendGet(table: table, func: 'del', type: 'data', p1: row);
    return response;
  }
}
