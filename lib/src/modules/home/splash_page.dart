import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';

import '../../ajustes.dart';

class SplashPage extends StatefulWidget {
  const SplashPage({Key? key}) : super(key: key);

  @override
  State<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends State<SplashPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback(
      //So executa depois que tudo ja estiver desenhado
      (_) {
        Future.delayed(const Duration(seconds: 3)).then(
          (value) {
            Modular.to.popAndPushNamed("/home", arguments: 1);
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Card(
        color: Colors.white,
        elevation: 8,
        shape: const OutlineInputBorder(
            borderRadius: BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.circular(20),
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(20)),
            borderSide: BorderSide(color: Colors.white)),
        child: SizedBox(
          height: 300.0,
          width: 400.0,
          child: Container(
            padding:
                const EdgeInsets.only(left: 20, top: 10, right: 20, bottom: 20),
            child: Container(
              color: groundColor,
              child: Image.asset('assets/montandocerebro.png'),
            ),
          ),
        ),
      ),
    );
  }
}
