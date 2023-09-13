import 'package:flutter/material.dart';

class DisplayFrame extends StatefulWidget {
  final Map<String, dynamic> item;
  final List<Widget>? widgets;
  final void Function(String audio)? playMusic;
  const DisplayFrame(
      {super.key, required this.item, this.widgets, this.playMusic});

  @override
  State<DisplayFrame> createState() => _DisplayFrameState();
}

class _DisplayFrameState extends State<DisplayFrame> {
  bool isPlaying = false;

  @override
  Widget build(BuildContext context) {
    final String body = widget.item['body'] ?? "";
    return Container(
      alignment: Alignment.center,
      decoration: widget.item['body_hasFrame'] ?? true
          ? BoxDecoration(
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
            )
          : null,
      child: (body == "") &&
              (widget.item['body_hasFrame'] ?? true) // body_type = vazio
          ? const SizedBox(
              height: 300.0,
              width: 400.0,
            )
          : body.contains('.mp3') // body_type = audio
              ? SizedBox(
                  height: 300.0,
                  width: 400.0,
                  child: Container(
                    alignment: Alignment.center,
                    margin: const EdgeInsets.only(top: 20),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: !isPlaying
                          ? <Widget>[
                              IconButton(
                                  iconSize: 64,
                                  icon: const Icon(Icons.play_arrow),
                                  onPressed: () async {
                                    if (widget.playMusic != null) {
                                      widget.playMusic!(widget.item['body']);
                                    }
                                    setState(() {
                                      isPlaying = true;
                                    });
                                  }),
                              const Text("Clique para iniciar o Audio"),
                            ]
                          : const <Widget>[
                              CircularProgressIndicator(),
                              SizedBox(height: 10),
                              Text("Tocando o audio!!"),
                            ],
                    ),
                  ),
                )
              : body.contains('.png') // body_type = image
                  ? widget.item['body_hasFrame'] ?? true
                      ? Image.asset(
                          body, //assets/arvore2.png
                          //height: 300.0,
                          width: 400.0,
                          alignment: Alignment.center,
                        )
                      : Image.asset(
                          body, //assets/arvore2.png
                          alignment: Alignment.bottomCenter,
                        )
                  : widget.item['body_hasFrame'] ?? true // body_type = texto
                      ? Text(
                          body,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 100.0,
                            color: Colors.black,
                            fontWeight: FontWeight.w500,
                          ),
                        )
                      : body.isNotEmpty
                          ? Text(
                              body,
                              textAlign: TextAlign.justify,
                              style: const TextStyle(
                                  fontSize: 15.0,
                                  color: Colors.black,
                                  decorationColor: Colors.black),
                            )
                          : null,
    );
  }
}
