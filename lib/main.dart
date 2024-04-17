import 'package:flutter/widgets.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'src/app_module.dart';
import 'src/app_widget.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(ModularApp(module: AppModule(), child: const AppWidget()));
}
