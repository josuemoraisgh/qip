import 'package:flutter_modular/flutter_modular.dart';
import 'package:qip_triagem/src/notfound_page.dart';
import 'modules/home/telas_module.dart';

class AppModule extends Module {
  @override
  void routes(r) {
    r.module(Modular.initialRoute, module: TelasModule());
    r.wildcard(child: (_) => const NotFoundPage());
  }
}
