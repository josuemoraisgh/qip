import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'package:just_audio/just_audio.dart';
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
  final _formFieldkey = GlobalKey<FormFieldState>();
  final answerNotifier = ValueNotifier<List<String>>([]);
  var player = AudioPlayer();

  @override
  void initState() {
    super.initState();
    controller = widget.controller ?? Modular.get<TelasController>();
    if (telas[widget.id]!['delay'] != null) {
      Future.delayed(Duration(seconds: telas[widget.id]!['delay']!))
          .then((value) {
        setState(() {
          if (telas[widget.id]!['hasProx']) {
            answerNotifier.value = ['Sucess'];
          } else {
            Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
          }
        });
      });
    }
  }

  void playMusic(String fileName) async {
    if (fileName != '.mp3') {
      try {
        await player.setAudioSource(
          AudioSource.uri(Uri.parse("asset:///$fileName")),
          initialPosition: Duration.zero,
          preload: true,
        );
        //await player.setAsset(path); //load audio from assets
        player.play().then((value) {
          setState(() {
            Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
          });
        });
      } catch (e) {
        debugPrint("Error loading audio source: $e");
      }
    } else {
      Future.delayed(const Duration(seconds: 3)).then((value) {
        setState(() {
          Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
        });
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double tam = typeSpace(constraints.maxWidth);
        return Container(
          padding: EdgeInsets.only(left: tam, top: 10, right: tam, bottom: 10),
          width: constraints.maxWidth,
          color: Colors.lightGreen.shade100,
          //child: SingleChildScrollView(
          child: Center(
            child: Column(
              children: <Widget>[
                Card(
                  color: Colors.green,
                  elevation: 8,
                  margin: const EdgeInsets.all(0.0),
                  shape: const OutlineInputBorder(
                      borderRadius: BorderRadius.only(
                          topLeft: Radius.circular(20),
                          topRight: Radius.circular(20)),
                      borderSide: BorderSide(color: Colors.green)),
                  child: Container(
                    width: constraints.maxWidth - 2 * tam - 50,
                    padding: EdgeInsets.only(
                        left: 20,
                        top: (telas[widget.id]?['header'] != null ? 0 : 10),
                        right: 20,
                        bottom: (telas[widget.id]?['header'] != null ? 5 : 10)),
                    child: telas[widget.id]?['header'] != null
                        ? Text(
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
                          )
                        : null,
                  ),
                ),
                Expanded(
                  child: Card(
                    color: Colors.white,
                    elevation: 8,
                    margin: const EdgeInsets.all(0.0),
                    shape: const OutlineInputBorder(
                        borderRadius: BorderRadius.only(
                            bottomLeft: Radius.circular(20),
                            bottomRight: Radius.circular(20)),
                        borderSide: BorderSide(color: Colors.white)),
                    child: Container(
                      padding: const EdgeInsets.only(
                          left: 20, top: 10, right: 20, bottom: 20),
                      //width: constraints.maxWidth,
                      child: Form(
                        key: _formKey,
                        onChanged: () {
                          if (_formKey.currentState!.validate()) {
                            answerNotifier.value = [
                              _formFieldkey.currentState?.value.join(";")
                            ];
                          } else {
                            answerNotifier.value = [];
                          }
                        },
                        autovalidateMode: AutovalidateMode.onUserInteraction,
                        child: FormField<List<String>>(
                          key: _formFieldkey,
                          //initialValue: answer,
                          validator: (List<String>? value) {
                            if (value == null) {
                              return 'Por favor responda todas as questões';
                            } else {
                              final count =
                                  value.where((item) => item != "").length;
                              if (count != value.length) {
                                return 'Por favor responda todas as questões';
                              }
                            }
                            return (null);
                          },
                          builder: (FormFieldState<List<String>> state) {
                            var itens =
                                telas[widget.id]!['itens']!(controller, state);
                            return ListView.builder(
                              //shrinkWrap: true,
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
                          left: 0, top: 10, right: 10, bottom: 0),
                      alignment: Alignment.bottomRight,
                      child: Text(
                        widget.id.toString(),
                        style: const TextStyle(
                          fontSize: 15,
                        ),
                      ),
                    ),
                    const Spacer(flex: 1),
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
          //),
        );
      },
    );
  }

  Widget _proximaButton() {
    return ValueListenableBuilder<List<String>>(
      valueListenable: answerNotifier,
      builder: (BuildContext context, List<String> resp, Widget? child) =>
          ElevatedButton(
        style: ButtonStyle(
          fixedSize: MaterialStateProperty.all<Size>(const Size(170, 40)),
          shape: MaterialStateProperty.all<RoundedRectangleBorder>(
              RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18.0),
                  side: const BorderSide(color: Colors.white))),
        ),
        onPressed: resp.isEmpty
            ? null
            : () {
                debugPrint("${widget.id.toString()};${resp.toString()}");
                controller.answer += answerNotifier.value;
                if (widget.id == 75) {
                  controller.storage.addData(controller.answer);
                  controller.storage.addData(resp);
                }
                Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
              },
        child: const Row(
          children: [
            Padding(
              padding: EdgeInsets.only(
                left: 10,
                top: 5,
                right: 10,
                bottom: 5,
              ), //apply padding to all four sides
              child: Text(
                "Próxima",
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w300,
                  fontSize: 25.0,
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
