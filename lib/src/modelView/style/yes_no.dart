import 'package:flutter/material.dart';
import '../base_widget/custom_button.dart';
import '../../modules/home/parameters.dart';
import '../card_question/header_card.dart';

class TypeYesNo extends StatefulWidget {
  final int id;
  final ValueNotifier<List<String>> answer;
  const TypeYesNo({Key? key, required this.id, required this.answer})
      : super(key: key);

  @override
  State<TypeYesNo> createState() => _TypeYesNoState();
}

class _TypeYesNoState extends State<TypeYesNo> {
  final _formKey = GlobalKey<FormState>();
  List<String> answer = [];
  List<ValueNotifier<String>> answerAux = [];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: HeaderCard(
        headerTitle: Text(
          telas[widget.id]!['header'],
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 26, height: 2, color: Colors.white),
        ),
        widgetBody: Form(
          key: _formKey,
          onChanged: () {
            if (_formKey.currentState!.validate()) {
              _formKey.currentState!.save();
              widget.answer.value = [answer.join(";")];
            } else {
              widget.answer.value = [];
            }
          },
          autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
          child: Column(
            children:
                _montaAternativas(telas[widget.id]!['options'] as List<String>),
          ),
        ),
      ),
    );
  }

  List<Widget> _montaAternativas(List<String> items) {
    List<Widget> widgetList = [];
    for (int i = 0; i < items.length; i++) {
      answer.add("");
      answerAux.add(ValueNotifier<String>(""));
      widgetList.add(const SizedBox(height: 10));
      widgetList.add(
        Text(
          (telas[widget.id]!['options'][i] as String),
          textAlign: TextAlign.justify,
          style: const TextStyle(fontSize: 24.0),
        ),
      );
      widgetList.add(const SizedBox(height: 10));
      widgetList.add(
        FormField<String>(
          initialValue: "",
          autovalidateMode: AutovalidateMode.always,
          builder: (FormFieldState<String> state) {
            return Row(
              children: [
                Expanded(
                  child: CustomButton(
                    title: "Sim",
                    value: "Sim",
                    groupValue: answerAux[i],
                    onChanged: (value) {
                      answer[i] = "$value; ${DateTime.now().toString()}";
                      state.didChange(answer[i]);
                    },
                  ),
                ),
                Expanded(
                  child: CustomButton(
                    title: "Não",
                    value: "Não",
                    groupValue: answerAux[i],
                    onChanged: (value) {
                      answer[i] = "$value; ${DateTime.now().toString()}";
                      state.didChange(answer[i]);
                    },
                  ),
                ),
              ],
            );
          },
          validator: (String? value) {
            if (value == null) {
              return 'Por favor escolha um item';
            } else if (value.isEmpty) {
              return 'Por favor escolha um item';
            }
            return (null);
          },
        ),
      );
    }
    return (widgetList);
  }
}
