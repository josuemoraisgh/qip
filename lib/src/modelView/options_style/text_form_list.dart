import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class TextFormList extends StatefulWidget {
  final String? title;
  final String? options;
  final String? labelText;
  final int? optionsColumnsSize;
  final IconData? icon;
  //final void Function(String)? answerFunc;
  final ValueNotifier<String> answer;
  final TextInputType? keyboardType;
  final List<TextInputFormatter>? inputFormatters;
  final String? Function(String?)? validator;
  const TextFormList({
    super.key,
    //required this.answerFunc,
    this.optionsColumnsSize,
    this.title,
    this.options,
    this.labelText,
    this.icon,
    this.keyboardType,
    this.inputFormatters,
    this.validator,
    required this.answer,
  });

  @override
  State<TextFormList> createState() => _TextFormListState();
}

class _TextFormListState extends State<TextFormList> {
  final textController = TextEditingController();
  final focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    textController.text = widget.answer.value;
    textController.addListener(
      () {
        if (textController.value.selection.isValid) {
          widget.answer.value = textController.text;
        }
      },
    );
    focusNode.addListener(
      () {
        widget.answer.value = textController.text;
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8.0),
        border: Border.all(width: 0.2, color: Colors.black),
        color: Colors.white,
        boxShadow: const [
          BoxShadow(
            color: Colors.black,
            blurRadius: 2.0,
            spreadRadius: 0.0,
            offset: Offset(2.0, 2.0), // shadow direction: bottom right
          )
        ],
      ),
      child: Padding(
        padding:
            const EdgeInsets.only(left: 10, top: 10, right: 10, bottom: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: ((widget.title ?? "") != ""
                  ? <Widget>[
                      const SizedBox(width: 15),
                      Center(
                        child: Text(
                          widget.title!,
                          textAlign: TextAlign.justify,
                          style: const TextStyle(
                              fontSize: 35,
                              color: Colors.black,
                              decorationColor: Colors.black),
                        ),
                      ),
                    ]
                  : <Widget>[]) +
              <Widget>[
                const SizedBox(height: 15),
                widget.options == null
                    ? _montaEdit()
                    : SafeArea(
                        child: Row(
                          children: widget.options?[0] == "-"
                              ? <Widget>[
                                  Flexible(flex: 60, child: _montaEdit()),
                                  const Flexible(
                                      flex: 5, child: SizedBox(width: 5)),
                                  Flexible(flex: 35, child: _montaTexto()),
                                ]
                              : <Widget>[
                                  Flexible(flex: 35, child: _montaTexto()),
                                  const Flexible(
                                      flex: 5, child: SizedBox(width: 5)),
                                  Expanded(flex: 60, child: _montaEdit()),
                                ],
                        ),
                      ),
              ],
        ),
      ),
    );
  }

  BoxDecoration myContainerDecoration() {
    return BoxDecoration(
      border: Border.all(width: 3.0, color: Colors.redAccent),
      color: Colors.white70,
    );
  }

  Widget _montaTexto() {
    return Container(
      alignment: Alignment.center,
      height: 50,
      //width: 500,
      decoration: myContainerDecoration(),
      child: Text(
        widget.options ?? "",
        textAlign: TextAlign.center,
        style: const TextStyle(
            color: Colors.black, fontWeight: FontWeight.bold, fontSize: 18.0),
      ),
    );
  }

  Widget _montaEdit() {
    return TextFormField(
      //initialValue: answer,
      controller: textController,
      focusNode: focusNode,
      decoration: InputDecoration(
        border: const UnderlineInputBorder(),
        icon: widget.icon != null ? Icon(widget.icon!) : null,
        labelText: widget.labelText,
      ),
      keyboardType: widget.keyboardType,
      inputFormatters: widget.inputFormatters,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: widget.validator,
    );
  }
}
