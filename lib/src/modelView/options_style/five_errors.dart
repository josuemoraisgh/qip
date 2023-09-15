import 'package:flutter/material.dart';
import 'find_images.dart';

class FiveErrors extends StatefulWidget {
  final String imagemFull;
  final String imagemClean;
  //final Function(String) answerFunc;
  final ValueNotifier<String> answer;
  final int? answerId;
  const FiveErrors({
    Key? key,
    required this.answer,
    //required this.answerFunc,
    this.answerId,
    required this.imagemFull,
    required this.imagemClean,
  }) : super(key: key);

  @override
  State<FiveErrors> createState() => _FiveErrorsState();
}

class _FiveErrorsState extends State<FiveErrors> {
  bool isImagemFull = true;
  List<Offset> pointSelected = [];

  @override
  void initState() {
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AppBar(
          leading: IconButton(
            icon: Icon(
              isImagemFull == true
                  ? Icons.comment_sharp
                  : Icons.comments_disabled,
              color: Colors.white,
            ),
            onPressed: () {
              setState(() {
                isImagemFull == true
                    ? isImagemFull = false
                    : isImagemFull = true;
              });
            },
          ),
        ),
        Center(
          child: SizedBox(
            width: MediaQuery.of(context).size.width,
            child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 1000),
                transitionBuilder: (Widget child, Animation<double> animation) {
                  const begin = Offset(6.0, 0.0);
                  const end = Offset.zero;
                  const curve = Curves.ease;

                  final tween = Tween(begin: begin, end: end);
                  final curvedAnimation = CurvedAnimation(
                    parent: animation,
                    curve: curve,
                  );
                  return SlideTransition(
                      position: tween.animate(curvedAnimation), child: child);
                },
                child: isImagemFull == true
                    ? Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(4.0),
                          border: Border.all(width: 0.2, color: Colors.black),
                          color: Colors.white,
                          boxShadow: const [
                            BoxShadow(
                              color: Colors.black,
                              blurRadius: 4.0,
                              spreadRadius: 0.0,
                              offset: Offset(
                                  3.0, 3.0), // shadow direction: bottom right
                            )
                          ],
                        ),
                        child: Image.asset(
                          key: const ValueKey<int>(0),
                          widget.imagemFull, //assets/arvore2.png
                          alignment: Alignment.center,
                        ),
                      )
                    : FindImages(
                        key: const ValueKey<int>(1),
                        imagem: widget.imagemClean,
                        answerId: widget.answerId ?? 0,
                        answer: widget.answer,
                        //answerFunc: widget.answerFunc,
                      )),
          ),
        ),
      ],
    );
  }
}
