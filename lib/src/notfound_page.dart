import 'package:flutter/material.dart';

import 'ajustes.dart';

class NotFoundPage extends StatelessWidget {
  const NotFoundPage({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) => Container(
      color: groundColor,
      child: const Center(
        child: Text(
            "Pagina não encontrada !!",
            textAlign: TextAlign.center,
            style: TextStyle(
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
