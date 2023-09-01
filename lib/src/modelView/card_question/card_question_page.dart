import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/card_question/question_frame.dart';

import 'display_frame.dart';
import 'header_card.dart';
import '../base_widget/monta_alternativas.dart';

class CardQuestionPage extends StatefulWidget {
  final String? header;
  final dynamic body;
  final ValueNotifier<List<String>> answer;
  final void Function(String audio)? playMusic;
  const CardQuestionPage(
      {super.key,
      required this.answer,
      this.header,
      required this.body,
      this.playMusic});

  @override
  State<CardQuestionPage> createState() => _CardQuestionPageState();
}

class _CardQuestionPageState extends State<CardQuestionPage> {
  final _formKey = GlobalKey<FormState>();
  List<String> answer = [];

  @override
  void initState() {
    super.initState();
    if (widget.body is! String) {
      final count = (widget.body as List)
              .where((item) => (item['options'] ?? "") != "")
              .length +
          (widget.body as List)
              .where((item) => (item['labelText'] ?? "") != "")
              .length;
      answer = List.filled(count, "");
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: HeaderCard(
        headerTitle: widget.header != null
            ? Text(
                widget.header!,
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
        widgetBody: (widget.body is String)
            ? Text(
                widget.body,
                textAlign: TextAlign.justify,
                style: const TextStyle(color: Colors.black, fontSize: 15.0),
              )
            : Form(
                key: _formKey,
                onChanged: () {
                  if (_formKey.currentState!.validate()) {
                    widget.answer.value = [answer.join(";")];
                  } else {
                    widget.answer.value = [];
                  }
                },
                autovalidateMode: AutovalidateMode.onUserInteraction,
                child: FormField<List<String>>(
                  initialValue: answer,
                  validator: (List<String>? value) {
                    if (value == null) {
                      return 'Por favor responda todas as questões';
                    } else {
                      final count = value.where((item) => item != "").length;
                      if (count != value.length) {
                        return 'Por favor responda todas as questões';
                      }
                    }
                    return (null);
                  },
                  builder: (FormFieldState<List<String>> state) {
                    List<Map<String, dynamic>>? item = widget.body;
                    int identificador = 0;
                    return MontaAlternativas(
                      length: item?.length ?? 1,
                      builder: (i) {
                        return Expanded(
                          child: Column(
                            children: <Widget>[
                                  if (item![i]['body_hasFrame'] != null)
                                    DisplayFrame(
                                      item: item[i],
                                      playMusic: widget.playMusic,
                                    ),
                                  if ((item[i]['body_hasFrame'] ?? false) ==
                                          true &&
                                      (item[i]['body'] ?? "") != "")
                                    const SizedBox(height: 15),
                                  if ((item[i]['options'] != null) ||
                                      (item[i]['labelText'] != null))
                                    QuestionFrame(
                                      item: item[i],
                                      answerId: identificador++,
                                      answerFunc: (value, id) {
                                        answer[id] = value;
                                        state.didChange(answer);
                                      },
                                    ),
                                ] +
                                ((item[i]['has_divider'] ?? false) == true
                                    ? <Widget>[
                                        const SizedBox(height: 15),
                                        const Divider(),
                                        const SizedBox(height: 15),
                                      ]
                                    : <Widget>[]),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
      ),
    );
  }
}
