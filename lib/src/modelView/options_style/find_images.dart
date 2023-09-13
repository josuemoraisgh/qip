import 'dart:math';
import 'package:flutter/material.dart';

class FindImages extends StatefulWidget {
  final String imagem;
  final Function(String) answerFunc;
  final int? answerId;
  final List<Offset> pointSelected;
  const FindImages(
      {Key? key,
      required this.answerFunc,
      this.answerId,
      required this.imagem,
      required this.pointSelected})
      : super(key: key);

  @override
  State<FindImages> createState() => _FindImagesState();
}

class _FindImagesState extends State<FindImages> {
  @override
  void initState() {
    super.initState();
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
              if (widget.pointSelected.firstWhere(
                      (element) =>
                          distance(element, details.localPosition) <= 11,
                      orElse: () => Offset.zero) !=
                  Offset.zero) {
                widget.pointSelected.removeWhere((element) =>
                    distance(element, details.localPosition) <= 11);
              } else {
                widget.pointSelected.add(details.localPosition);
              }
              if (widget.pointSelected.isNotEmpty) {
                widget.answerFunc(
                    "${widget.pointSelected.toString().replaceAll('Offset', '')} - ${DateTime.now().toString()}");
              } else {
                widget.answerFunc('');
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
                  painter: OpenPainter(pointSelected: widget.pointSelected),
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
