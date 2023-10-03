import 'package:dio/dio.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'package:ia_triagem/src/modules/home/telas_controller.dart';
import 'package:ia_triagem/src/modules/home/telas_page.dart';
import '../interfaces/asssistido_remote_storage_interface.dart';
import '../repositories/assistido_gsheet_repository.dart';

class TelasModule extends Module {
  @override
  final List<Module> imports = [];

  @override
  List<Bind<Object>> get binds => [
        Bind.lazySingleton<TelasController>((i) => TelasController()),
        Bind.lazySingleton<Dio>((i) => Dio()),
        Bind.lazySingleton<AssistidoRemoteStorageInterface>(
            (i) => AssistidoRemoteStorageRepository(provider: i<Dio>())),
      ];

  @override
  final List<ModularRoute> routes = [
    //ChildRoute("/", child: (__,_) => const SplashPage()),
    ChildRoute("/", child: (_, args) => TelasPage(id: args.data ?? 5)),
  ];
}
