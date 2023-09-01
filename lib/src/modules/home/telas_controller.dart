import 'package:flutter_modular/flutter_modular.dart';
import '../interfaces/asssistido_remote_storage_interface.dart';

//Reatividade na classe inteira
class TelasController {
  final storage = Modular.get<AssistidoRemoteStorageInterface>();
  List<String> answer = [];
}
