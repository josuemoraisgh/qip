import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_modular/flutter_modular.dart';

import '../../modules/home/telas_controller.dart';

class SendEmail extends StatefulWidget {
  final ValueNotifier<String> answer;
  const SendEmail({super.key, required this.answer});

  @override
  State<SendEmail> createState() => _SendEmailState();
}

class _SendEmailState extends State<SendEmail> {
  late TelasController controller;
  final _formKey = GlobalKey<FormState>();
  final textController = TextEditingController();
  final focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    controller = Modular.get<TelasController>();
    textController.text = widget.answer.value;
    textController.addListener(
      () {
        widget.answer.value = textController.text;
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
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
    );
  }

  _sendEmailMessage() {
    //Faça aqui o codigo Eviando a mensagem para o Email no textController.text;
    controller.storage.sendEmail(textController.text).whenComplete(() => "");
    textController.text = '';
    focusNode.requestFocus();
  }
}
