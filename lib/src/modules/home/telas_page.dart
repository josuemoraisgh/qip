import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../../ajustes.dart';
import 'parameters.dart';
import 'telas_controller.dart';

double typeSpace(double maxWidth) {
  const tamDesejado = 500.0;
  return ((maxWidth - tamDesejado) > 0 ? (maxWidth - tamDesejado) / 2 : 0);
}

class TelasPage extends StatefulWidget {
  final TelasController? controller;
  final int id;
  const TelasPage({Key? key, required this.id, this.controller})
      : super(key: key);

  @override
  State<TelasPage> createState() => _TelasPageState();
}

class _TelasPageState extends State<TelasPage> {
  late TelasController controller;
  final _formKey = GlobalKey<FormState>();
  final formFieldkey = GlobalKey<FormFieldState<List<ValueNotifier<String>>>>();
  final answerNotifier = ValueNotifier<List<ValueNotifier<String>>>([]);

  @override
  void initState() {
    super.initState();
    controller = widget.controller ?? Modular.get<TelasController>();
    controller.idPage.value = widget.id;
    if (telas[widget.id]?['delay'] != null) {
      WidgetsBinding.instance.addPostFrameCallback(
        //So executa depois que tudo ja estiver desenhado
        (_) {
          controller.delay(
            id: widget.id,
            hasProx: telas[widget.id]!['hasProx'],
            time: telas[widget.id]!['delay']!,
            setState: setState,
            answerNotifier: answerNotifier,
          );
        },
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    debugPrint(Modular.args.data.toString());
    if (telas[widget.id]?['answerLenght'] != 0) {
      controller.answerAux.value = List.generate(
          telas[widget.id]?['answerLenght'],
          (index) => ValueNotifier<String>(""));
    }
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double tam = typeSpace(constraints.maxWidth);
        return Container(
          padding: EdgeInsets.only(left: tam, top: 10, right: tam, bottom: 10),
          width: constraints.maxWidth,
          color: groundColor,
          //child: SingleChildScrollView(
          child: Center(
            child: Column(
              //mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Card(
                  color: headerColor, //Colors.green,
                  elevation: 8,
                  margin: const EdgeInsets.all(0.0),
                  shape: const OutlineInputBorder(
                    borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(20),
                        topRight: Radius.circular(20)),
                    borderSide: borderSideValue,
                  ),
                  child: Container(
                    width: constraints.maxWidth - 2 * tam - 50,
                    padding: EdgeInsets.only(
                        left: 20,
                        top: (telas[widget.id]?['header'] != null ? 0 : 10),
                        right: 20,
                        bottom: (telas[widget.id]?['header'] != null ? 5 : 10)),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (telas[widget.id]?['leading'] != null)
                          Padding(
                            padding: const EdgeInsets.only(
                                left: 0, top: 10, right: 20, bottom: 0),
                            child: IconButton(
                              icon: Icon(
                                controller.isImagemFull.value == true
                                    ? telas[widget.id]!['leading']
                                        ['selectedIcon']
                                    : telas[widget.id]!['leading']
                                        ['deselectedIcon'],
                                color: Colors.white,
                              ),
                              onPressed: () {
                                controller.isImagemFull.value =
                                    !controller.isImagemFull.value;
                              },
                            ),
                          ),
                        if (telas[widget.id]?['header'] != null)
                          Flexible(
                            child: Text(
                              telas[widget.id]!['header'],
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                fontSize: 26,
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
                      ],
                    ),
                  ),
                ),
                Flexible(
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
                    child: Container(
                      padding: const EdgeInsets.only(
                          left: 20, top: 10, right: 20, bottom: 20),
                      child: Form(
                        key: _formKey,
                        onChanged: () {
                          if (_formKey.currentState!.validate()) {
                            List<ValueNotifier<String>> answer =
                                formFieldkey.currentState!.value!;
                            answerNotifier.value = answer;
                          } else {
                            answerNotifier.value = [];
                          }
                        },
                        autovalidateMode: AutovalidateMode.onUserInteraction,
                        child: FormField<List<ValueNotifier<String>>>(
                          key: formFieldkey,
                          initialValue: controller.answerAux.value,
                          validator: (List<ValueNotifier<String>>? value) {
                            if (value == null) {
                              return 'Por favor responda todas as questões';
                            } else {
                              final count = value
                                  .where((item) => item.value != "")
                                  .length;
                              if (count != value.length) {
                                return 'Por favor responda todas as questões';
                              }
                            }
                            return (null);
                          },
                          builder: (FormFieldState<List<ValueNotifier<String>>>
                              state) {
                            List<Widget> itens = telas[widget.id]!['itens']!(
                                controller, formFieldkey);
                            return ListView.builder(
                              shrinkWrap: true,
                              itemCount: itens.length,
                              itemBuilder: (BuildContext context, int index) =>
                                  itens[index],
                            );
                          },
                        ),
                      ),
                    ),
                  ),
                ),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.only(
                          left: 20, top: 0, right: 10, bottom: 0),
                      alignment: Alignment.bottomRight,
                      child: Text(
                        "Pagina: ${widget.id.toString()}",
                        style: const TextStyle(
                          color: Colors.black,
                          fontSize: 15,
                          decoration: TextDecoration.none, //Retira o sublinhado
                        ),
                      ),
                    ),
                    const Spacer(flex: 1),
                    if (telas[widget.id]!['hasProx'])
                      Container(
                        padding: const EdgeInsets.only(
                            left: 0, top: 0, right: 10, bottom: 0),
                        alignment: Alignment.bottomRight,
                        child: _proximaButton(),
                      ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _proximaButton() {
    return ValueListenableBuilder<List<ValueNotifier<String>>>(
      valueListenable: answerNotifier,
      builder: (BuildContext context, List<ValueNotifier<String>> resp,
              Widget? child) =>
          ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: headerColor,
          disabledBackgroundColor: groundColor,

          foregroundColor: Colors.white,
          disabledForegroundColor: Colors.blueGrey,

          shadowColor: Colors.black, //specify the button's elevation color
          elevation: 8.0, //buttons Material shadow
          textStyle: const TextStyle(
              fontFamily: 'roboto'), //specify the button's text TextStyle

          fixedSize: const Size(180, 30),
          side: borderSideValue,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(35.0)),
          enabledMouseCursor: MouseCursor.defer,
          disabledMouseCursor: MouseCursor.uncontrolled,
          visualDensity: const VisualDensity(horizontal: 1.0, vertical: 1.0),
          tapTargetSize: MaterialTapTargetSize.padded,
          animationDuration: const Duration(milliseconds: 100),
          enableFeedback: true, //to set the feedback to true or false
          alignment: Alignment.bottomCenter, //set the button's child Alignment
        ),
        /*ButtonStyle(
          fixedSize: MaterialStateProperty.all<Size>(const Size(170, 40)),
          shape: MaterialStateProperty.all<RoundedRectangleBorder>(
              RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18.0),
                  side: const BorderSide(color: Colors.white))),
        ),*/
        onPressed: resp.isEmpty
            ? null
            : () {
                List<String> aux = resp.map((e) => e.value).toList();
                debugPrint("${widget.id.toString()};${aux.toString()}");
                controller.answer += [
                  "${DateTime.now().toString()} - ${aux.join(";")}"
                ];
                if (widget.id == 75) {
                  controller.storage.addData(controller.answer);
                  controller.storage.addData(resp);
                }
                Modular.to.popAndPushNamed('/', arguments: widget.id + 1);
              },
        child: Row(
          children: [
            Padding(
              padding: const EdgeInsets.only(
                left: 10,
                top: 5,
                right: 10,
                bottom: 5,
              ), //apply padding to all four sides
              child: Text(
                "Próxima",
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 25,
                  height: 1.0,
                  //color: Colors.white,
                  shadows: resp.isEmpty
                      ? null
                      : <Shadow>[
                          const Shadow(
                            offset: Offset(2.0, 2.0),
                            blurRadius: 1.0,
                            color: Color.fromARGB(255, 0, 0, 0),
                          ),
                        ],
                ),
              ),
            ),
            const Icon(Icons.arrow_forward),
          ],
        ),
      ),
    );
  }
}
