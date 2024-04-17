import 'dart:math';
import 'package:flutter/material.dart';
import '../base_widget/custom_button.dart';
import '../base_widget/monta_alternativas.dart';

class ArvoreCiculos extends StatefulWidget {
  final String imagem;
  final List<String> itens;
  final int? optionsColumnsSize;
  final List<Color>? colors;
  final ValueNotifier<String> answer;
  const ArvoreCiculos({
    super.key,
    required this.answer,
    required this.imagem,
    required this.itens,
    this.colors,
    this.optionsColumnsSize,
  });

  @override
  State<ArvoreCiculos> createState() => _ArvoreCiculosState();
}

class _ArvoreCiculosState extends State<ArvoreCiculos> {
  List<Offset> pointSelected = [];
  ValueNotifier<String> selectedColor = ValueNotifier<String>('');
  Map<int, String> paintSelected = <int, String>{};
  late Map<String, Paint> paintType;
  late Image image;
  var imageSize =
      ValueNotifier<(double imageWidth, double imageHeight)>((1.0, 1.0));
  ValueNotifier<bool> isChange = ValueNotifier<bool>(true);

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
    image = Image.asset(
      widget.imagem, //assets/arvore2.png
      alignment: Alignment.center,
    );
    image.image.resolve(const ImageConfiguration()).addListener(
      ImageStreamListener(
        (ImageInfo imageInfo, bool synchronousCall) {
          imageSize.value = (
            imageInfo.image.width.toDouble(),
            imageInfo.image.height.toDouble()
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) =>
            ValueListenableBuilder(
          valueListenable: imageSize,
          builder: (context, imageSizeFinal, _) {
            final double width = constraints.maxWidth;
            final double height =
                (width / imageSizeFinal.$1) * imageSizeFinal.$2;
            pointSelected = [
              Offset(0.38 * width, 0.70 * height), //0
              Offset(0.38 * width, 0.60 * height), //1
              Offset(0.20 * width, 0.55 * height), //2
              Offset(0.29 * width, 0.39 * height), //3
              Offset(0.30 * width, 0.48 * height), //4
              Offset(0.40 * width, 0.28 * height), //5
              Offset(0.28 * width, 0.30 * height), //6
              Offset(0.50 * width, 0.21 * height), //7
              Offset(0.59 * width, 0.14 * height), //8
              Offset(0.70 * width, 0.10 * height), //9
              Offset(0.78 * width, 0.18 * height), //10
              Offset(0.90 * width, 0.20 * height), //11
              Offset(0.70 * width, 0.32 * height), //12
              Offset(0.85 * width, 0.31 * height), //13
              Offset(0.83 * width, 0.40 * height), //14
              Offset(0.66 * width, 0.50 * height), //15
              Offset(0.84 * width, 0.52 * height), //16
              Offset(0.90 * width, 0.60 * height), //17
              Offset(0.67 * width, 0.64 * height), //18
              Offset(0.80 * width, 0.70 * height), //19
            ];
            return ValueListenableBuilder(
              valueListenable: selectedColor,
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
                  const SizedBox(height: 10),
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
                          offset: Offset(
                              3.0, 3.0), // shadow direction: bottom right
                        )
                      ],
                    ),
                    child: Center(
                      child: SizedBox(
                        width: MediaQuery.of(context).size.width,
                        child: GestureDetector(
                          key: const ValueKey<int>(1),
                          onPanDown: (DragDownDetails details) {
                            for (int i = 0; i < pointSelected.length; i++) {
                              if (distance(pointSelected[i],
                                      details.localPosition) <=
                                  25) {
                                if (paintSelected[i] == selectedColorNotifier) {
                                  paintSelected[i] = 'white';
                                } else {
                                  paintSelected[i] = selectedColorNotifier;
                                }
                                isChange.value = !isChange.value;
                                break;
                              }
                            }
                            if (paintSelected.isNotEmpty) {
                              var aux = "";
                              paintSelected.forEach((key, value) => aux +=
                                  "${key.toString()} - ${value.toString()};");
                              widget.answer.value = aux.toString();
                            } else {
                              widget.answer.value = '';
                            }        
                          },
                          child: Stack(
                            children: <Widget>[
                              image,
                              ValueListenableBuilder(
                                valueListenable: isChange,
                                builder: (context, __, _) => CustomPaint(
                                  painter: OpenPainter(
                                      pointSelected: pointSelected,
                                      paintSelected: paintSelected,
                                      paintType: paintType),
                                ),
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
          },
        ),
      );

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
    for (int i = 0; i < pointSelected.length; i++) {
      canvas.drawCircle(
          pointSelected[i], 23, paintType[paintSelected[i]] ?? paintWhite);
      canvas.drawCircle(pointSelected[i], 25, paintStroke);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}
