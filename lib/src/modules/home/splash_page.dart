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
    Future.delayed(const Duration(seconds: 3)).then(
      (value) {
        Modular.to.popAndPushNamed("/home", arguments: 1);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: groundColor,
      child: Center(
        child: Image.asset(
          'assets/montandocerebro.png',
          height: 300.0,
          width: 400.0,
        ),
      ),
    );
  }
}
