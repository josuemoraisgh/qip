import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';

import 'ajustes.dart';

class NotFoundPage extends StatelessWidget {
  const NotFoundPage({super.key});

  @override
  Widget build(BuildContext context) => Container(
        color: groundColor,
        child: Center(
          child: Text(
            "Pagina '${Modular.args.uri}' não encontrada !!",
            textAlign: TextAlign.center,
            style: const TextStyle(
              decoration: TextDecoration.none,
              fontSize: 50,
              height: 1.5,
              color: Colors.white,
              shadows: <Shadow>[
                Shadow(
                  offset: Offset(2.0, 2.0),
                  blurRadius: 1.0,
                  color: Color.fromARGB(255, 0, 0, 0),
                ),
              ],
            ),
          ),
        ),
      );
}
