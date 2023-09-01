import 'package:flutter/material.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'package:just_audio/just_audio.dart';
import '../card_question/card_question_page.dart';
import '../../modules/home/parameters.dart';

class TypeForm extends StatefulWidget {
  final int id;
  final ValueNotifier<List<String>> answer;
  const TypeForm({Key? key, required this.id, required this.answer})
      : super(key: key);

  @override
  State<TypeForm> createState() => _TypeFormState();
}

class _TypeFormState extends State<TypeForm> {
  var player = AudioPlayer();

  @override
  void initState() {
    super.initState();
    if (telas[widget.id]!['delay'] != null) {
      Future.delayed(Duration(seconds: telas[widget.id]!['delay']!))
          .then((value) {
        setState(() {
          if (telas[widget.id]!['hasProx']) {
            widget.answer.value = ['Sucess'];
          } else {
            Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
          }
        });
      });
    }
  }

  void playMusic(String fileName) async {
    if (fileName != '.mp3') {
      try {
        await player.setAudioSource(
          AudioSource.uri(Uri.parse("asset:///$fileName")),
          initialPosition: Duration.zero,
          preload: true,
        );
        //await player.setAsset(path); //load audio from assets
        player.play().then((value) {
          setState(() {
            Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
          });
        });
      } catch (e) {
        debugPrint("Error loading audio source: $e");
      }
    } else {
      Future.delayed(const Duration(seconds: 3)).then((value) {
        setState(() {
          Modular.to.popAndPushNamed("/", arguments: widget.id + 1);
        });
      });
    }
  }

  @override
  void dispose() {
    player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CardQuestionPage(
        answer: widget.answer,
        header: (telas[widget.id]!['header'] ?? "") != ""
            ? telas[widget.id]!['header']
            : null,
        body: telas[widget.id]!['itens'],
        playMusic: playMusic);
  }
}
