import 'package:flutter/material.dart';
import '../base_widget/custom_button.dart';
import '../base_widget/monta_alternativas.dart';

class MuroColorido extends StatefulWidget {
  final String imagem;
  final List<String> itens;
  final int? optionsColumnsSize;
  final List<Color>? colors;
  final ValueNotifier<String> answer;
  const MuroColorido({
    super.key,
    required this.answer,
    required this.imagem,
    required this.itens,
    this.colors,
    this.optionsColumnsSize,
  });

  @override
  State<MuroColorido> createState() => _MuroColoridoState();
}

class _MuroColoridoState extends State<MuroColorido> {
  List<Rect> pointSelected = [];
  ValueNotifier<String> selectedColor = ValueNotifier<String>('white');
  Map<int, String> paintSelected = <int, String>{};
  ValueNotifier<bool> isChange = ValueNotifier<bool>(true);
  late Map<String, Paint> paintType;

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
    pointSelected = List.filled(40, Rect.zero);
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final double width = constraints.maxWidth;
          const double height = 200;
          {
            const double qtdadeTijolosLinha = 3;
            const double ini = 20;
            final double tam = (width - 2 * ini) / qtdadeTijolosLinha;

            for (int i = 0; i < 6; i++) {
              for (int j = 0; j < qtdadeTijolosLinha; j++) {
                if (i % 2 == 0) {
                  if (j != 2) {
                    pointSelected[i * 5 + j] = Rect.fromLTRB(
                        tam * j + tam/2 + ini,
                        30.0 * i + 10.0,
                        tam * (j + 1) + tam/2 + ini,
                        30.0 * (i + 1) + 10.0);
                  }
                } else {
                  pointSelected[i * 5 + j] = Rect.fromLTRB(
                      tam * j + ini,
                      30.0 * i + 10.0,
                      tam * (j + 1) + ini,
                      30.0 * (i + 1) + 10.0);
                }
              }
            }
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
                        width: width,
                        height: height,
                        child: GestureDetector(
                          key: const ValueKey<int>(1),
                          onPanDown: (DragDownDetails details) {
                            for (int i = 0; i < pointSelected.length; i++) {
                              if (isInside(
                                  pointSelected[i], details.localPosition)) {
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
                          child: ValueListenableBuilder(
                            valueListenable: isChange,
                            builder: (context, __, _) => CustomPaint(
                              painter: OpenPainter(
                                  pointSelected: pointSelected,
                                  paintSelected: paintSelected,
                                  paintType: paintType),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          }
        },
      );
  bool isInside(Rect ponto1, Offset ponto2) {
    return ponto1.left < ponto2.dx &&
        ponto1.right > ponto2.dx &&
        ponto1.top < ponto2.dy &&
        ponto1.bottom > ponto2.dy;
  }
}

class OpenPainter extends CustomPainter {
  List<Rect> pointSelected;
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
      canvas.drawRect(
          pointSelected[i], paintType[paintSelected[i]] ?? paintWhite);
      canvas.drawRect(pointSelected[i], paintStroke);
    }
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => true;
}
