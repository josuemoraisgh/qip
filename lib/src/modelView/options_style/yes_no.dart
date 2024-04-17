import 'package:flutter/material.dart';
import '../base_widget/custom_button.dart';

class TypeYesNo extends StatefulWidget {
  final ValueNotifier<String> answer;
  final List<String> options;
  const TypeYesNo(
      {super.key, required this.answer, required this.options});

  @override
  State<TypeYesNo> createState() => _TypeYesNoState();
}

class _TypeYesNoState extends State<TypeYesNo> {
  final _formKey = GlobalKey<FormState>();
  late List<ValueNotifier<String>> answerAux;

  @override
  void initState() {
    super.initState();
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
          widget.answer.value = answerAux.join(";");
        } else {
          widget.answer.value = "";
        }
        _formKey.currentState!.save();
      },
      autovalidateMode: AutovalidateMode.always, //.onUserInteraction,
      child: Column(
        children: _montaAternativas(widget.options),
      ),
    );
  }

  List<Widget> _montaAternativas(List<String> options) {
    List<Widget> widgetList = [];
    for (int i = 0; i < options.length; i++) {
      widgetList.add(const SizedBox(height: 10));
      widgetList.add(
        Text(
          widget.options[i],
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
                      state.didChange(value);
                    },
                  ),
                ),
                Expanded(
                  child: CustomButton(
                    title: "Não",
                    value: "Não",
                    groupValue: answerAux[i],
                    onChanged: (value) {
                      state.didChange(value);
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
