import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/base_widget/monta_alternativas.dart';

class TextFormList extends StatefulWidget {
  final Map<String, dynamic> itens;
  final int? optionsColumnsSize;
  final Function(String, int) answerFunc;
  final int? answerId;
  const TextFormList(
      {super.key,
      required this.answerFunc,
      required this.itens,
      this.optionsColumnsSize,
      this.answerId});

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
    tamanho = widget.itens['options']?.length ??
        (widget.itens['labelText']?.length ?? 1);
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
          widget.answerFunc(answer.join(';'), widget.answerId ?? 0);
        } else {
          widget.answerFunc('', widget.answerId ?? 0);
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
                children: ((widget.itens['title']?[id] ?? "") != ""
                        ? <Widget>[
                            const SizedBox(width: 15),
                            Center(
                              child: Text(
                                widget.itens['title']![id],
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
                      widget.itens['options']?[id] == null
                          ? _montaEdit(id)
                          :  Row(
                                children: widget.itens['options']?[id][0] == "-"
                                    ? <Widget>[
                                        Flexible(flex: 20, child: _montaEdit(id)),
                                        const Flexible(flex: 3, child: SizedBox(width: 5)),
                                        Flexible(flex: 10, child:_montaTexto(id)),
                                      ]
                                    : <Widget>[
                                        Flexible(flex: 10, child:_montaTexto(id)),                                        
                                        const Flexible(flex: 3, child: SizedBox(width: 5)),
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
        widget.itens['options']?[id] ?? "",
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
        icon: widget.itens['icons']?[id] != null
            ? Icon(widget.itens['icons']![id])
            : null,
        labelText: widget.itens['labelText']?[id],
      ),
      keyboardType: widget.itens['keyboardType']?[id],
      inputFormatters: widget.itens['inputFormatters']?[id],
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: (value) {
        final String? condicao = widget.itens['validator']?[id](value);
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
