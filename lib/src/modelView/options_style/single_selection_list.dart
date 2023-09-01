import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';
import 'package:ia_triagem/src/modelView/card_question/question_frame.dart';

import '../base_widget/custom_button.dart';

class SingleSelectionList extends StatefulWidget {
  final void Function(String, int) answerFunc;
  final int? answerId;
  final String? description;
  final IconData? icon;
  final List<String> itens;
  final bool hasPrefiroNaoDizer;
  final int? optionsColumnsSize;
  final String? otherLabel;
  final Map<String, dynamic>? otherItem;
  const SingleSelectionList({
    super.key,
    required this.answerFunc,
    this.description,
    this.icon,
    required this.itens,
    required this.hasPrefiroNaoDizer,
    this.otherLabel,
    this.otherItem,
    this.optionsColumnsSize,
    this.answerId,
  });

  @override
  State<SingleSelectionList> createState() => _SingleSelectionListState();
}

class _SingleSelectionListState extends State<SingleSelectionList> {
  final _formKey = GlobalKey<FormState>();
  static const double fontSize = 18;
  String answer = "";
  String answerOther = "";

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          widget.answerFunc(
              "${answer == (widget.otherLabel ?? "Outro (Qual?)") ? answerOther : answer} - ${DateTime.now().toString()}",
              widget.answerId ?? 0);
        } else {
          widget.answerFunc('', widget.answerId ?? 0);
        }
      },
      autovalidateMode: AutovalidateMode.onUserInteraction,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (widget.description != null)
            Row(
              children: [
                if (widget.icon != null)
                  Icon(widget.icon!, color: Colors.black54),
                const SizedBox(width: 15),
                Expanded(
                  child: Text(
                    widget.description!,
                    textAlign: TextAlign.justify,
                    style: const TextStyle(
                        fontSize: fontSize,
                        color: Colors.black,
                        decorationColor: Colors.black),
                  ),
                ),
              ],
            ),
          if (widget.description != null) const SizedBox(height: 15),
          FormField<String>(
            initialValue: answer,
            autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
            validator: (String? value) {
              if (value == null) {
                return 'Por favor escolha um item';
              } else {
                if (value.isEmpty) {
                  return 'Por favor escolha um item';
                }
              }
              return (null);
            },
            builder: (FormFieldState<String> state) => MontaAlternativas(
              optionsColumnsSize: widget.optionsColumnsSize,
              length: widget.itens.length,
              builder: (int id) => Expanded(
                child: CustomButton(
                  title: widget.itens[id],
                  value: widget.itens[id],
                  groupValue: answer,
                  onChanged: (String? e) {
                    answer = e.toString();
                    state.didChange(answer);
                  },
                ),
              ),
              childList: <Widget>[
                if (widget.hasPrefiroNaoDizer)
                  Expanded(
                    child: CustomButton(
                        title: "Prefiro não dizer",
                        value: "Prefiro não dizer",
                        groupValue: answer,
                        onChanged: (String? e) {
                          answer = e.toString();
                          state.didChange(answer);
                        }),
                  ),
                if (widget.otherItem != null)
                  Expanded(
                    child: CustomButton(
                      title: widget.otherLabel == null
                          ? "Outro (Qual?)"
                          : widget.otherLabel!,
                      value: widget.otherLabel == null
                          ? "other"
                          : widget.otherLabel!,
                      groupValue: answer,
                      onChanged: (String? e) {
                        answer = e.toString();
                        state.didChange(answer);
                      },
                    ),
                  ),
                if (answer == (widget.otherLabel ?? "other"))
                  Expanded(
                    child: QuestionFrame(
                      answerFunc: (e, i) {
                        answerOther = e.toString();
                        state.didChange(answerOther);
                      },
                      item: widget.otherItem!,
                      answerId: 0,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
