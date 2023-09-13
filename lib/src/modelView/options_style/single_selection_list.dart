import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';

import '../base_widget/custom_button.dart';

class SingleSelectionList extends StatefulWidget {
  final void Function(String) answerFunc;
  final int? answerId;
  final String? title;
  final IconData? icon;
  final List<String> options;
  final List<Color>? colors;
  final bool hasPrefiroNaoDizer;
  final int? optionsColumnsSize;
  final String? otherLabel;
  final Widget? otherItem;
  const SingleSelectionList({
    super.key,
    required this.answerFunc,
    this.title,
    this.icon,
    required this.options,
    required this.hasPrefiroNaoDizer,
    this.otherLabel,
    this.optionsColumnsSize,
    this.answerId,
    this.colors,
    this.otherItem,
  });

  @override
  State<SingleSelectionList> createState() => _SingleSelectionListState();
}

class _SingleSelectionListState extends State<SingleSelectionList> {
  final _formKey = GlobalKey<FormState>();
  static const double fontSize = 18;
  ValueNotifier<String> answer = ValueNotifier<String>("");
  ValueNotifier<String> answerOther = ValueNotifier<String>("");

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          widget.answerFunc(
              "${answer.value == (widget.otherLabel ?? "Outro (Qual?)") ? answerOther : answer} - ${DateTime.now().toString()}");
        } else {
          widget.answerFunc('');
        }
      },
      autovalidateMode: AutovalidateMode.onUserInteraction,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (widget.title != null)
            Row(
              children: [
                if (widget.icon != null)
                  Icon(widget.icon!, color: Colors.black54),
                const SizedBox(width: 15),
                Expanded(
                  child: Text(
                    widget.title!,
                    textAlign: TextAlign.justify,
                    style: const TextStyle(
                        fontSize: fontSize,
                        color: Colors.black,
                        decorationColor: Colors.black),
                  ),
                ),
              ],
            ),
          if (widget.title != null) const SizedBox(height: 15),
          FormField<ValueNotifier<String>>(
            initialValue: answer,
            autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
            validator: (ValueNotifier<String>? value) {
              if (value == null) {
                return 'Por favor escolha um item';
              } else {
                if (value.value.isEmpty) {
                  return 'Por favor escolha um item';
                }
              }
              return (null);
            },
            builder: (FormFieldState<ValueNotifier<String>> state) =>
                MontaAlternativas(
              optionsColumnsSize: widget.optionsColumnsSize,
              length: widget.options.length,
              builder: (int id) => Expanded(
                child: CustomButton(
                  title: widget.options[id],
                  value: widget.options[id],
                  color: widget.colors?[id],
                  groupValue: answer,
                  onChanged: (String? e) {
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
                        state.didChange(answer);
                      },
                    ),
                  ),
                if (answer.value == (widget.otherLabel ?? "other"))
                  Expanded(
                    child: widget.otherItem!,
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
