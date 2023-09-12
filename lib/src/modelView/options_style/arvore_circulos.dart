import 'dart:math';
import 'package:flutter/material.dart';

import '../base_widget/custom_button.dart';
import '../base_widget/monta_alternativas.dart';

class ArvoreCiculos extends StatefulWidget {
  final String imagem;
  final List<String> itens;
  final int? optionsColumnsSize;
  final List<Color>? colors;
  final Function(String, int) answerFunc;
  final int? answerId;
  const ArvoreCiculos({
    Key? key,
    required this.answerFunc,
    this.answerId,
    required this.imagem,
    required this.itens,
    this.colors,
    this.optionsColumnsSize,
  }) : super(key: key);

  @override
  State<ArvoreCiculos> createState() => _ArvoreCiculosState();
}

class _ArvoreCiculosState extends State<ArvoreCiculos> {
  static List<Offset> pointSelected = const [
    Offset(160, 420),
    Offset(160, 360),
    Offset(80, 340),
    Offset(135, 240),
    Offset(145, 300),
    Offset(195, 180),
    Offset(130, 180),
    Offset(230, 130),
    Offset(320, 60),
    Offset(270, 90),
    Offset(410, 110),
    Offset(340, 115),
    Offset(390, 200),
    Offset(320, 210),
    Offset(300, 290),
    Offset(390, 300),
    Offset(325, 400),
    Offset(400, 370),
    Offset(350, 445),
  ];
  ValueNotifier<String> selectedColor = ValueNotifier<String>('white');
  Map<int, String> paintSelected = <int, String>{};
  late Map<String, Paint> paintType; //= <String, Paint>{};

  @override
  void initState() {
    super.initState();
    paintType = <String, Paint>{};
    for (int i = 0; i < widget.itens.length; i++) {
      paintType.addEntries(
        {
          widget.itens[i]: Paint()
            ..style = PaintingStyle.fill
            ..color = widget.colors?[i] ?? Colors.black
        }.entries,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder(
      valueListenable: selectedColor ,
      builder: (context, selectedColorNotifier, _) => Column(
        children: [
          MontaAlternativas(
            optionsColumnsSize: widget.optionsColumnsSize ?? 1,
            length: widget.itens.length,
            builder: (int id) => Expanded(
              child: CustomButton(
                title: widget.itens[id],
                value: widget.itens[id],
                color: widget.colors?[id],
                groupValue: selectedColor,
              ),
            ),
          ),
          const SizedBox(height: 30),
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(4.0),
              border: Border.all(width: 0.2, color: Colors.black),
              color: Colors.white,
              boxShadow: const [
                BoxShadow(
                  color: Colors.black,
                  blurRadius: 4.0,
                  spreadRadius: 0.0,
                  offset: Offset(3.0, 3.0), // shadow direction: bottom right
                )
              ],
            ),
            child: Center(
              child: SizedBox(
                width: MediaQuery.of(context).size.width,
                child: GestureDetector(
                  key: const ValueKey<int>(1),
                  onPanDown: (DragDownDetails details) {
                    for (int i = 0; i <= pointSelected.length; i++) {
                      if (distance(pointSelected[i], details.localPosition) <=
                          25) {
                        paintSelected[i] = selectedColorNotifier;
                        break;
                      }
                    }
                    if (paintSelected.isNotEmpty) {
                      var aux = "";
                      paintSelected.forEach((key, value) =>
                          aux += "${key.toString()} - ${value.toString()}; ");
                      widget.answerFunc(
                          "${aux.toString()} - ${DateTime.now().toString()}",
                          widget.answerId ?? 0);
                    } else {
                      widget.answerFunc('', widget.answerId ?? 0);
                    }
                    setState(() {});
                  },
                  child: Stack(
                    children: <Widget>[
                      Image.asset(
                        widget.imagem, //assets/arvore2.png
                        alignment: Alignment.center,
                      ),
                      CustomPaint(
                        painter: OpenPainter(
                            pointSelected: pointSelected,
                            paintSelected: paintSelected,
                            paintType: paintType),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  num distance(Offset ponto1, Offset ponto2) {
    return sqrt(pow(ponto1.dx - ponto2.dx, 2) + pow(ponto1.dy - ponto2.dy, 2));
  }
}

class OpenPainter extends CustomPainter {
  List<Offset> pointSelected;
  Map<int, String> paintSelected;
  Map<String, Paint> paintType;
  OpenPainter(
      {required this.pointSelected,
      required this.paintSelected,
      required this.paintType});

  @override
  void paint(Canvas canvas, Size size) {
    var paintStroke = Paint()
      ..color = Colors.black
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;

    var paintWhite = Paint()
      ..style = PaintingStyle.fill
      ..color = Colors.white;
    for (int i = 0; i <= pointSelected.length; i++) {
      canvas.drawCircle(
          pointSelected[i], 23, paintType[paintSelected[i]] ?? paintWhite);
      canvas.drawCircle(pointSelected[i], 25, paintStroke);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}
