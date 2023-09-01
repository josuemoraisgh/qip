import 'package:collection/collection.dart';
import 'package:flutter/material.dart';

class MontaAlternativas extends StatelessWidget {
  final int? optionsColumnsSize;
  final int length;
  final Widget Function(int index) builder;
  final List<Widget>? childList;
  const MontaAlternativas({
    Key? key,
    this.optionsColumnsSize,
    required this.length,
    required this.builder,
    this.childList,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    List<Widget> widgetListRow = [];
    for (int i = 0; i < length; i++) {
      widgetListRow.add(builder(i));
    }
    if (childList != null) {
      widgetListRow = widgetListRow + childList!;
    }
    widgetListRow = widgetListRow
        .slices(optionsColumnsSize ?? 1)
        .map<Widget>(
          (e) => Row(children: e),
        )
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: (widgetListRow),
    );
  }
}
