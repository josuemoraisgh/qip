import 'package:flutter/material.dart';

class DisplayFrame extends StatefulWidget {
  final int? id;
  final String? body;
  final bool? bodyHasFrame;
  final double? fontSize;
  final List<Widget>? widgets;
  final void Function()? isLoading;
  final void Function({required int id, required String fileName})? playMusic;
  const DisplayFrame({
    super.key,
    this.id,
    this.widgets,
    this.playMusic,
    this.body,
    this.bodyHasFrame,
    this.fontSize,
    this.isLoading,
  });

  @override
  State<DisplayFrame> createState() => _DisplayFrameState();
}

class _DisplayFrameState extends State<DisplayFrame> {
  bool isPlaying = false;

  @override
  void initState() {
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    final String body = widget.body ?? "";
    return Container(
      alignment: Alignment.center,
      decoration: widget.bodyHasFrame ?? true
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
      child: (body == "") && (widget.bodyHasFrame ?? true) // body_type = vazio
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
                                      widget.playMusic!(
                                          id: widget.id!,
                                          fileName: widget.body ?? "");
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
                  ? widget.bodyHasFrame ?? true
                      ? Padding(
                          padding: const EdgeInsets.only(
                              left: 5, top: 5, right: 5, bottom: 5),
                          child: Image.asset(
                            body, //assets/arvore2.png
                            //width: 400.0,
                            alignment: Alignment.center,
                            frameBuilder: (BuildContext context, Widget child,
                                int? frame, bool wasSynchronouslyLoaded) {
                              if (frame != null) {
                                if (widget.isLoading != null) widget.isLoading!();
                                return child;
                              }
                              return const CircularProgressIndicator();
                            },
                          ),
                        )
                      : Image.asset(
                          body, //assets/arvore2.png
                          alignment: Alignment.bottomCenter,
                          frameBuilder: (BuildContext context, Widget child,
                              int? frame, bool wasSynchronouslyLoaded) {
                            if (frame != null) {
                              if (widget.isLoading != null) widget.isLoading!();
                              return child;
                            }
                            return const CircularProgressIndicator();
                          },
                        )
                  : widget.bodyHasFrame ?? true // body_type = texto
                      ? Text(
                          body,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: widget.fontSize ?? 100,
                            color: Colors.black,
                            fontWeight: FontWeight.w500,
                          ),
                        )
                      : body.isNotEmpty
                          ? Text(
                              body,
                              textAlign: TextAlign.justify,
                              style: TextStyle(
                                  fontSize: widget.fontSize ?? 15.0,
                                  color: Colors.black,
                                  decorationColor: Colors.black),
                            )
                          : null,
    );
  }
}
