import 'package:flutter_modular/flutter_modular.dart';
import 'notfound_page.dart';
import 'modules/home/telas_module.dart';

class AppModule extends Module {
  @override
  final List<Module> imports = [];

  @override
  List<Bind<Object>> get binds => [];

  @override
  final List<ModularRoute> routes = [
    ModuleRoute("/", module: TelasModule()),
    WildcardRoute(child: (_, __) => const NotFoundPage())
  ];
}
