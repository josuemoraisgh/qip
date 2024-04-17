import 'package:flutter/material.dart';
import '/src/modelView/base_widget/monta_alternativas.dart';

import '../base_widget/custom_button.dart';

class MultiSelectionList extends StatefulWidget {
  //final void Function(String) answerFunc;
  final ValueNotifier<String> answer;
  final String? title;
  final IconData? icon;
  final List<String> options;
  final int? optionsColumnsSize;
  final String? Function(List<ValueNotifier<String>>?)? validator;
  final int maxSizeAnswer;
  final int mimSizeAnswer;
  const MultiSelectionList({
    super.key,
    required this.answer,
    //required this.answerFunc,
    this.title,
    this.icon,
    required this.options,
    this.validator,
    this.optionsColumnsSize,
    required this.maxSizeAnswer,
    required this.mimSizeAnswer,
  });

  @override
  State<MultiSelectionList> createState() => _MultiSelectionListState();
}

class _MultiSelectionListState extends State<MultiSelectionList> {
  late List<ValueNotifier<String>> answerAux;
  late final GlobalKey<FormState> _formKey;

  @override
  void initState() {
    super.initState();
    _formKey = GlobalKey<FormState>();
    var aux = widget.answer.value.split(";");
    if (aux.length != widget.options.length) {
      answerAux = List.generate(
          widget.options.length, (index) => ValueNotifier<String>(""));
    } else {
      answerAux = List.generate(
          widget.options.length, (index) => ValueNotifier<String>(aux[index]));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          widget.answer.value = answerAux.map((e) => e.value).join(';');
        } else {
          widget.answer.value = '';
        }
        _formKey.currentState!.save();
      },
      autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
      child: FormField<List<ValueNotifier<String>>>(
        initialValue: answerAux,
        autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
        validator: widget.validator ??
            (List<ValueNotifier<String>>? value) {
              if (value == null) {
                return 'Por favor escolha um item';
              } else {
                final count = value.where((item) => item.value != "").length;
                if (count < widget.mimSizeAnswer) {
                  return 'Por favor escolha um item';
                } else if (count > widget.maxSizeAnswer) {
                  return 'Por favor escolha um item';
                }
              }
              return (null);
            },
        builder: (FormFieldState<List<ValueNotifier<String>>> state) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            if (widget.title != null)
              Row(
                children: [
                  if (widget.icon != null) Icon(widget.icon!),
                  if (widget.icon != null) const SizedBox(width: 15),
                  Expanded(
                    child: Text(
                      widget.title!,
                      textAlign: TextAlign.justify,
                      style: const TextStyle(
                          fontSize: 15,
                          color: Colors.black,
                          decorationColor: Colors.black),
                    ),
                  ),
                ],
              ),
            if (widget.title != null) const SizedBox(height: 15),
            MontaAlternativas(
              length: widget.options.length,
              optionsColumnsSize: widget.optionsColumnsSize,
              builder: (int i) => Expanded(
                child: !widget.options[i].contains('.png') &&
                        !widget.options[i].contains('.mp3')
                    ? CustomButton(
                        title: widget.options[i],
                        value: widget.options[i],
                        groupValue: answerAux[i],
                        onChanged: (_) {
                          state.didChange(answerAux);
                        },
                      )
                    : TextButton(
                        child: Opacity(
                          opacity: answerAux[i].value != "" ? 1 : 0.3,
                          child: Image.asset(widget.options[i]),
                        ),
                        onPressed: () {
                          setState(() {
                            if (answerAux[i].value != "") {
                              answerAux[i].value = "";
                            } else {
                              answerAux[i].value = widget.options[i]
                                  .replaceAll('assets/emoji_', '')
                                  .replaceAll('.png', '');
                            }
                            state.didChange(answerAux);
                          });
                        },
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
