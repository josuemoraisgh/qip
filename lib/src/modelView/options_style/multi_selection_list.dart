import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';

import '../base_widget/custom_button.dart';

class MultiSelectionList extends StatefulWidget {
  //final void Function(String) answerFunc;
  final ValueNotifier<String> answer;
  final int? answerId;
  final String? description;
  final Icon? icon;
  final List<String> itens;
  final int? optionsColumnsSize;
  final String? Function(List<ValueNotifier<String>>?)? validator;
  const MultiSelectionList({
    super.key,
    required this.answer,
    //required this.answerFunc,
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
  late List<ValueNotifier<String>> answerAux;
  late final GlobalKey<FormState> _formKey;

  @override
  void initState() {
    super.initState();

    _formKey = GlobalKey<FormState>();

    var aux = widget.answer.value.split(";");
    if (aux.length != widget.itens.length) {
      answerAux = List.filled(widget.itens.length, ValueNotifier<String>(""));
    } else {
      answerAux = List.generate(
          widget.itens.length, (index) => ValueNotifier<String>(aux[index]));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          widget.answer.value = answerAux.join(';');
          //if(widget.answerFunc != null) widget.answerFunc!(answerAux.join(';'));
        } else {
          widget.answer.value = '';
          //if(widget.answerFunc != null) widget.answerFunc!('');
        }
        _formKey.currentState!.save();
      },
      autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
      child: FormField<List<ValueNotifier<String>>>(
        initialValue: answerAux,
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
                        groupValue: answerAux[i],
                        onChanged: (_) {
                          state.didChange(answerAux);
                        },
                      )
                    : TextButton(
                        child: Opacity(
                          opacity: answerAux[i].value != "" ? 1 : 0.3,
                          child: Image.asset(widget.itens[i]),
                        ),
                        onPressed: () {
                          setState(() {
                            if (answerAux[i].value != "") {
                              answerAux[i].value = "";
                            } else {
                              answerAux[i].value = widget.itens[i];
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
