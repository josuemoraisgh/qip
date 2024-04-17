  
  import 'package:web/web.dart';

  class AudioWeb {
  final audioContext = AudioContext();
  //AudioGainNode gainNode = audioContext.createGainNode();
/*
  play(File audioData){
    // asynchronous decoding
    audioContext.decodeAudioData(audioData.arrayBuffer(), (buffer) {
      playSound() {
        AudioBufferSourceNode source = audioContext.createBufferSource();
        source.connect(gainNode, 0, 0);
        source.buffer = buffer;
        source.noteOn(0);
      }


      var button = document.query("#play");
      button.disabled = false;
      button.on.click.add((_) {
        playSound();
      });
    }, (error) {
      print('Error decoding MP3 file');
    });


  });  


  xhr.send();


  document.query("#volume").on.change.add((e) {
    var volume = Math.parseInt(e.target.value);
    var max = Math.parseInt(e.target.max);
    var fraction = volume / max;
    gainNode.gain.value = fraction * fraction;
  });

*/
}