import 'dart:math';
import 'package:flutter/material.dart';

class FindImages extends StatefulWidget {
  final String imagem;
  //final Function(String)? answerFunc;
  final ValueNotifier<String> answer;
  const FindImages({
    super.key,
    required this.answer,
    //this.answerFunc,
    required this.imagem,
  });

  @override
  State<FindImages> createState() => _FindImagesState();
}

class _FindImagesState extends State<FindImages> {
  List<Offset> pointSelected = [];

  @override
  void initState() {
    super.initState();
    if (widget.answer.value != "") {
      var aux = widget.answer.value.split(";");
      pointSelected = List.generate(
        aux.length,
        (index) {
          var aux2 = aux[index].split(",");
          return Offset(double.parse(aux2[0]),
              aux.length <= 1 ? 0.0 : double.parse(aux2[1]));
        },
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
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
              if (pointSelected.firstWhere(
                      (element) =>
                          distance(element, details.localPosition) <= 11,
                      orElse: () => Offset.zero) !=
                  Offset.zero) {
                pointSelected.removeWhere((element) =>
                    distance(element, details.localPosition) <= 11);                    
              } else {
                pointSelected.add(details.localPosition);
              }
              if (pointSelected.isNotEmpty) {
                widget.answer.value =
                    pointSelected.map((e) => "${e.dx},${e.dy}").join(";");
              } else {
                widget.answer.value = '';
              }
            },
            child: Stack(
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.only(
                      left: 5, top: 5, right: 5, bottom: 5),
                  child: Image.asset(
                    widget.imagem, //assets/arvore2.png
                    alignment: Alignment.center,
                  ),
                ),
                CustomPaint(
                  painter: OpenPainter(pointSelected: pointSelected),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  num distance(Offset ponto1, Offset ponto2) {
    return sqrt(pow(ponto1.dx - ponto2.dx, 2) + pow(ponto1.dy - ponto2.dy, 2));
  }
}

class OpenPainter extends CustomPainter {
  List<Offset> pointSelected;
  OpenPainter({required this.pointSelected});

  @override
  void paint(Canvas canvas, Size size) {
    var paint1 = Paint()
      ..color = Colors.red
      ..style = PaintingStyle.fill;
    var paint2 = Paint()
      ..color = Colors.black
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;

    for (var ps in pointSelected) {
      canvas.drawCircle(ps, 10, paint1);
      canvas.drawCircle(ps, 11, paint2);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}
