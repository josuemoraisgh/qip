import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../../modelView/style/form.dart';
import '../../modelView/style/terms.dart';
import '../../modelView/style/yes_no.dart';
import '../../notfound_page.dart';
import 'parameters.dart';
import 'telas_controller.dart';

double typeSpace(BuildContext context) {
  const tamDesejado = 500.0;
  final Size size = MediaQuery.of(context).size;
  return ((size.width - tamDesejado) > 0 ? (size.width - tamDesejado) / 2 : 0);
}

class TelasPage extends StatefulWidget {
  final TelasController? controller;
  final int? id;
  const TelasPage({Key? key, required this.id, this.controller})
      : super(key: key);

  @override
  State<TelasPage> createState() => _TelasPageState();
}

class _TelasPageState extends State<TelasPage> {
  late TelasController controller;
  final answerNotifier = ValueNotifier<List<String>>([]);

  @override
  void initState() {
    super.initState();
    controller = widget.controller ?? Modular.get<TelasController>();
  }

  @override
  Widget build(BuildContext context) {
    double tam = typeSpace(context);
    return widget.id == null
        ? const NotFoundPage()
        : Scaffold(
            body: Container(
              padding:
                  EdgeInsets.only(left: tam, top: 10, right: tam, bottom: 10),
              width: MediaQuery.of(context).size.width,
              height: MediaQuery.of(context).size.height,
              color: Colors.lightGreen.shade100,
              //child: SingleChildScrollView(
                child: Column(
                  children: <Widget>[
                    switch (telas[widget.id]!['style'] ?? 'form') {
                      'terms' =>
                        TypeTerms(id: widget.id!, answer: answerNotifier),
                      'form' =>
                        TypeForm(id: widget.id!, answer: answerNotifier),
                      'yes_no' =>
                        TypeYesNo(id: widget.id!, answer: answerNotifier),
                      _ =>
                        const Center(child: Text("Pagina não Encontrada !!")),
                    },
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.only(
                              left: 0, top: 10, right: 10, bottom: 0),
                          alignment: Alignment.bottomRight,
                          child: Text(widget.id.toString()),
                        ),
                        const Spacer(
                          flex: 1,
                        ),
                        if (telas[widget.id]!['hasProx'])
                          Container(
                            padding: const EdgeInsets.only(
                                left: 0, top: 10, right: 10, bottom: 0),
                            alignment: Alignment.bottomRight,
                            child: _proximaButton(),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
           // ),
          );
  }

  Widget _proximaButton() {
    return ValueListenableBuilder<List<String>>(
      valueListenable: answerNotifier,
      builder: (BuildContext context, List<String> resp, Widget? child) =>
          ElevatedButton(
        style: ButtonStyle(
          fixedSize: MaterialStateProperty.all<Size>(const Size(180, 50)),
          shape: MaterialStateProperty.all<RoundedRectangleBorder>(
              RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18.0),
                  side: const BorderSide(color: Colors.white))),
        ),
        onPressed: resp.isEmpty
            ? null
            : () {
                debugPrint("${widget.id!.toString()};${resp.toString()}");
                controller.answer += answerNotifier.value;
                if(widget.id == 75){
                  controller.storage.addData(controller.answer);
                  controller.storage.addData(resp);
                }
                Modular.to.popAndPushNamed("/", arguments: widget.id! + 1);
              },
        child: const Row(
          children: [
            Padding(
              padding: EdgeInsets.only(
                left: 15,
                top: 5,
                right: 15,
                bottom: 5,
              ), //apply padding to all four sides
              child: Text(
                "Próxima",
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w300,
                  fontSize: 24.0,
                ),
              ),
            ),
            Icon(Icons.arrow_forward),
          ],
        ),
      ),
    );
  }
}
