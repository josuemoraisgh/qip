import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_modular/flutter_modular.dart';
import '../../modules/home/telas_controller.dart';
import '../options_style/single_selection_list.dart';
import '../../modules/home/parameters.dart';
import '../card_question/header_card.dart';

class TypeTerms extends StatefulWidget {
  final int id;
  final ValueNotifier<List<String>> answer;
  const TypeTerms({Key? key, required this.id, required this.answer})
      : super(key: key);

  @override
  State<TypeTerms> createState() => _TypeTermsState();
}

class _TypeTermsState extends State<TypeTerms> {
  late TelasController controller;
  final _formKey = GlobalKey<FormState>();
  final textController = TextEditingController();
  final focusNode = FocusNode();
  @override
  void initState() {
    super.initState();
    controller = Modular.get<TelasController>();
  }

  _sendEmailMessage() {
    //Faça aqui o codigo Eviando a mensagem para o Email no textController.text;
    controller.storage.sendEmail(textController.text).whenComplete(() => "");
    textController.text = '';
    focusNode.requestFocus();
  }

  _changeComboBox(String value) {
    if (value.contains('Concordo')) {
      widget.answer.value = [value];
    } else {
      widget.answer.value = [];
    }
  }

  @override
  Widget build(BuildContext context) {
    return HeaderCard(
      headerTitle: Text(
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
      ),
      widgetBody: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            telas[widget.id]!['body1'],
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answerFunc: (String e, int i) => _changeComboBox(e),
            hasPrefiroNaoDizer: false,
            itens: const ['Concordo', 'Não concordo'],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          Text(
            telas[widget.id]!['body2'],
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Form(
              key: _formKey,
              autovalidateMode: AutovalidateMode.always,
              child: TextFormField(
                keyboardType: TextInputType.emailAddress,
                inputFormatters: [
                  FilteringTextInputFormatter.deny(
                      RegExp('[\\s]')), // Remove espaços em branco
                  FilteringTextInputFormatter.deny(RegExp(
                      r'[^\w\s@\.-]')), // Remove caracteres especiais, exceto @, . e -
                ],
                focusNode: focusNode,
                controller: textController,
                validator: (value) {
                  if (value!.isEmpty) {
                    return null;
                  }
                  if (!RegExp(r'^[\w-]+(\.[\w-]+)*@([\w-]+\.)+[a-zA-Z]{2,7}$')
                      .hasMatch(value)) {
                    return 'Por favor, insira um email válido.';
                  }
                  return null;
                },
                decoration: InputDecoration(
                  border: const OutlineInputBorder(),
                  fillColor: Colors.white,
                  filled: true,
                  labelText: 'Seu e-mail',
                  hintText: 'Seu e-mail',
                  suffixIcon: AnimatedBuilder(
                    animation: textController,
                    builder: (context, _) {
                      return IconButton(
                        onPressed: _sendEmailMessage,
                        icon: const Icon(Icons.send),
                      );
                    },
                  ),
                ),
              ),
            ),
          ),
          const Divider(),
          const SizedBox(height: 10.0),
          Text(
            telas[widget.id]!['body3'],
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          Image.asset(
            telas[widget.id]!['image'][0], //assets/arvore2.png
            alignment: Alignment.bottomCenter,
          ),
          const SizedBox(height: 10.0),
          Image.asset(
            telas[widget.id]!['image'][1], //assets/arvore2.png
            alignment: Alignment.bottomCenter,
          ),
        ],
      ),
    );
  }
}
