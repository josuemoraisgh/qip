import 'package:dio/dio.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../../notfound_page.dart';
import '/src/modules/home/telas_controller.dart';
import 'telas_page.dart';
import '../interfaces/asssistido_remote_storage_interface.dart';
import '../repositories/assistido_gsheet_repository.dart';

class TelasModule extends Module {
  @override
  void binds(i) {
    i.addInstance<Dio>(Dio());
    i.addSingleton<AssistidoRemoteStorageInterface>(
        AssistidoRemoteStorageRepository.new);
    i.addSingleton<TelasController>(TelasController.new);
  }

  @override
  void routes(r) {
    //r.child('/', child: (_) => const SplashPage());
    r.child('/', child: (_) => TelasPage(id: r.args.data ?? 46));
    r.wildcard(child: (_) => const NotFoundPage());
  }
}
