import 'package:brasil_fields/brasil_fields.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_modular/flutter_modular.dart';
import 'package:qip_triagem/src/modelView/options_style/muro_colorido.dart';
import '/src/modelView/options_style/display_frame.dart';
import '/src/modelView/options_style/multi_selection_list.dart';

import '../../modelView/options_style/arvore_circulos.dart';
import '../../modelView/options_style/dots_line.dart';
import '../../modelView/options_style/find_images.dart';
import '../../modelView/options_style/five_errors.dart';
import '../../modelView/options_style/send_email.dart';
import '../../modelView/options_style/single_selection_list.dart';
import '../../modelView/options_style/text_form_list.dart';
import '../../modelView/options_style/yes_no.dart';
import 'telas_controller.dart';

void addListenerSimples(
  TelasController controller,
  GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
) {
  state.currentState!.didChange(controller.answerAux.value);
}

void addListenerComposto(
  TelasController controller,
  GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
  int i1,
  int i2,
) {
  if (controller.answerAux.value[i1].value == 'other') {
    if (controller.answerAux.value[i2].value == 'Sucess') {
      controller.answerAux.value[i2].value = '';
    }
  } else {
    if (controller.answerAux.value[i2].value == '') {
      controller.answerAux.value[i2].value = 'Sucess';
    }
  }
  state.currentState!.didChange(controller.answerAux.value);
}

