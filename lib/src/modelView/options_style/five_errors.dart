import 'package:flutter/material.dart';
import 'find_images.dart';

class FiveErrors extends StatefulWidget {
  final String imagemFull;
  final String imagemClean;
  final ValueNotifier<bool> isImagemFull;
  //final Function(String) answerFunc;
  final ValueNotifier<String> answer;
  const FiveErrors({
    super.key,
    required this.answer,
    //required this.answerFunc,
    required this.imagemFull,
    required this.imagemClean,
    required this.isImagemFull,
  });

  @override
  State<FiveErrors> createState() => _FiveErrorsState();
}

class _FiveErrorsState extends State<FiveErrors> {
  List<Offset> pointSelected = [];

  @override
  void initState() {
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SizedBox(
        width: MediaQuery.of(context).size.width,
        child: ValueListenableBuilder(
          valueListenable: widget.isImagemFull,
          builder: (context, isImagemFull, _) => AnimatedSwitcher(
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
                    child: Padding(
                      padding: const EdgeInsets.only(
                          left: 5, top: 5, right: 5, bottom: 5),
                      child: Image.asset(
                        widget.imagemFull, //assets/arvore2.png
                        alignment: Alignment.center,
                      ),
                    ),
                  )
                : FindImages(
                    imagem: widget.imagemClean,
                    answer: widget.answer,
                  ),
          ),
        ),
      ),
    );
  }
}
