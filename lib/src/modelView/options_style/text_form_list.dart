import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';

class TextFormList extends StatefulWidget {
  final String? title;
  final List<String>? options;
  final List<String>? labelText;
  final int? optionsColumnsSize;
  final List<IconData>? icons;
  final Function(String) answerFunc;
  final List<TextInputType>? keyboardType;
  final List<List<TextInputFormatter>>? inputFormatters;
  final List<String? Function(String?)>? validator;
  const TextFormList({
    super.key,
    required this.answerFunc,
    this.optionsColumnsSize,
    this.title,
    this.options,
    this.labelText,
    this.icons,
    this.keyboardType,
    this.inputFormatters,
    this.validator,
  });

  @override
  State<TextFormList> createState() => _TextFormListState();
}

class _TextFormListState extends State<TextFormList> {
  late int tamanho;
  late List<String> answer;
  late List<TextEditingController> textEditingController;
  late final GlobalKey<FormState> _formKey;

  @override
  void initState() {
    _formKey = GlobalKey<FormState>();
    tamanho = widget.options?.length ?? (widget.labelText?.length ?? 1);
    answer = List.filled(tamanho, "");
    textEditingController = List.filled(tamanho, TextEditingController());
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      onChanged: () {
        if (_formKey.currentState!.validate()) {
          _formKey.currentState!.save();
          widget.answerFunc(answer.join(';'));
        } else {
          widget.answerFunc('');
        }
      },
      child: Container(
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
          child: MontaAlternativas(
            optionsColumnsSize: widget.optionsColumnsSize,
            length: tamanho,
            builder: (int id) => Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: ((widget.title?[id] ?? "") != ""
                        ? <Widget>[
                            const SizedBox(width: 15),
                            Center(
                              child: Text(
                                widget.title![id],
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
                      widget.options?[id] == null
                          ? _montaEdit(id)
                          : Row(
                              children: widget.options?[id][0] == "-"
                                  ? <Widget>[
                                      Flexible(flex: 20, child: _montaEdit(id)),
                                      const Flexible(
                                          flex: 3, child: SizedBox(width: 5)),
                                      Flexible(
                                          flex: 10, child: _montaTexto(id)),
                                    ]
                                  : <Widget>[
                                      Flexible(
                                          flex: 10, child: _montaTexto(id)),
                                      const Flexible(
                                          flex: 3, child: SizedBox(width: 5)),
                                      Expanded(flex: 20, child: _montaEdit(id)),
                                    ],
                            ),
                    ],
              ),
            ),
          ),
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

  Widget _montaTexto(int id) {
    return Container(
      alignment: Alignment.center,
      height: 50,
      width: 100,
      decoration: myContainerDecoration(),
      child: Text(
        widget.options?[id] ?? "",
        textAlign: TextAlign.center,
        style: const TextStyle(
            color: Colors.black, fontWeight: FontWeight.bold, fontSize: 18.0),
      ),
    );
  }

  Widget _montaEdit(int id) {
    return TextFormField(
      initialValue: answer[id],
      decoration: InputDecoration(
        border: const UnderlineInputBorder(),
        icon: widget.icons?[id] != null ? Icon(widget.icons![id]) : null,
        labelText: widget.labelText?[id],
      ),
      keyboardType: widget.keyboardType?[id],
      inputFormatters: widget.inputFormatters?[id],
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: (value) {
        final String? condicao = widget.validator?[id](value);
        if (condicao != null) {
          answer[id] = "";
          return condicao;
        }
        answer[id] = "$value - ${DateTime.now().toString()}";
        return null;
      },
    );
  }
}
