import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';

import '../base_widget/custom_button.dart';

class MultiSelectionList extends StatefulWidget {
  final Function(String) answerFunc;
  final int? answerId;
  final String? description;
  final Icon? icon;
  final List<String> itens;
  final int? optionsColumnsSize;
  final String? Function(List<ValueNotifier<String>>?)? validator;
  const MultiSelectionList({
    super.key,
    required this.answerFunc,
    this.description,
    this.icon,
    required this.itens,
    this.validator,
    this.optionsColumnsSize,
    required this.answerId,
  });

  @override
  State<MultiSelectionList> createState() => _MultiSelectionListState();
}

class _MultiSelectionListState extends State<MultiSelectionList> {
  late List<ValueNotifier<String>> answers;
  late final GlobalKey<FormState> _formKey;

  @override
  void initState() {
    _formKey = GlobalKey<FormState>();
    answers = List.filled(widget.itens.length, ValueNotifier<String>(""));
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          _formKey.currentState!.save();
          widget.answerFunc(answers.join(";"));
        } else {
          widget.answerFunc("");
        }
      },
      autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
      child: FormField<List<ValueNotifier<String>>>(
        initialValue: answers,
        autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
        validator: widget.validator,
        builder: (FormFieldState<List<ValueNotifier<String>>> state) => Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            if (widget.description != null)
              Row(
                children: [
                  if (widget.icon != null) widget.icon!,
                  const SizedBox(width: 15),
                  Text(
                    widget.description!,
                    textAlign: TextAlign.start,
                    style: const TextStyle(
                        fontSize: 15,
                        color: Colors.black,
                        decorationColor: Colors.black),
                  ),
                ],
              ),
            if (widget.description != null) const SizedBox(height: 15),
            MontaAlternativas(
              length: widget.itens.length,
              optionsColumnsSize: widget.optionsColumnsSize,
              builder: (int i) => Expanded(
                child: !widget.itens[i].contains('.png') &&
                        !widget.itens[i].contains('.mp3')
                    ? CustomButton(
                        title: widget.itens[i],
                        value: widget.itens[i],
                        groupValue: answers[i],
                        onChanged: (String? _) {
                            if (answers[i].value != "") {
                              answers[i].value = "";
                            } else {
                              answers[i].value =
                                  "${widget.itens[i]} - ${DateTime.now().toString()}";
                            }
                            state.didChange(answers);
                        },
                      )
                    : TextButton(
                        child: Opacity(
                          opacity: answers[i].value != "" ? 1 : 0.3,
                          child: Image.asset(widget.itens[i]),
                        ),
                        onPressed: () {
                          setState(() {
                            if (answers[i].value != "") {
                              answers[i].value = "";
                            } else {
                              answers[i].value =
                                  "${widget.itens[i]} - ${DateTime.now().toString()}";
                            }
                            state.didChange(answers);
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