Map<int, Map<String, dynamic>> telas = {
  1: {
    'hasProx': true,
    'header': "Questionário Interativo Psicopatológico (QIP)",
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const Text(
            """

TERMO DE CONSENTIMENTO LIVRE E ESCLARECIDO

  
Você está sendo convidado(a) a participar da pesquisa intitulada “Sistematização de ferramentas para Avaliação Psicopatológica utilizando técnica de Inteligência Artificial”, sob a responsabilidade dos pesquisadores Prof. Dr. Keiji Yamanaka, Ms. Résia da Silva Morais (da Faculdade de Engenharia Elétrica da Universidade Federal de Uberlândia). Nesta pesquisa nós estamos buscando confirmar a possibilidade de usar técnicas de Inteligência artificial para avaliar as estruturas de saúde mental chamadas de Funções Mentais Psíquicas (atenção, consciência, orientação, experiências de tempo e de espaço, sensopercepção, memória, afetividade, vontade e psicomotricidade, pensamento, juízos de realidade, linguagem, Inteligência e cognição social), essenciais para uma excelente avaliação psicopatológica com o objetivo de ajudar os profissionais da área da saúde mental. 
O Termo/Registro de Consentimento Livre e Esclarecido está sendo obtido pelos pesquisadores Dr. Keiji Yamanaka e Ms. Résia da Silva Morais, antecedendo toda e qualquer experimentação que envolva a pesquisa. Conforme o item IV da Resol. CNS 466/12 ou Cap. III da Resol. 510/2016, o participante terá o tempo que julgar necessário para decidir se deseja participar da pesquisa. Se você tiver qualquer dúvida em relação à pesquisa, você pode entrar em contato com o(a) pesquisador(a) pelo e-mail duvidaspsicopatologiacomia@gmail.com para discutir as informações do estudo
Na sua participação, após você ter compreendido as informações que constituem o Termo de Consentimento Livre e Esclarecido e após ter assinado eletronicamente o campo no qual “Concorda” participar da pesquisa, serão apresentadas telas com as instruções das tarefas que você irá responder. Certifique-se que esteja em um ambiente silencioso, sem estímulos de distração. Em algumas telas serão apresentados sons, sendo assim, fundamental o uso de fones ou que você ligue os alto-falantes do seu dispositivo. A avaliação das Funções Psíquicas será através de 45 testes apresentados através de 66 telas e você gastará em torno de 25 minutos. Em algumas questões, será solicitado que você ouça primeiramente alguns sons para respondê-las, e cada tela apresentada pelo questionário interativo permitirá a identificação da relação entre as respostas dadas por você e sinais de possíveis funções mentais afetadas.
As respostas serão coletadas e registradas por meio da plataforma do Google Forms e do sistema TensorFlow que agrupará os dados possibilitando a análise das ferramentas de avaliação psicopatológica. O pesquisador responsável atenderá as orientações das Resoluções nº 466/2012, Capítulo XI, Item Xl.2: f e nº 510/2016, Capítulo VI, Art. 28: IV; e manterá os dados da pesquisa em arquivo, físico ou digital, sob sua guarda e responsabilidade, por um período mínimo de 5 (cinco) anos após o término da pesquisa. Uma vez concluída a coleta de dados, o pesquisador responsável irá fazer o download dos dados coletados para um dispositivo eletrônico local, apagando todo e qualquer registro de qualquer plataforma virtual, ambiente compartilhado ou "nuvem". Em nenhum momento você será identificado. Os resultados da pesquisa serão publicados e ainda assim a sua identidade será preservada.
Você não terá nenhum gasto e nem ganho financeiro por participar na pesquisa. Você não receberá pagamentos por ser participante.  Todas as informações obtidas por meio de sua participação serão de uso exclusivo para esta pesquisa e ficarão sob a guarda do/da pesquisador/a responsável. Havendo algum dano decorrente da pesquisa, você terá direito a solicitar indenização através das vias judiciais (Código Civil, Lei 10.406/2002, Artigos 927 a 954 e Resolução CNS nº 510 de 2016, Artigo 19).
Os riscos consistem em possibilidade de cansaço durante a realização da prova e algum desconforto relacionado a utilização dos testes. Para minimizar os riscos o instrumento de coleta de dados será respondido de forma virtual e anônima. Os pesquisadores se comprometem a tomar medidas de proteção e confidencialidade dos dados para que o sigilo da sua identidade seja preservado. Na possibilidade de ocorrer algum desconforto emocional durante a realização da prova, fique à vontade para entrar em contato pelo e-mail duvidaspsicopatologiacomia@gmail.com, e será acolhido pelo pesquisador assistente (Psicólogo Clínico). Caso o pesquisador identificar necessidade de continuidade da assistência, de forma virtual, você receberá orientações psicoterapêuticas breve e será encaminhado (a) para atendimento psicológico na rede pública mais próxima da sua residência. Os benefícios serão a expansão do seu conhecimento sobre a importância da Inteligência artificial como um meio auxiliar no processo de avaliação psicológica, o que pode facilitar o trabalho clínico interventivo dos profissionais da saúde mental. Os dados da pesquisa serão mantidos em arquivo, físico e digital, sob sua guarda e responsabilidade, por um período mínimo de 5 (cinco) anos após o término da pesquisa, conforme capítulo VI da resolução CNS 510, de 07 de abril de 2016. 
Você é livre para deixar de participar da pesquisa a qualquer momento sem qualquer prejuízo ou coação. Até o momento da divulgação dos resultados, você também é livre para solicitar a retirada dos seus dados da pesquisa. Uma via original deste Termo de Consentimento Livre e Esclarecido ficará com você, você poderá salvar em seu dispositivo eletrônico. Em caso de qualquer dúvida ou reclamação a respeito da pesquisa, você poderá entrar em contato com: Dr. Keiji Yamanaka, Faculdade de Engenharia Elétrica da Universidade Federal de Uberlândia. Av. João Naves de Ávila, 2121 Campus Santa Mônica - Universidade Federal de Uberlândia CEP 38400-902 - Uberlândia MG - Brasil - Fone (sala coordenação): (34) 3239-4706, ou com a Pesquisadora Psicóloga Ms. Résia Silva de Morais, Faculdade de Engenharia Elétrica da Universidade Federal de Uberlândia. Av. João Naves de Ávila, 2121Campus Santa Mônica - Universidade Federal de Uberlândia, CEP 38400-902 - Uberlândia MG - Brasil – e-mail: duvidaspsicopatologiacomia@gmail.com. Para obter orientações quanto aos direitos dos participantes de pesquisa acesse a cartilha no link:https://conselho.saude.gov.br/images/comissoes/conep/documentos/Cartilha_Direitos_Eticos_2020.pdf.
Você poderá também entrar em contato com o CEP - Comitê de Ética na Pesquisa com Seres Humanos na Universidade Federal de Uberlândia, localizado na Av. João Naves de Ávila, nº 2121, bloco A, sala 224, campus Santa Mônica – Uberlândia/MG, 38408-100; telefone: 34-3239-4131 ou pelo e-mail: cep@propp.ufu.br. O CEP é um colegiado independente criado para defender os interesses dos participantes das pesquisas em sua integridade e dignidade e para contribuir para o desenvolvimento da pesquisa dentro de padrões éticos conforme resoluções do Conselho Nacional de Saúde.
Ao assinalar a opção “Concordo”, a seguir, você declara que aceita participar do projeto citado acima, voluntariamente, após ter sido devidamente esclarecido, pelos pesquisadores; que entendeu como é a pesquisa, que pode solicitar esclarecimentos em relação as dúvidas com o/a pesquisador/a via e-mail (duvidaspsicopatologiacomia@gmail.com); e que pode desistir em qualquer momento, durante e depois de participar; você autoriza a divulgação dos dados obtidos neste estudo mantendo em sigilo sua identidade. 
""",
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(
                () {
                  if (controller.answerAux.value[0].value == 'Concordo') {
                    state.currentState!.didChange(controller.answerAux.value);
                  } else {
                    state.currentState!.didChange([]);
                  }
                },
              ),
            hasPrefiroNaoDizer: false,
            options: const ['Concordo', 'Não concordo'],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Text(
            """
Solicitamos que você salve este documento em seus arquivos. Se desejar receber uma cópia deste registro de consentimento por e-mail, por favor, preencha-o abaixo e clique no botão de enviar:
""",
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          SendEmail(answer: controller.emailAux),
          const Divider(),
          const SizedBox(height: 10.0),
          const Text(
            """

  DECLARAÇÃO DOS PESQUISADORES

Declaramos que obtivemos de forma apropriada e voluntária, o Consentimento Livre e Esclarecido deste participante para a participação neste estudo. Declaramos ainda que nos comprometemos a cumprir todos os termos aqui descritos;
""",
            textAlign: TextAlign.justify,
          ),
          const SizedBox(height: 10.0),
          Image.asset(
            'assets/assinatura_keiji.png',
            alignment: Alignment.bottomCenter,
          ),
          const SizedBox(height: 10.0),
          Image.asset(
            'assets/assinatura_resia.png',
            alignment: Alignment.bottomCenter,
          ),
        ],
  },
  2: {
    'hasProx': true,
    'header': 'Questionário Sociodemográfico',
    'answerLenght': 19,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TextFormList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            labelText: 'Que horas são neste instante?',
            validator: (value) {
              if (value == null) {
                return 'Horário Inválido!!';
              } else if ((value.isEmpty) || (value.length != 5)) {
                return 'Horário Inválido!!';
              }
              return null;
            },
            icon: Icons.lock_clock,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              HoraInputFormatter()
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            labelText: 'Data de hoje?',
            validator: (value) {
              if (value == null) {
                return 'Data atual Incorreta!!';
              } else if ((value.isEmpty) || (value.length != 10)) {
                return 'Data atual Incorreta!!';
              }
              return null;
            },
            icon: Icons.date_range,
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              DataInputFormatter()
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
              answer: controller.answerAux.value[2]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              labelText: 'Qual a sua Idade?',
              icon: Icons.cake,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (String? value) {
                if ((value == null) ||
                    (value.isEmpty) ||
                    (int.parse(value) <= 0) ||
                    (int.parse(value) >= 130)) {
                  return 'Idade invalida!! Corrija por favor';
                }
                return null;
              }),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[3]
              ..addListener(() => addListenerComposto(controller, state, 3, 4)),
            title: 'Gênero *',
            icon: Icons.transgender,
            hasPrefiroNaoDizer: true,
            options: const ["Feminino", "Masculino"],
            optionsColumnsSize: 2,
            otherItem: TextFormList(
              answer: controller.answerAux.value[4]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              labelText: "Qual o seu gênero?",
              keyboardType: TextInputType.name,
              inputFormatters: [
                FilteringTextInputFormatter.singleLineFormatter
              ],
              validator: (String? value) {
                if (value == null) {
                  return 'Descrição invalida!! Corrija por favor';
                } else if ((value.isEmpty) || (value.length < 3)) {
                  return 'Descrição invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[5]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'Qual foi o sexo atribuído no seu nascimento?',
            icon: Icons.wc,
            hasPrefiroNaoDizer: false,
            options: const ["Feminino", "Masculino"],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[6]
              ..addListener(() => addListenerComposto(controller, state, 6, 7)),
            title: "Assinale a alternativa que identifica a sua Cor ou Raça:",
            icon: Icons.person,
            hasPrefiroNaoDizer: true,
            options: const ["Preta", "Branca", "Parda", "Amarela", "IndÍgena"],
            optionsColumnsSize: 2,
            otherItem: TextFormList(
              answer: controller.answerAux.value[7]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              keyboardType: TextInputType.name,
              labelText: "Qual a sua Cor ou Raça ?",
              inputFormatters: [
                FilteringTextInputFormatter.singleLineFormatter
              ],
              validator: (value) {
                if (value == null) {
                  return 'Descrição invalida!! Corrija por favor';
                } else if ((value.isEmpty) || (value.length < 3)) {
                  return 'Descrição invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[8]
              ..addListener(() => addListenerComposto(controller, state, 8, 9)),
            title: "Dentro de sua família, você é o(a) único(a) filho(a)?",
            icon: Icons.diversity_3,
            hasPrefiroNaoDizer: false,
            options: const ["Sim"],
            optionsColumnsSize: 2,
            otherLabel: "Não",
            otherItem: TextFormList(
              answer: controller.answerAux.value[9]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              labelText: "Quantos irmãos você tem?",
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (value) {
                if (value == null) {
                  return 'Quantidade invalida!! Corrija por favor';
                } else if ((value.isEmpty)) {
                  return 'Quantidade invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[10]
              ..addListener(
                  () => addListenerComposto(controller, state, 10, 11)),
            title: "Qual o seu estado civil?",
            icon: Icons.diversity_2,
            hasPrefiroNaoDizer: false,
            optionsColumnsSize: 2,
            options: const [
              "Solteiro (a):",
              "Casado (a)",
              "Viúvo (a)",
              "Divorciado(a)",
              "Amaziado",
            ],
            otherItem: TextFormList(
              answer: controller.answerAux.value[11]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              labelText: "Qual estado civil ?",
              keyboardType: TextInputType.name,
              inputFormatters: [
                FilteringTextInputFormatter.singleLineFormatter
              ],
              validator: (value) {
                if (value == null) {
                  return 'Descrição invalida!! Corrija por favor';
                } else if ((value.isEmpty) || (value.length < 3)) {
                  return 'Descrição invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[12]
              ..addListener(
                  () => addListenerComposto(controller, state, 12, 13)),
            title: "Possui filhos(as)?",
            icon: Icons.group_add,
            hasPrefiroNaoDizer: false,
            optionsColumnsSize: 2,
            options: const ["Não"],
            otherLabel: "Sim",
            otherItem: TextFormList(
              answer: controller.answerAux.value[13]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              labelText: "Quantos filhos você tem?",
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              validator: (value) {
                if (value == null) {
                  return 'Quantidade invalida!! Corrija por favor';
                } else if ((value.isEmpty)) {
                  return 'Quantidade invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[14]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: "Possui filhos(as) menores de 6 anos?",
            icon: Icons.child_friendly,
            hasPrefiroNaoDizer: false,
            optionsColumnsSize: 2,
            options: const ["Não", "Sim"],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[15]
              ..addListener(
                  () => addListenerComposto(controller, state, 15, 16)),
            title: "Religião *",
            icon: Icons.church,
            hasPrefiroNaoDizer: false,
            optionsColumnsSize: 2,
            options: const ["Sem religião"],
            otherLabel: "Tenho religião",
            otherItem: TextFormList(
                answer: controller.answerAux.value[16]
                  ..addListener(() => state.currentState!
                      .didChange(controller.answerAux.value)),
                labelText: "Qual é a Religião?",
                keyboardType: TextInputType.name,
                inputFormatters: [
                  FilteringTextInputFormatter.singleLineFormatter
                ],
                validator: (value) {
                  if (value == null) {
                    return 'Religião invalida!! Corrija por favor';
                  } else if ((value.isEmpty)) {
                    return 'Religião invalida!! Corrija por favor';
                  }
                  return null;
                }),
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[17]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: "Escolaridade *",
            icon: Icons.school,
            hasPrefiroNaoDizer: false,
            options: const [
              "Sem Escolaridade",
              "Ensino Fundamental (1º grau) incompleto",
              "Ensino Fundamental (1º grau) completo",
              "Ensino Médio (2º grau) incompleto",
              "Ensino Médio (2º grau) completo",
              "Superior Incompleto",
              "Superior Completo",
              "Mestrado",
              "Doutorado",
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[18]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: "Renda familiar mensal de sua casa (somatória)",
            icon: Icons.attach_money,
            hasPrefiroNaoDizer: false,
            options: const [
              "Até 1 salário mínimo",
              "Mais de 1 a 2 salários mínimos",
              "Mais de 2 a 3 salários mínimos",
              "Mais de 3 a 5 salários mínimos",
              "Mais de 5 a 8 salários mínimos",
              "Mais de 8 a 12 salários mínimos",
              "Mais de 12 a 20 salários mínimos",
              "Mais de 20 salários mínimos",
            ],
          ),
        ],
  },
  3: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 3,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() => addListenerComposto(controller, state, 0, 1)),
            title:
                'Você possui algum diagnóstico em relação ao seu estado de saúde mental, laudado por um profissional da saúde?',
            optionsColumnsSize: 2,
            hasPrefiroNaoDizer: false,
            options: const ["Não"],
            otherLabel: "Sim",
            otherItem: SingleSelectionList(
              answer: controller.answerAux.value[1]
                ..addListener(
                    () => addListenerComposto(controller, state, 1, 2)),
              title:
                  "\nCaso afirmativo, selecione o diagnóstico\n correspondente.",
              icon: Icons.admin_panel_settings,
              hasPrefiroNaoDizer: false,
              options: const [
                "Transtorno do Espectro Autista",
                "Transtornos Depressivos",
                "Transtorno Ciclotímico",
                "Transtornos de Ansiedade",
                "Transtorno de Estresse Pós-traumático",
                "Transtornos Alimentares",
                "Transtorno Bipolar",
                "Transtorno Obsessivo-compulsivo",
                "Transtorno de Déficit de Atenção/Hiperatividade",
                "Transtorno da Personalidade Borderline",
                "Transtorno do Espectro da Esquizofrenia e Outros Transtornos Psicóticos",
              ],
              otherLabel: "Outro tipo de transtorno",
              otherItem: TextFormList(
                answer: controller.answerAux.value[2]
                  ..addListener(() => state.currentState!
                      .didChange(controller.answerAux.value)),
                labelText:
                    'Digite a denominação desse outro tipo de transtorno',
                keyboardType: TextInputType.name,
                inputFormatters: [
                  FilteringTextInputFormatter.singleLineFormatter
                ],                
                validator: (value) {
                  if (value == null) {
                    return 'Digite a denominação desse outro tipo de transtorno';
                  } else if (value.length < 4) {
                    return 'Digite a denominação desse outro tipo de transtorno';
                  }
                  return null;
                },
              ),
            ),
          ),
        ],
  },
  4: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                'A partir de agora serão apresentadas telas com as instruções das tarefas que você irá responder.\r\n\nCertifique-se que esteja em um ambiente silencioso, sem estímulos de distração.\f\n\nEm algumas telas, sons serão reproduzidos; portanto, é fundamental usar fones de ouvido ou ligar os alto-falantes do seu dispositivo.',
            bodyHasFrame: false,
          ),
        ]
  },
  5: {
    'hasProx': true,
    'header': 'Informações',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body: 'Olhe atentamente para a figura apresentada na proxima tela.',
            bodyHasFrame: false,
          ),
        ]
  },
  6: {
    'hasProx': false,
    'header': 'Observe',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/arvore_free.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  7: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'O que você viu na tela anterior?',
            icon: Icons.question_answer,
            hasPrefiroNaoDizer: false,
            options: const [
              "Jesus Cristo",
              "Coração",
              "Dragão cuspindo fogo",
              "Árvore",
              "Não vi nada",
              "Outra coisa",
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  8: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body: 'Olhe atentamente para a figura apresentada na proxima tela.',
            bodyHasFrame: false,
          ),
        ]
  },
  9: {
    'hasProx': false,
    'header': 'Observe',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '',
            bodyHasFrame: true,
          ),
        ]
  },
  10: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'O que você viu na tela anterior?',
            icon: Icons.timelapse,
            hasPrefiroNaoDizer: false,
            options: const [
              "Jesus Cristo",
              "Coração",
              "Dragão cuspindo fogo",
              "Árvore",
              "Não vi nada",
              "Outra coisa",
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  11: {
    'hasProx': true,
    'header': 'Informações',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Nas próximas telas, serão apresentadas algumas sequências de números, após visualizá-las você deverá marcar a resposta que corresponde à sequência correta.",
            bodyHasFrame: false,
          ),
        ]
  },
  12: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '2 - 7',
            bodyHasFrame: true,
          ),
        ]
  },
  13: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.timeline,
            hasPrefiroNaoDizer: false,
            options: const [
              "1 - 5",
              "4 - 7",
              "2 - 7",
              "2 - 8",
              "9 - 4",
              "7 - 2"
            ],
            optionsColumnsSize: 3,
          ),
        ]
  },
  14: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '5 - 6 - 4',
            bodyHasFrame: true,
          ),
        ]
  },
  15: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              "5 - 7 - 1",
              "1 - 3 - 4",
              "5 - 6 - 3",
              "4 - 6 - 5",
              "5 - 4 - 6",
              "5 - 6 - 4"
            ],
            optionsColumnsSize: 3,
          ),
        ]
  },
  16: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '6 - 4 - 3 - 9',
            bodyHasFrame: true,
          ),
        ]
  },
  17: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              "6 - 4 - 9 - 3",
              "4 - 8 - 9 - 1",
              "6 - 4 - 3 - 9",
              "5 - 4 - 3 - 8",
              "1 - 5 - 2 - 9",
              "6 - 4 - 3 - 7"
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  18: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '4 - 2 - 7 - 3 - 1',
            bodyHasFrame: true,
          ),
        ]
  },
  19: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              "2 - 1 - 4 - 7 - 9",
              "4 - 3 - 9 - 8",
              "4 - 2 - 6 - 3 - 1",
              "7 - 5 - 1 - 4 - 2 ",
              "4 - 2 - 7 - 3 - 1",
              "6 - 3 - 1 - 5 - 9"
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  20: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '6 - 1 - 9 - 4 - 7 - 3',
            bodyHasFrame: true,
          ),
        ]
  },
  21: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              "6 - 1 - 4 - 7 - 3 - 9",
              "2 - 1 - 8 - 3 - 9 - 5",
              "6 - 1 - 9 - 4 - 7 - 3",
              "6 - 4 - 5 - 8 - 3 - 7",
              "2 - 8 - 6 - 4 - 7 - 3",
              "6 - 1 - 9 - 4 - 5 - 2"
            ],
            optionsColumnsSize: 1,
          ),
        ]
  },
  22: {
    'hasProx': false,
    'header': '',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '5 - 9 - 1 - 7 - 4 - 2 - 8',
            bodyHasFrame: true,
          ),
        ]
  },
  23: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Qual foi a sequência correta dos números apresentados na tela anterior?',
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              "5 - 8 - 1 - 7 - 4 - 3 - 8",
              "5 - 9 - 1 - 7 - 4 - 8",
              "8 - 9 - 0 - 7 - 3 - 1",
              "5 - 9 - 1 - 7 - 4 - 2 - 8",
              "5 - 2 - 3 - 7 - 4 - 9 - 8",
              "5 - 9 - 1 - 7 - 8 - 0 - 9"
            ],
            optionsColumnsSize: 1,
          ),
        ]
  },
  24: {
    'hasProx': true,
    'header': 'Informações',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Por favor, identifique expressões e intenções das pessoas levando em consideração apenas a região dos olhos. Para cada imagem, selecione a palavra que melhor descreve os sentimentos, pensamentos ou impressões que a pessoa em questão está transmitindo.",
            bodyHasFrame: false,
          ),
        ]
  },
  25: {
    'hasProx': true,
    'header':
        'Dentre as quatro alternativas de cada imagem. Selecione a palavra que melhor a descreve',
    'answerLenght': 14,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: 'assets/olho1.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Inquieto(a)',
              'Pensativo(a)',
              'Irritado(a)',
              'Desconfiado(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho2.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Nervoso(a)',
              'Deprimido(a)',
              'Irritado(a)',
              'Divertido(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho3.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Envergonhado(a)',
              'Divertido(a)',
              'Interessado(a)',
              'Deprimido(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho4.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[3]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Arrogante',
              'Decidido(a)',
              'Apavorado(a)',
              'Chateado(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho5.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[4]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Amável',
              'Decidido(a)',
              'Simpático(a)',
              'Deprimido(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho6.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[5]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Tímido(a)',
              'Perturbado(a)',
              'Desanimado(a)',
              'Pensativo(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho7.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[6]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Impaciente ',
              'Desanimado(a)',
              'Sedutor(a)',
              'Aliviado(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho8.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[7]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Grato(a)',
              'Sonhador(a)',
              'Desanimado(a)',
              'Chocado(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho9.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[8]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Satisfeito(a)',
              'Preocupado(a)',
              'Afetuoso(a)',
              'Indiferente'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho10.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[9]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Amável',
              'Arrependido(a)',
              'Zangado(a)',
              'Simpático(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho11.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[10]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Desconfortável',
              'Entediado(a)',
              'Confiante',
              'Impaciente'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho12.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[11]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Arrependido(a)',
              'Nervoso(a)',
              'Divertido(a)',
              'Envergonhado(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho13.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[12]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Amigável',
              'Entretido(a)',
              'Desconfiado(a)',
              'Sedutor(a)'
            ],
            optionsColumnsSize: 2,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          const DisplayFrame(
            body: 'assets/olho14.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[13]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            hasPrefiroNaoDizer: false,
            options: const [
              'Preocupado(a)',
              'Cauteloso(a)',
              'Hostil',
              'Divertido(a)'
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  26: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Tem sentido muito medo de perder o controle ou enlouquecer?',
              'Para impedir o ganho de peso, há uso de laxantes, diuréticos ou outros medicamentos; jejum, vômitos autoinduzidos, ou exercício físico em excesso?',
              'Sente medo intenso de ganhar peso ou de engordar, ao ponto de não comer?',
              'Há ingestão persistente de substâncias não nutritivas tais como doces e/ou chocolates, durante um período mínimo de um mês?',
              'Você se irrita fácil, de forma que seu humor muda facilmente durante o dia?',
              'Já teve ataques ou crises de medo intenso nos quais se sentiu muito mal?',
            ],
          ),
        ]
  },
  27: {
    'hasProx': true,
    'header': 'Qual das imagens abaixo completa a sequência a seguir?',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: 'assets/intel_1.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.more_time,
            options: const [
              'assets/intel_1a.png',
              'assets/intel_1b.png',
              'assets/intel_1c.png',
              'assets/intel_1d.png',
              'assets/intel_1e.png',
              'assets/intel_1f.png'
            ],
            optionsColumnsSize: 3,
            maxSizeAnswer: 1,
            mimSizeAnswer: 1,
          ),
        ],
  },
  28: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Ultimamente tem arrancado o próprio cabelo de forma recorrente, resultando em perda de cabelo?',
              'Observou grande perda de interesse ou prazer em todas ou quase todas as atividades na maior parte do dia; sente-se triste, vazio, sem esperança?',
              'Você se sente incomodado por pensamentos que surgem em sua mente, mesmo quando não os deseja, como o medo de estar exposto a germes, doenças ou sujeira, ou a necessidade de que tudo esteja alinhado de certa maneira?',
              'Você é incomodado por imagens indesejadas que surgem em sua mente, como cenas violentas e horríveis, ou conteúdo de natureza sexual?',
              'Percebo que sou uma pessoa especial e único/a? Espero que um dia as pessoas possam reconhecer meu valor e a diferença que faço na vida delas.',
              'Tende a se enxergar como alguém socialmente incapaz, sem atrativos pessoais ou inferior aos outros?',
              'Possui dificuldade em iniciar projetos ou fazer as coisas sozinho (por falta de autoconfiança, em vez de falta de motivação ou energia)?',
            ],
          ),
        ]
  },
  29: {
    'hasProx': true,
    'header': 'Complete as sequências a seguir:',
    'answerLenght': 4,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TextFormList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.confirmation_num,
            title: '2, 4, 8, 16, ?',
            labelText: "Sequência *",
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Horário Inválido!!';
              } else if (value.isEmpty) {
                return 'Horário Inválido!!';
              }
              return null;
            },
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.confirmation_num,
            title: '1, 3, 9, ?',
            labelText: "Sequência *",
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Horário Inválido!!';
              } else if (value.isEmpty) {
                return 'Horário Inválido!!';
              }
              return null;
            },
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.confirmation_num,
            title: '3, 7, 11, 15, ? ',
            labelText: "Sequência *",
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Horário Inválido!!';
              } else if (value.isEmpty) {
                return 'Horário Inválido!!';
              }
              return null;
            },
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[3]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.confirmation_num,
            title: '32, 16, 8, ? ',
            labelText: "Sequência *",
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Horário Inválido!!';
              } else if (value.isEmpty) {
                return 'Horário Inválido!!';
              }
              return null;
            },
            keyboardType: TextInputType.number,
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
        ],
  },
  30: {
    //Para inserir caracters em String use: "\u{0x___}"
    'hasProx': true,
    'header': 'Observe as palavras a seguir:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                '\n1)\tMUITOS\n2)\tOCEANO\n3)\tPEIXES\n4)\tE\n5)\tTEM\n6)\tO\n7)\tPLANTAS\n\nAgora forme uma frase que faça sentido e contenha todas essas palavras. Marque a ordem correta:',
            hasPrefiroNaoDizer: false,
            options: const [
              '1 - 4 - 6 - 2 - 5 - 3 - 7',
              '6 - 2 - 4 - 7 - 5 - 1 - 3',
              '5 - 1 - 3 - 4 - 6 - 7 - 2',
              '6 - 2 - 5 - 1 - 3 - 4 - 7',
              '7 - 4 - 3 - 5 - 1 - 2 - 6 '
            ],
            optionsColumnsSize: 1,
          ),
        ]
  },
  31: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Sente algo estranho dentro do seu corpo, e/ou movimentos, como se levasse um empurrão?',
              'Sente como se alguém lhe tocasse, beliscassem, batessem ou beijassem seu corpo?',
              'Possui a sensação de falta de controle durante a alimentação; não consegue parar de comer ou controlar a quantidade que está ingerindo?',
              'Sente-se descansado e preparado para mais um dia, mesmo com apenas 3 horas de sono?',
              'Você com frequência tem dificuldade em manter-se concentrado durante a realização de tarefas ou atividades?',
              'Muitas vezes responde precipitadamente antes que as perguntas tenham sido completadas.',
            ],
          ),
        ]
  },
  32: {
    'hasProx': true,
    'header':
        'Preencha o campo a seguir com o nome da cidade e estado onde você está agora.',
    'answerLenght': 2,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TextFormList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.location_city,
            labelText: 'CIDADE:',
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Cidade Inválida!!';
              } else if (value.isEmpty) {
                return 'Cidade Inválida!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            icon: Icons.location_history,
            labelText: 'ESTADO:',
            optionsColumnsSize: 1,
            validator: (value) {
              if (value == null) {
                return 'Estado Inválido!!';
              } else if (value.isEmpty) {
                return 'Estado Inválido!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
        ],
  },
  33: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'Selecione qual o período do dia atual ?',
            icon: Icons.timer_outlined,
            hasPrefiroNaoDizer: false,
            options: const [
              'Manhã: 6:00 às 11:59 horas',
              'Tarde: 12:00 às 17:59 horas',
              'Noite: 18:00 às 23:59 horas',
              'Madrugada: 00:00 às 05:59 horas',
            ],
            optionsColumnsSize: 1,
          ),
        ]
  },
  34: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                'Seis (6) imagens serão apresentadas. Fique atendo! Em um certo momento do teste, elas serão escondidas em uma figura e você deverá encontrá-las.',
            bodyHasFrame: false,
          ),
        ]
  },
  35: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/CORREDOR.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  36: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/PAPAI NOEL.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  37: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/circo.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  38: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/chuteira.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  39: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/NUMERO8.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  40: {
    'hasProx': false,
    'header': 'Atenção!!',
    'answerLenght': 0,
    'itens': (TelasController controller, __) => [
          DisplayFrame(
            body: 'assets/reciclagem.png',
            bodyHasFrame: true,
            isLoading: () {
              Future.delayed(const Duration(seconds: 3)).then(
                (value) {
                  Modular.to.popAndPushNamed('/',
                      arguments: controller.idPage.value + 1);
                },
              );
            },
          ),
        ]
  },
  41: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Diariamente, há momentos em que você sente como se o chão oscilasse?',
              'Durante o dia há vários momentos em que você se sente irritado(a) e impaciente?',
              'Diariamente, há momentos em que você se sente muito feliz, irradiante?',
              'Durante o dia há vários momentos em que você se sente triste e/ou melancólico(a)?',
              'Tem notado(a) muita preocupação com um ou mais defeitos ou falhas percebidas na aparência física que não são observáveis ou que parecem leves para os outros.',
              'Você com frequência mexe de forma irrequieta as mãos e os pés ou remexe-se na cadeira quando está sentado(a)?',
              'Exibe dificuldade em concordar com as ideias de outras pessoas, demonstrando inflexibilidade e rigidez tanto em relação a si mesmo quanto aos outros.',
            ],
          ),
        ]
  },
  42: {
    'hasProx': true,
    'header': 'Encontre os objetos!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body:
                'Seis (6) imagens foram apresentadas em algum momento do teste. Vamos encontrá-los? Clique nas figuras que você lembrou. Não é obrigado(a) a encontrar todas as imagens. Faça o seu melhor!\n',
            bodyHasFrame: false,
          ),
          const SizedBox(height: 10.0),
          FindImages(
              answer: controller.answerAux.value[0]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              imagem: 'assets/seisimagens.png'),
        ],
  },
  43: {
    'hasProx': true,
    'header': 'Avalie e responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: "assets/questao32.png",
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                "\nSe tivesse a oportunidade de, por alguns minutos, adquirir conhecimento sobre alguém ou algo por meio de uma abertura no tempo e espaço, quais das ações a seguir você optaria por realizar? Escolha duas ou três opções que mais se adequariam a você.\n",
            //icon: Icons.more_time,
            options: const [
              'Encontrar-se com um ente querido falecido.',
              'Ver uma pessoa nua',
              'Saber como desempenhar tarefas cotidianas sem ser prejudicado por pensamentos incessantes que me limitam.',
              'Voltar na minha infância e recomeçar tudo',
              'Voltar na minha adolescência e recomeçar tudo',
              'Saber se meu namorado (a) ou esposo (a) está me traindo',
              'Saber como poderia ser o futuro da minha família e ajudá-los',
              'Desaparecer no tempo e espaço, ao entrar pela fenda',
              'Saber se estarei vivo daqui 5 anos.',
              'Saber quem é minha alma gêmea',
              'Ver meu futuro profissional',
              'Saber como faço para não pensar coisas bizarras',
              'Testemunhar avanços tecnológicos futuros.',
              'Presenciar um evento histórico de grande relevância, como a construção das pirâmides do Egito, a Grande Muralha da China, a era dos dinossauros, ou a criação de alguma das invenções de Albert Einstein ou Leonardo da Vinci, por exemplo.',
              'Saber se ficarei rico(a)',
              'Saber quem está me perseguindo na rua',
              'Saber como faço para dormir a noite toda.',
              'Saber como fazer meu cônjuge e/ou filho(a) a realizar tarefas e tomar decisões em suas vidas de acordo com meus valores e princípios.',
              'Saber como desaparecer minha dor e sofrimento existencial.',
            ],
            optionsColumnsSize: 1,
            mimSizeAnswer: 2,
            maxSizeAnswer: 3,
          ),
        ],
  },
  44: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Percebe-se impulsivo(a) e de forma abusiva; p. ex., gastos exagerados, sexo com desconhecidos, abuso de substâncias, dirigir de forma perigosa/irresponsável e/ou atos repetitivos de autolesão?',
              'Tem dificuldade em terminar o que começa?',
              'Quando você conta uma história que aconteceu, na maioria das vezes você exagera e dramatiza alguns detalhes?',
              'Já testemunhou e/ou ainda é exposto(a) de forma repetida ou extrema a detalhes aversivos do evento traumático?',
              'Você apresenta explosões de raiva recorrente, manifestadas por meio da linguagem (como insultos dirigidos a outras pessoas) ou através de ações (como agressão física)?',
              'Você está tendo insônia praticamente todos os dias?',
            ],
          ),
        ]
  },
  45: {
    'hasProx': true,
    'header': 'Atenção !!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body: 'Atente-se ao som que será reproduzido na próxima tela.',
            bodyHasFrame: false,
          ),
        ]
  },
  46: {
    'hasProx': false,
    'header': 'Pressione o play para escutar !!',
    'answerLenght': 0,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          DisplayFrame(
            id: controller.idPage.value,
            body: "assets/audios/aguacorrente-edited_v2.mp3",
            bodyHasFrame: true,
            playMusic: controller.playMusic,
          ),
        ]
  },
  47: {
    'hasProx': true,
    'header': 'Responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'Qual das opções corresponde ao som escutado?',
            hasPrefiroNaoDizer: false,
            options: const [
              "Pássaros",
              "Barulho de água",
              "Aspirador de pó",
              "Choro de criança",
              "Telefone tocando",
              "Sem som"
            ],
            optionsColumnsSize: 2,
          ),
        ]
  },
  48: {
    'hasProx': true,
    'header': 'Observe e responda',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: "assets/Ebbinghaus.png",
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Selecione qual alternativa corresponde ao que você vê na imagem acima.',
            icon: Icons.more_time,
            options: const [
              'A Reta A é maior que a Reta B',
              'A Reta A é menor que a Reta B',
              'Retas A e B, são do mesmo tamanho',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
        ],
  },
  49: {
    'hasProx': true,
    'header': 'Desenhe !!',
    'answerLenght': 3,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() {
                if (controller.answerAux.value[0].value == 'Não desejo fazer') {
                  controller.answerAux.value[1].value = 'Sucess';
                  controller.answerAux.value[2].value = 'Sucess';
                  state.currentState!.didChange(controller.answerAux.value);
                } else {
                  addListenerComposto(controller, state, 0, 1);
                  controller.answerAux.value[2].value = '';
                }
              }),
            title:
                'Serão exibidos diversos pontos e ao clicar sobre estes pontos, você poderá compor imagens, uma vez que os pontos serão conectados por linhas retas. Escolha uma das sugestões fornecidas, selecionando a opção e inicie o processo de desenho. O tempo disponível é flexível, permitindo que você retorne ou apague conforme necessário.',
            options: const [
              'Avião',
              'Borboleta',
              'Casa',
              'Estrela',
              'Quadrado',
              'Não desejo fazer',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
            otherItem: TextFormList(
              answer: controller.answerAux.value[1]
                ..addListener(() =>
                    state.currentState!.didChange(controller.answerAux.value)),
              keyboardType: TextInputType.name,
              labelText: "O que você deseja desenhar ?",
              inputFormatters: [
                FilteringTextInputFormatter.singleLineFormatter
              ],
              validator: (value) {
                if (value == null) {
                  return 'Descrição invalida!! Corrija por favor';
                } else if ((value.isEmpty) || (value.length < 3)) {
                  return 'Descrição invalida!! Corrija por favor';
                }
                return null;
              },
            ),
          ),
          const SizedBox(height: 10.0),
          DotsLine(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
          ),
        ],
  },
  50: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Você tem sentido mais fadiga ou perda de energia quase todos os dias?',
              'Você vivenciou algum evento traumático?',
              'Você tem escutado Zumbido no ouvido?',
              'Você tem dificuldades em jogar fora objetos usados ou sem valor, mesmo quando não têm valor sentimental. Ultimamente guarda muitas coisas, papeis, recibos, com a ideia de que poderá precisar algum dia?',
              'Você apresenta comportamentos repetitivos (p. ex., lavar as mãos, organizar, verificar) ou atos mentais (p. ex., orar, contar ou repetir palavras em silêncio).',
              'Você se sente incomodado por impulsos como machucar alguém que você ama, mesmo quando não deseja fazê-lo?',
              'Você tem visto algo estranho como figuras, sombras, fogo, fantasmas, demônios, pessoas estranhas ou algo do tipo, no seu dia a dia?',
            ],
          ),
        ]
  },
  51: {
    'hasProx': true,
    'leading': {
      'selectedIcon': Icons.comment_sharp,
      'deselectedIcon': Icons.comments_disabled,
    },
    'header': 'Jogo dos 5 (cinco) erros',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body:
                'No botão que aparece na barra de aplicação acima é possível mudar entre duas imagens: uma considerada \'verdadeira\' e a outra \'falsa\'. Entre elas, há 5 alterações que você deve identificar, apontando as discrepâncias por meio de cliques nos locais correspondentes na imagem falsa.',
            bodyHasFrame: false,
          ),
          const SizedBox(height: 10.0),
          FiveErrors(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            imagemFull: 'assets/five_errors1.jpg',
            imagemClean: 'assets/five_errors2.jpg',
            isImagemFull: controller.isImagemFull,
          ),
        ],
  },
  52: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Nos últimos meses, você tem ouvido vozes de pessoas estranhas?',
              'Ultimamente, você tem ouvido vozes que são seus próprios pensamentos sendo expressos em voz alta?',
              'Alguém tem tentado envenená-lo(a)?',
              'Você tem dificuldade para relaxar? Está sempre ocupado(a)?',
              'Você vem apresentando sensações de falta de ar ou sufocamento?',
              'Você está vivenciando um estado de luto prolongado e persistente, que se estende por um período superior a 12 meses, caracterizado por uma intensa saudade, preocupação e apatia em relação ao futuro?',
              'Você tem medo de ser demitido(a) o tempo todo?'
            ],
          ),
        ]
  },
  53: {
    'hasProx': true,
    'header': 'Avalie e responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: 'assets/intel_2.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: "Qual das imagens abaixo completa a sequência a seguir?",
            //icon: Icons.more_time,
            options: const [
              'assets/intel_2a.png',
              'assets/intel_2b.png',
              'assets/intel_2c.png',
              'assets/intel_2d.png',
              'assets/intel_2e.png',
              'assets/intel_2f.png'
            ],
            optionsColumnsSize: 3,
            mimSizeAnswer: 1,
            maxSizeAnswer: 1,
          ),
        ],
  },
  54: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Você vive com medo de decepcionar as pessoas?',
              'Você tem-se irritado com mais facilidade que antes?',
              'Nos últimos meses você sente dificuldades de parar de se preocupar?',
              'Você pensa muitas coisas ao mesmo tempo?',
              'Você sente dificuldade em se concentrar?',
              'Evita realizar atividades profissionais ou estudantis que impliquem contato interpessoal, pois tem muito medo de críticas, desaprovação ou rejeição?',
              'Você não acha que tem fraquezas e muito menos evita ambientes, pois consegue tudo o que quer?',
            ],
          ),
        ]
  },
  55: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Na próxima tela será reproduzida algumas palavras. Fique atento.",
            bodyHasFrame: false,
          ),
        ]
  },
  56: {
    'hasProx': false,
    'header': 'Pressione o play para escutar !!',
    'answerLenght': 0,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          DisplayFrame(
            id: controller.idPage.value,
            body: 'assets/audios/quatro_palavras.mp3',
            bodyHasFrame: true,
            playMusic: controller.playMusic,
          ),
        ]
  },
  57: {
    'hasProx': true,
    'header': 'Avalie e responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                'Escolha de 2 a 3 imagens que possam representar você ou seu jeito de ser.',
            //icon: Icons.more_time,
            options: const [
              'assets/questao45coquetel.png',
              'assets/questao45humburgue.png',
              'assets/questao45casa.png',
              'assets/questao45gato.png',
              'assets/questao45trabalhador.png',
              'assets/questao45carro.png',
              'assets/questao45cachorro.png',
              'assets/questao45passaro.png',
              'assets/questao45cerveja.png',
              'assets/questao45cocacola.png',
              'assets/questao45cafe.png',
              'assets/questao45bombons.png',
              'assets/questao45viajar.png',
              'assets/questao45livros.png',
              'assets/questao45leaonovo.png',
              'assets/questao45controlegame.png',
            ],
            optionsColumnsSize: 2,
            mimSizeAnswer: 2,
            maxSizeAnswer: 3,
          ),
        ],
  },
  58: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Você acredita que precisa fazer as coisas de forma perfeita, caso contrário não será aceito (a)? ',
              'Você acredita que as pessoas estão julgando suas atitudes e comportamentos, mesmo que não estejam dizendo?',
              'Você tem ideias negativas, como pensar em morrer?',
              'Você se sente inadequado (a) inquieto (a) e conversa de forma excessiva?',
              'Você costuma adiar ou evitar fazer as coisas até o último minuto? Possui o perfil de procrastinar?',
              'Tem relutado em delegar tarefas ou de trabalhar com outras pessoas, pois precisa estar no controle de tudo.',
              'Você percebe que se esforça de forma intensa para evitar ser abandonado (a)?',
            ],
          ),
        ]
  },
  59: {
    'hasProx': true,
    'header': 'Responda de acordo com o som escutado anteriormente!!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'Qual das opções corresponde ao som escutado?\n',
            icon: Icons.more_time,
            options: const [
              "Rua - Madeira - Paz - Pastel",
              "Lua - Cadeira - Raiz - Chapéu",
              "Rua - Cadeira - Paz - Chapéu",
              "Lua - Cadeira - Paz - Pastel",
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
        ],
  },
  60: {
    'hasProx': true,
    'header':
        'Marque a expressão que melhor corresponde a emoção básica descrita.',
    'answerLenght': 6,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body: 'assets/questao48.png',
            bodyHasFrame: true,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'a) Nojo:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'b) Tristeza:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'c) Medo:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[3]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'd) Raiva:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[4]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'e) Alegria:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[5]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: 'f) Surpresa:',
            icon: Icons.more_time,
            options: const ["1", "2", "3", "4", "5", "6"],
            optionsColumnsSize: 6,
            hasPrefiroNaoDizer: false,
          ),
        ],
  },
  61: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Nas próximas 4 telas, serão exibidas diversas expressões representando diferentes sentimentos. Em cada tela, selecione pelo menos 3 e no máximo 4 expressões que melhor correspondem ao que você tem sentido nos últimos meses.\n\nQuando estiver pronto é só clicar em próximo...",
            bodyHasFrame: false,
          ),
        ]
  },
  62: {
    'hasProx': true,
    'header': 'Selecione!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            //icon: Icons.more_time,
            title:
                'Selecione pelo menos 2 e no máximo 4 expressões que melhor correspondem ao que você tem sentido nos últimos meses.',
            options: const [
              'assets/emoji_sempre_atrasado.png',
              'assets/emoji_poderoso.png',
              'assets/emoji_otimista.png',
              'assets/emoji_em_panico.png',
              'assets/emoji_indeciso.png',
              'assets/emoji_triste.png',
              'assets/emoji_entediado.png',
              'assets/emoji_pessimista.png',
              'assets/emoji_reflexivo.png',
              'assets/emoji_confiante.png',
              'assets/emoji_forte.png',
              'assets/emoji_nojo.png',
            ],
            optionsColumnsSize: 3,
            mimSizeAnswer: 2,
            maxSizeAnswer: 4,
          ),
        ],
  },
  63: {
    'hasProx': true,
    'header': 'Selecione!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            //icon: Icons.more_time,
            title:
                'Selecione pelo menos 2 e no máximo 4 expressões que melhor correspondem ao que você tem sentido nos últimos meses.',
            options: const [
              'assets/emoji_esperancoso.png',
              'assets/emoji_pura_alegria.png',
              'assets/emoji_burro.png',
              'assets/emoji_surpreso.png',
              'assets/emoji_feliz.png',
              'assets/emoji_velho.png',
              'assets/emoji_frustrado.png',
              'assets/emoji_ansioso.png',
              'assets/emoji_emocionado.png',
              'assets/emoji_em_paz.png',
              'assets/emoji_inteligente.png',
              'assets/emoji_preocupado.png',
            ],
            optionsColumnsSize: 3,
            mimSizeAnswer: 2,
            maxSizeAnswer: 4,
          ),
        ],
  },
  64: {
    'hasProx': true,
    'header': 'Selecione!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            //icon: Icons.more_time,
            title:
                'Selecione pelo menos 2 e no máximo 4 expressões que melhor correspondem ao que você tem sentido nos últimos meses.',
            options: const [
              'assets/emoji_apaixonado.png',
              'assets/emoji_desesperado.png',
              'assets/emoji_envergonhado.png',
              'assets/emoji_abencoado.png',
              'assets/emoji_impulsivo.png',
              'assets/emoji_amado.png',
              'assets/emoji_confuso.png',
              'assets/emoji_sem_forcas.png',
              'assets/emoji_sonolento.png',
              'assets/emoji_gordo.png',
              'assets/emoji_sem_paciencia.png',
              'assets/emoji_com_ciumes.png',
            ],
            optionsColumnsSize: 3,
            mimSizeAnswer: 2,
            maxSizeAnswer: 4,
          ),
        ],
  },
  65: {
    'hasProx': true,
    'header': 'Selecione!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            //icon: Icons.more_time,
            title:
                'Selecione pelo menos 2 e no máximo 4 expressões que melhor correspondem ao que você tem sentido nos últimos meses.',
            options: const [
              'assets/emoji_com_raiva.png',
              'assets/emoji_silenciado.png',
              'assets/emoji_desanimado.png',
              'assets/emoji_com_gratidao.png',
              'assets/emoji_fraude.png',
              'assets/emoji_agressivo.png',
              'assets/emoji_desequilibrado.png',
              'assets/emoji_comendo_muito.png',
              'assets/emoji_fumando_muito.png',
              'assets/emoji_jesus.png',
              'assets/emoji_bebendo_muito.png',
              'assets/emoji_animado.png',
            ],
            optionsColumnsSize: 3,
            mimSizeAnswer: 2,
            maxSizeAnswer: 4,
          ),
        ],
  },
  66: {
    'hasProx': true,
    'header': 'Avalie e responda !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          MultiSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title:
                "Selecione as palavras que você mais gosta e, ao mesmo tempo, lhe descreveria. A quantidade é ilimitada, pode escolher quantas palavras quiser, desde que elas fazem sentido na sua vida.",
            options: const [
              'ABANDONO',
              'ACOMETIDO(A)',
              'AFEIÇÃO',
              'AMIUDAR',
              'ANTIPATIA',
              'APATIA',
              'APEGO',
              'APREENSÃO',
              'ARQUEJO',
              'ATONIA',
              'AUTENTICIDADE',
              'AUTOCÍDIO',
              'AUTOESTIMA',
              'BELEZA',
              'BONDADE',
              'COMPLACÊNCIA',
              'COMPULSÃO',
              'CORAGEM',
              'DECÊNCIA',
              'DESAFETO',
              'DESÂNIMO',
              'DESARMONIA',
              'DESTEMOR',
              'DIGNIDADE',
              'ELEGÂNCIA',
              'EMPATIA',
              'ENGODO',
              'ESPERANÇA',
              'ESTIMA',
              'ESTREITEZA',
              'EUFORIA',
              'FORTÚNIO',
              'FRACASSO',
              'FRAQUEZA',
              'FUGAZ',
              'GENTILEZA',
              'GRATIDÃO',
              'HARMONIA',
              'HUMILDADE',
              'IMPAVIDEZ',
              'IMPOTÊNCIA',
              'IMPULSIVIDADE',
              'INAPETÊNCIA',
              'INDIFERENÇA',
              'INDULGÊNCIA',
              'INQUIETUDE',
              'INTELIGÊNCIA',
              'LETARGIA',
              'MÁGOA',
              'MANIA',
              'MAQUIAVÉLICO',
              'MELANCOLIA',
              'MORTE',
              'NOSTALGIA',
              'OBCECAÇÃO',
              'OBSESSÃO',
              'PERECÍVEL',
              'PERSISTÊNCIA',
              'PREOCUPAÇÃO',
              'PROSTRAÇÃO',
              'PRUDÊNCIA',
              'RUMINAÇÃO',
              'RAIVA',
              'RANCOR',
              'SATISFAÇÃO',
              'SIGILO',
              'SOLIDÃO',
              'SUICÍDIO',
              'TENACIDADE',
              'VIRTUDE',
            ],
            optionsColumnsSize: 2,
            mimSizeAnswer: 1,
            maxSizeAnswer: 65,
          ),
        ],
  },
  67: {
    'hasProx': true,
    'header': 'Atenção!!',
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Na próxima tela será reproduzida uma lista de 10 pares de palavras relacionadas logicamente entre si (p. ex., alto-baixo). Depois, você será solicitado para preencher a palavra faltante. Fique atento, você terá que memorizar todos os pares.\n\nQuando estiver pronto é só clicar em próximo...",
            bodyHasFrame: false,
          ),
        ]
  },
  68: {
    'hasProx': false,
    'header': 'Pressione o play para escutar !!',
    'answerLenght': 0,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          DisplayFrame(
            id: controller.idPage.value,
            body: 'assets/audios/dez_palavras.mp3',
            bodyHasFrame: true,
            playMusic: controller.playMusic,
          ),
        ]
  },
  69: {
    'hasProx': true,
    'header': 'Complete com o par correspondente escutado anteriormente',
    'answerLenght': 10,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TextFormList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'chuva -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'criança -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: '- verão',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[3]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'mostro -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[4]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: '- água',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[5]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'dinheiro -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[6]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: '- pequeno',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[7]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'livro -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[8]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: '- móvel',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          TextFormList(
            answer: controller.answerAux.value[9]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            optionsColumnsSize: 1,
            options: 'Professor -',
            validator: (value) {
              if (value == null) {
                return 'Dados Incorrets!!';
              } else if ((value.isEmpty) || (value.length < 2)) {
                return 'Dados Incorretos!!';
              }
              return null;
            },
            keyboardType: TextInputType.name,
            inputFormatters: [
              FilteringTextInputFormatter.singleLineFormatter,
            ],
          ),
        ],
  },
  70: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Você se preocupa com a internet (pensa sobre atividades virtuais anteriores ou fica antecipando quando ocorrerá a próxima conexão)?',
              'Você sente necessidade de usar a internet por períodos cada vez maiores para se sentir satisfeito?',
              'Você já se esforçou repetidas vezes para controlar, diminuir ou parar de usar a internet, mas fracassou?',
              'Você fica inquieto, mal-humorado, deprimido ou irritável quando tenta diminuir, parar de usar a internet ou quando o uso é restringido?',
              'Você fica online mais tempo do que pretendia originalmente?',
              'Você já prejudicou ou correu o risco de perder um relacionamento significativo, emprego ou oportunidade educacional ou profissional por causa de internet?',
              'Você já mentiu para familiares, terapeutas ou outras pessoas para esconder a extensão do seu envolvimento com a internet?',
              'Você usa a internet como uma maneira de fugir de problemas ou de aliviar um humor desagradável (por exemplo, sentimento de impotência, solidão, culpa, tristeza, ansiedade, depressão)?',
            ],
          ),
        ]
  },
  71: {
    'hasProx': true,
    'header': 'Com que frequência você pausa e consome estas substâncias?',
    'answerLenght': 5,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: '1) Cafeina:',
            icon: Icons.more_time,
            options: const [
              'Nunca',
              'Uma vez por mês ou menos (raramente)',
              'Duas a quatro vezes ao mês (às vezes)',
              'Duas a três vezes por semana',
              'Na maioria dos dias ou sempre',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[1]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: '2)	Álcool:',
            icon: Icons.more_time,
            options: const [
              'Nunca',
              'Uma vez por mês ou menos (raramente)',
              'Duas a quatro vezes ao mês (às vezes)',
              'Duas a três vezes por semana',
              'Na maioria dos dias ou sempre',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[2]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: '3)	Tabaco:',
            icon: Icons.more_time,
            options: const [
              'Nunca',
              'Uma vez por mês ou menos (raramente)',
              'Duas a quatro vezes ao mês (às vezes)',
              'Duas a três vezes por semana',
              'Na maioria dos dias ou sempre',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[3]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: '4)	Maconha:',
            icon: Icons.more_time,
            options: const [
              'Nunca',
              'Uma vez por mês ou menos (raramente)',
              'Duas a quatro vezes ao mês (às vezes)',
              'Duas a três vezes por semana',
              'Na maioria dos dias ou sempre',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
          const SizedBox(height: 10.0),
          const Divider(),
          const SizedBox(height: 10.0),
          SingleSelectionList(
            answer: controller.answerAux.value[4]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            title: '5)	Cocaína/crack:',
            icon: Icons.more_time,
            options: const [
              'Nunca',
              'Uma vez por mês ou menos (raramente)',
              'Duas a quatro vezes ao mês (às vezes)',
              'Duas a três vezes por semana',
              'Na maioria dos dias ou sempre',
            ],
            optionsColumnsSize: 1,
            hasPrefiroNaoDizer: false,
          ),
        ],
  },
  72: {
    'hasProx': true,
    'header': 'Responda as questões abaixo:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          TypeYesNo(
            answer: controller.answerAux.value[0]
              ..addListener(() =>
                  state.currentState!.didChange(controller.answerAux.value)),
            options: const [
              'Você tem medo ou ansiedade acentuados acerca de um objeto ou situação (p. ex., voar, altura, animais, tomar uma injeção, ver sangue).',
              'Você apresenta dificuldade persistente de descartar ou de se desfazer de pertences, independentemente do seu valor real.',
              'Possui medo ou ansiedade acentuada acerca de uma ou mais situações sociais em que é exposto a uma possível avaliação por outras pessoas. Exemplos incluem interações sociais (p. ex., manter uma conversa, encontrar pessoas que não são familiares), ser observado (p. ex., comendo ou bebendo) e situações de desempenho diante de outros (p. ex., proferir palestras, falar em público).',
              'Você não tem amigos íntimos ou confidentes que não sejam membros da família de primeiro grau. Geralmente, busca atividades de lazer e/ou profissionais de forma solitária?',
              'Você adota um estilo bem baixo de gastos em relação a si e a outros; enxergando o dinheiro como algo a ser poupado para possíveis emergências futuras.',
              'Você vem tendo sentimentos de inutilidade ou culpa excessiva? ',
              'Você iniciou uma quantidade maior de projetos do que o normal ou se envolveu em atividades mais arriscadas do que o habitual?',
            ],
          ),
        ]
  },
  73: {
    'hasProx': true,
    'header': 'Escolha !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(
                () {
                  if (controller.answerAux.value[0].value ==
                      'Tenho daltonismo') {
                    controller.idPage.value = controller.idPage.value + 2;
                  }
                  state.currentState!.didChange(controller.answerAux.value);                  
                },
              ),
            title:
                'Daltonismo é o termo usado para denominar a falta de sensibilidade ocular que algumas pessoas possuem na percepção de determinadas cores. Você tem Daltonismo? Foi diagnosticado por um profissional especializado? Se sim, basta clicar em \'Tenho daltonismo.\' Se você não tem daltonismo, clique em \'Não tenho daltonismo\' e depois continuar com a atividade.\n',
            icon: Icons.more_time,
            options: const [
              'Tenho daltonismo',
              'Não tenho daltonismo',
            ],
            optionsColumnsSize: 3,
            hasPrefiroNaoDizer: false,
          ),
        ]
  },
  74: {
    'hasProx': true,
    'header': 'Vamos colorir !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body:
                'Marque a cor que você mais gosta e pinte os círculos da figura abaixo. Faça da forma que mais te agrada.\n',
            bodyHasFrame: false,
          ),
          ArvoreCiculos(
            answer: controller.answerAux.value[0]
              ..addListener(
                () => state.currentState!.didChange(controller.answerAux.value),
              ),
            imagem: 'assets/arvore_circulos.png',
            itens: const [
              'Azul',
              'Verde',
              'Laranja',
              'Amarelo',
              'Vermelho',
              'Rosa',
              'Marrom',
              'Preto',
              'Cinza',
            ],
            optionsColumnsSize: 3,
            colors: const [
              Colors.blue,
              Colors.green,
              Colors.orange,
              Colors.yellow,
              Colors.red,
              Colors.pink,
              Colors.brown,
              Colors.black,
              Colors.grey,
            ],
          ),
        ]
  },
  75: {
    'hasProx': true,
    'header': 'Vamos colorir !!',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          const DisplayFrame(
            body:
                'Marque a cor que você mais gosta e pinte os retângulos da figura abaixo. Faça da forma que mais te agrada.\n',
            bodyHasFrame: false,
          ),
          MuroColorido(
            answer: controller.answerAux.value[0]
              ..addListener(
                () => state.currentState!.didChange(controller.answerAux.value),
              ),
            imagem: 'assets/arvore_circulos.png',
            itens: const [
              'Azul',
              'Verde',
              'Laranja',
              'Amarelo',
              'Vermelho',
              'Rosa',
              'Marrom',
              'Preto',
              'Cinza',
            ],
            optionsColumnsSize: 3,
            colors: const [
              Colors.blue,
              Colors.green,
              Colors.orange,
              Colors.yellow,
              Colors.red,
              Colors.pink,
              Colors.brown,
              Colors.black,
              Colors.grey,
            ],
          ),
        ]
  },
  76: {
    'hasProx': true,
    'header': 'Selecione qual dia da semana é hoje:',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(
                () => state.currentState!.didChange(controller.answerAux.value),
              ),
            icon: Icons.more_time,
            options: const [
              'Segunda-feira',
              'Terça-feira',
              'Quarta-feira',
              'Quinta-feira',
              'Sexta-feira',
              'Sábado',
              'Domingo',
            ],
            optionsColumnsSize: 2,
            hasPrefiroNaoDizer: false,
          ),
        ]
  },
  77: {
    'hasProx': true,
    'header':
        'Quanto tempo, aproximadamente, você acha que investiu para fazer este teste?',
    'answerLenght': 1,
    'itens': (
      TelasController controller,
      GlobalKey<FormFieldState<List<ValueNotifier<String>>>> state,
    ) =>
        [
          SingleSelectionList(
            answer: controller.answerAux.value[0]
              ..addListener(
                () => state.currentState!.didChange(controller.answerAux.value),
              ),
            icon: Icons.more_time,
            options: const [
              '5 minutos',
              '15 minutos',
              '30 minutos',
              '40 minutos',
              '60 minutos',
              'Mais que 1 hora',
            ],
            optionsColumnsSize: 2,
            hasPrefiroNaoDizer: false,
          ),
        ]
  },
  78: {
    'hasProx': false,
    'header': 'Parabéns!!!!',
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body:
                "Você terminou o questionário, agradeçemos muito pela sua disponibilidade.\n\nOBS.: Você ja pode fechar esta página.",
            bodyHasFrame: false,
          ),
        ]
  },
};
