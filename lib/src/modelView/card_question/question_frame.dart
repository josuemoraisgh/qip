import 'package:flutter/material.dart';
import 'package:ia_triagem/src/modelView/options_style/text_form_list.dart';
import 'package:ia_triagem/src/modelView/options_style/dots_line.dart';
import '../options_style/multi_selection_list.dart';
import '../options_style/single_selection_list.dart';
import '../options_style/find_images.dart';
import '../options_style/five_errors.dart';

class QuestionFrame extends StatefulWidget {
  final Map<String, dynamic> item;
  final int? answerId;
  final dynamic Function(String, int) answerFunc;
  const QuestionFrame(
      {super.key, required this.item, required this.answerFunc, this.answerId});

  @override
  State<QuestionFrame> createState() => _QuestionFrameState();
}

class _QuestionFrameState extends State<QuestionFrame> {
  List<Offset> pointSelected = [];
  @override
  Widget build(BuildContext context) {
    return switch (widget.item['options_style'] ?? 'singleSelect') {
      'textForm' => TextFormList(
          optionsColumnsSize: widget.item['options_columns_size'],
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
          itens: widget.item,
        ),      
      'singleSelect' => SingleSelectionList(
          icon: widget.item['icon'],
          description: widget.item['title'],
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
          hasPrefiroNaoDizer: widget.item['hasPrefiroNaoDizer'] ?? false,
          itens: widget.item['options'],
          otherLabel: widget.item['otherLabel'],
          otherItem: widget.item['otherItem'],
          optionsColumnsSize: widget.item['options_columns_size'],
        ),
      'multiSelect' => MultiSelectionList(
          description: widget.item['title'],
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
          itens: widget.item['options'],
          optionsColumnsSize: widget.item['options_columns_size'],
          validator: (List<String>? value) {
            if (value == null) {
              return 'Por favor escolha um item';
            } else {
              final count = value.where((item) => item != "").length;
              if (count < widget.item['mim_size_awnser']) {
                return 'Por favor escolha um item';
              } else if (count > widget.item['max_size_awnser']) {
                return 'Por favor escolha um item';
              }
            }
            return (null);
          },
        ),        
      'dotLine' => DotsLine(
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
        ),
      'fiveErrors' => FiveErrors(
          imagemFull: widget.item['options'][0],
          imagemClean: widget.item['options'][1],
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
        ),
      'findImages' => FindImages(
          imagem: widget.item['options'][0],
          answerId: widget.answerId ?? 0,
          answerFunc: widget.answerFunc,
          pointSelected: pointSelected,
        ),
      _ => const Center(child: CircularProgressIndicator()), //Default value
    };
  }
}
