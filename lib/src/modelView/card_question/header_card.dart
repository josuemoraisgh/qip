import 'package:flutter/material.dart';

class HeaderCard extends StatefulWidget {
  final Widget? headerTitle;
  final Widget? widgetBody;
  const HeaderCard({
    Key? key,
    this.headerTitle,
    this.widgetBody,
  }) : super(key: key);

  @override
  State<HeaderCard> createState() => _HeaderCardState();
}

class _HeaderCardState extends State<HeaderCard> {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          //const SizedBox(height: 10),
          Card(
            color: Colors.green,
            elevation: 8,
            margin: const EdgeInsets.all(0.0),
            shape: const OutlineInputBorder(
                borderRadius: BorderRadius.only(
                    topLeft: Radius.circular(20),
                    topRight: Radius.circular(20)),
                borderSide: BorderSide(color: Colors.green)),
            child: Container(

              padding: const EdgeInsets.only(
                  left: 20, top: 10, right: 20, bottom: 10),
              width: MediaQuery.of(context).size.width,
              child: widget.headerTitle == null ? null : widget.headerTitle!,
            ),
          ),
          Card(
            color: Colors.white,
            elevation: 8,
            margin: const EdgeInsets.all(0.0),
            shape: const OutlineInputBorder(
                borderRadius: BorderRadius.only(
                    bottomLeft: Radius.circular(20),
                    bottomRight: Radius.circular(20)),
                borderSide: BorderSide(color: Colors.white)),
            child: Container(
              padding: const EdgeInsets.only(
                  left: 20, top: 10, right: 20, bottom: 20),
              width: MediaQuery.of(context).size.width,
              child: widget.widgetBody,
            ),
          )
        ],
      ),
    );
  }
}
