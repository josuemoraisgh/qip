import 'package:dio/dio.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../../notfound_page.dart';
import '/src/modules/home/telas_controller.dart';
import 'telas_page0.dart';
import 'telas_page1.dart';
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
    r.child('/a', child: (_) => TelasPage1(id: r.args.data ?? 1));
    r.child('/', child: (_) => TelasPage0(id: r.args.data ?? 1));
    r.wildcard(child: (_) => const NotFoundPage());
  }
}
