import 'package:brasil_fields/brasil_fields.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:ia_triagem/src/modelView/options_style/display_frame.dart';

import '../../modelView/options_style/send_email.dart';
import '../../modelView/options_style/single_selection_list.dart';
import '../../modelView/options_style/text_form_list.dart';
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
              labelText: "Quantos irmãos voçê tem?",
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
              keyboardType: TextInputType.none,
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
              labelText: "Quantos filhos voçê tem?",
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
                  "\nCaso afirmativo, selecione o diagnóstico\n correspondente. *",
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
                'A partir de agora serão apresentadas telas com as instruções das tarefas que você irá responder.\n\nCertifique-se que esteja em um ambiente silencioso, sem estímulos de distração.\n\nEm algumas telas, sons serão reproduzidos; portanto, é fundamental usar fones de ouvido ou ligar os alto-falantes do seu dispositivo.',
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
    'delay': 3,
    'answerLenght': 0,
    'itens': (_, __) => [
          const DisplayFrame(
            body: 'assets/arvore_free.png',
            bodyHasFrame: true,
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
            icon: Icons.transgender,
            hasPrefiroNaoDizer: true,
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
            icon: Icons.transgender,
            hasPrefiroNaoDizer: true,
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
            body: "Nas próximas telas, serão apresentadas algumas sequências de números, após visualizá-las você deverá marcar a resposta que corresponde à sequência correta.",
            bodyHasFrame: false,
          ),
        ]
  },
  12: {
    'hasProx': true,
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'answerLenght': 1,
    'itens': (_, __) => [
          const DisplayFrame(
            body: '2 - 7',
            bodyHasFrame: true,
          ),          
        ]
  },  
  13: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?',
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 3,
        'options': ["1 - 5", "4 - 7", "2 - 7", "2 - 8", "9 - 4", "7 - 2"],
      },
    ],
  },
  14: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': '5 - 6 - 4',
      },
    ], // options_type: text
  },
  15: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?', //Titulo do card
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 3,
        'options': [
          "5 - 7 - 1",
          "1 - 3 - 4",
          "5 - 6 - 3",
          "4 - 6 - 5",
          "5 - 4 - 6",
          "5 - 6 - 4"
        ],
      },
    ], // options_type: text || image
  },
  16: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': '6 - 4 - 3 - 9',
      },
    ], // options_type: text
  },
  17: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?',
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 3,
        'options': [
          "6 - 4 - 9 - 3",
          "4 - 8 - 9 - 1",
          "6 - 4 - 3 - 9",
          "5 - 4 - 3 - 8",
          "1 - 5 - 2 - 9",
          "6 - 4 - 3 - 7"
        ], // options_type: text || image
      },
    ],
  },
  18: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': '4 - 2 - 7 - 3 - 1',
      },
    ], // options_type: text
  },
  19: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?',
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          "2 - 1 - 4 - 7 - 9",
          "4 - 3 - 9 - 8",
          "4 - 2 - 6 - 3 - 1",
          "7 - 5 - 1 - 4 - 2 ",
          "4 - 2 - 7 - 3 - 1",
          "6 - 3 - 1 - 5 - 9"
        ], // options_type: text || image
      },
    ],
  },
  20: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': '6 - 1 - 9 - 4 - 7 - 3',
      },
    ], // options_type: text
  },
  21: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?',
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          "6 - 1 - 4 - 7 - 3 - 9",
          "2 - 1 - 8 - 3 - 9 - 5",
          "6 - 1 - 9 - 4 - 7 - 3",
          "6 - 4 - 5 - 8 - 3 - 7",
          "2 - 8 - 6 - 4 - 7 - 3",
          "6 - 1 - 9 - 4 - 5 - 2"
        ], // options_type: text || image
      },
    ],
  },
  22: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atente-se para a sequência de números apresentada',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': '5 - 9 - 1 - 7 - 4 - 2 - 8',
      },
    ],
  },
  23: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual foi a sequência correta dos números apresentados na tela anterior?',
    'itens': [
      {
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          "5 - 8 - 1 - 7 - 4 - 3 - 8",
          "5 - 9 - 1 - 7 - 4 - 8",
          "8 - 9 - 0 - 7 - 3 - 1",
          "5 - 9 - 1 - 7 - 4 - 2 - 8",
          "5 - 2 - 3 - 7 - 4 - 9 - 8",
          "5 - 9 - 1 - 7 - 8 - 0 - 9"
        ],
      },
    ],
  },
  24: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Informações',
    'delay': 3,
    'itens':
        "Por favor, identifique expressões e intenções das pessoas levando em consideração apenas a região dos olhos. Para cada imagem, selecione a palavra que melhor descreve os sentimentos, pensamentos ou impressões que a pessoa em questão está transmitindo.",
  },
  25: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Dentre as quatro alternativas de cada imagem. Selecione a palavra que melhor a descreve', //Titulo do card
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho1.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Inquieto(a)',
          'Pensativo(a)',
          'Irritado(a)',
          'Desconfiado(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho2.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Nervoso(a)',
          'Deprimido(a)',
          'Irritado(a)',
          'Divertido(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho3.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Envergonhado(a)',
          'Divertido(a)',
          'Interessado(a)',
          'Deprimido(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho4.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Arrogante', 'Decidido(a)', 'Apavorado(a)', 'Chateado(a)'],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho5.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Amável', 'Decidido(a)', 'Simpático(a)', 'Deprimido(a)'],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho6.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Tímido(a)',
          'Perturbado(a)',
          'Desanimado(a)',
          'Pensativo(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho7.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Impaciente ',
          'Desanimado(a)',
          'Sedutor(a)',
          'Aliviado(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho8.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Grato(a)', 'Sonhador(a)', 'Desanimado(a)', 'Chocado(a)'],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho9.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Satisfeito(a)',
          'Preocupado(a)',
          'Afetuoso(a)',
          'Indiferente'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho10.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Amável', 'Arrependido(a)', 'Zangado(a)', 'Simpático(a)'],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho11.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Desconfortável',
          'Entediado(a)',
          'Confiante',
          'Impaciente'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho12.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': [
          'Arrependido(a)',
          'Nervoso(a)',
          'Divertido(a)',
          'Envergonhado(a)'
        ],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho13.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Amigável', 'Entretido(a)', 'Desconfiado(a)', 'Sedutor(a)'],
        'has_divider': true,
      },
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/olho14.png',
        'radioIsVisible': false,
        'options_columns_size': 2,
        'options': ['Preocupado(a)', 'Cauteloso(a)', 'Hostil', 'Divertido(a)']
      },
    ]
  },
  26: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': 'Responda as questões abaixo:',
    'options': [
      'Tem sentido muito medo de perder o controle ou enlouquecer?',
      'Para impedir o ganho de peso, há uso de laxantes, diuréticos ou outros medicamentos; jejum, vômitos autoinduzidos, ou exercício físico em excesso?',
      'Sente medo intenso de ganhar peso ou de engordar, ao ponto de não comer?',
      'Há ingestão persistente de substâncias não nutritivas tais como doces e/ou chocolates, durante um período mínimo de um mês?',
      'Você se irrita fácil, de forma que seu humor muda facilmente durante o dia?',
      'Já teve ataques ou crises de medo intenso nos quais se sentiu muito mal?',
    ],
  },
  27: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Qual das imagens abaixo completa a sequência a seguir?', //Titulo do card
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/intel_1.png',
        'mim_size_awnser': 1,
        'max_size_awnser': 1,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
          'assets/intel_1a.png',
          'assets/intel_1b.png',
          'assets/intel_1c.png',
          'assets/intel_1d.png',
          'assets/intel_1e.png',
          'assets/intel_1f.png'
        ],
      },
    ],
  },
  28: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': 'Responda as questões abaixo:',
    'options': [
      'Ultimamente tem arrancado o próprio cabelo de forma recorrente, resultando em perda de cabelo?',
      'Observou grande perda de interesse ou prazer em todas ou quase todas as atividades na maior parte do dia; sente-se triste, vazio, sem esperança?',
      'As situações sociais, tais como falar em público, quase sempre provocam medo ou ansiedade?',
      'Percebo que sou uma pessoa especial e único/a? Espero que um dia as pessoas possam reconhecer meu valor e a diferença que faço na vida delas.'
          'Tende a se enxergar como alguém socialmente incapaz, sem atrativos pessoais ou inferior aos outros?',
      'Possui dificuldade em iniciar projetos ou fazer as coisas sozinho (por falta de autoconfiança, em vez de falta de motivação ou energia)?',
    ],
  },
  29: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Complete as sequências a seguir:',
    'itens': [
      {
        'options_style':
            'textForm', // multiSelect,singleSelect,multiSelect,textForm
        'title': ['2, 4, 8, 16, ?'],
        'labelText': ["Seguência *"],
        'icons': [Icons.confirmation_num],
        'has_divider': true,
      },
      {
        'options_style':
            'textForm', // multiSelect,singleSelect,multiSelect,textForm
        'title': ['1, 3, 9, ?'],
        'labelText': ["Seguência *"],
        'icons': [Icons.confirmation_num],
        'has_divider': true,
      },
      {
        'options_style':
            'textForm', // multiSelect,singleSelect,multiSelect,textForm
        'title': ['3, 7, 11, 15, ? '],
        'labelText': ["Seguência *"],
        'icons': [Icons.confirmation_num],
        'has_divider': true,
      },
      {
        'options_style':
            'textForm', // multiSelect,singleSelect,multiSelect,textForm
        'title': ['32, 16, 8, ? '],
        'labelText': ["Seguência *"],
        'icons': [Icons.confirmation_num],
      },
    ],
  },
  30: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Observe as palavras a seguir:',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': """

    1) MUITOS    2) OCEANO    3) PEIXES    4) E

                5) TEM      6) O      7) PLANTAS 

Agora forme uma frase que faça sentido e contenha todas essas palavras. Marque a ordem correta:
""",
        'options_style': 'singleSelect', //multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 1,
        'options': [
          '1 - 4 - 6 - 2 - 5 - 3 - 7',
          '6 - 2 - 4 - 7 - 5 - 1 - 3',
          '5 - 1 - 3 - 4 - 6 - 7 - 2',
          '6 - 2 - 5 - 1 - 3 - 4 - 7',
          '7 - 4 - 3 - 5 - 1 - 2 - 6 '
        ],
      },
    ],
  },
  31: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': 'Responda as questões abaixo:',
    'options': [
      'Sente algo estranho dentro do seu corpo, e/ou movimentos, como se levasse um empurrão?',
      'Sente como se alguém lhe tocasse, beliscassem, batessem ou beijassem seu corpo?',
      'Sente movimentos no corpo, como se levasse um empurrão?',
      'Possui a sensação de falta de controle durante a alimentação; não consegue parar de comer ou controlar a quantidade que está ingerindo?',
      'Sente-se descansado e preparado para mais um dia, mesmo com apenas 3 horas de sono?',
      'Você com frequência tem dificuldade em manter-se concentrado durante a realização de tarefas ouatividades?',
      'Muitas vezes responde precipitadamente antes que as perguntas tenham sido completadas.',
    ],
  },
  32: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Preencha o campo a seguir com o nome da cidade e estado onde você está agora.',
    'itens': [
      {
        'icons': [Icons.location_city, Icons.location_history],
        'options_columns_size': 1,
        'options_style':
            'textForm', // multiSelect,singleSelect,multiSelect,textForm
        'labelText': ['CIDADE:', 'ESTADO:'],
      },
    ]
  },
  33: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': "Selecione qual o período do dia atual.",
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'options_columns_size': 1,
        'radioIsVisible': false,
        'options': [
          'Manhã: 6:00 às 11:59 horas',
          'Tarde: 12:00 às 17:59 horas',
          'Noite: 18:00 às 23:59 horas',
          'Madrugada: 00:00 às 05:59 horas',
        ]
      },
    ],
  },
  34: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Informações',
    'delay': 3,
    'itens':
        "Seis (6) imagens serão apresentadas. Fique atendo! Em um certo momento do teste, elas serão escondidas em uma figura e você deverá encontrá-las.",
  },
  35: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/CORREDOR.png', // body_type: image
      },
    ], // options_type: text
  },
  36: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/PAPAI NOEL.png', // body_type: image
      },
    ], // options_type: text
  },
  37: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/circo.png', // body_type: image
      },
    ], // options_type: text
  },
  38: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/mascara.png', // body_type: image
      },
    ], // options_type: text
  },
  39: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/NUMERO8.png', // body_type: image
      },
    ], // options_type: text
  },
  40: const {
    'hasProx': false,
    'isSendAnswer': false,
    'style': 'form',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/reciclagem.png', // body_type: image
      },
    ], // options_type: text
  },
  41: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': 'Responda as questões abaixo:',
    'options': [
      'Diariamente, há momentos em que você sente como o se chão oscilasse?',
      'Durante o dia há vários momentos em que você se sente irritadao e impaciente?',
      'Diariamente, há momentos em que você se sente muito feliz, irradiante?',
      'Durante o dia há vários momentos em que você se sente triste e/ou melancólico?',
      'Tem notado muita preocupação com um ou mais defeitos ou falhas percebidas na aparência física que não são observáveis ou que parecem leves para os outros.',
      'Você com frequência mexe de forma irrequieta as mãos e os pés ou remexe-se na cadeira quando está sentado?',
      'Exibe dificuldade em concordar com as ideias de outras pessoas, demonstrando inflexibilidade e rigidez tanto em relação a si mesmo quanto aos outros.',
    ],
  },
  42: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Encontre os objetos!',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body':
            'Seis (6) imagens foram apresentadas em algum momento do teste. Vamos encontrá-los? Clique nas figuras que você lembrou. Não é obrigado(a) a encontrar todas as imagens. Faça o seu melhor!\n',
      },
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'options_style': 'findImages',
        'options': [
          'assets/seisimagens.png',
        ]
      },
    ],
  },
  43: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Avalie e responda !!',
    'itens': [
      {
        'body': "assets/questao32.png",
        'body_hasFrame': true, //Imprime um quadro em volta do body
      },
      {
        'body':
            "Se possível, durante alguns minutos, imaginar ou tomar conhecimento de alguém ou algo através de uma abertura no tempo e espaço, qual das ações a seguir você escolheria? Selecione até duas opções que melhor se adequem a você.\n",
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'max_size_awnser': 2,
        'mim_size_awnser': 2,
        'options_columns_size': 1,
        'options_style': 'multiSelect', // singleSelect,multiSelect,textForm
        'options': [
          'Ver alguém que já morreu',
          'Ver uma pessoa nua',
          'Voltar na minha infância e recomeçar tudo',
          'Voltar na minha adolescência e recomeçar tudo',
          'Saber se meu namorado (a) ou esposo (a) está me traindo',
          'Saber como poderia ser o futuro da minha família e ajudá-los',
          'Desaparecer no tempo e espaço, ao entrar pela fenda',
          'Saber quem é minha alma gêmea',
          'Ver meu futuro profissional',
          'Saber como faço para não pensar coisas bizarras',
          'Saber se ficarei rico(a)',
          'Saber quem está me perseguindo na rua',
          'Não gostaria de ver ou saber de nada',
        ]
      },
    ],
  },
  44: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Percebe-se impulsivo e de forma abusiva; p. ex., gastos exagerados, sexo com desconhecidos, abuso de substâncias, dirigir de forma perigosa/irresponsável e/ou atos repetitivos de autolesão?',
      'Tem dificuldade em terminar o que começa?',
      'Quando você conta uma história que aconteceu, na maioria das vezes você exagera e dramatiza alguns detalhes?',
      'Já testemunhou e/ou ainda é exposto (a) de forma repetida ou extrema a detalhes aversivos do evento traumático?',
      'Você apresenta explosões de raiva recorrente, manifestadas por meio da linguagem (como insultos dirigidos a outras pessoas) ou através de ações (como agressão física)?',
      'Você está tendo insônia praticamente todos os dias?',
    ],
  },
  45: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atenção !!',
    'delay': 3,
    'itens': 'Atente-se ao som que será reproduzido na próxima tela.',
  },
  46: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': '',
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': "assets/audios/aguacorrente-edited_v2.mp3", // body_type: audio
      },
    ],
  },
  47: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Qual das opções corresponde ao som escutado?',
    'itens': [
      {
        'options_columns_size': 2,
        'radioIsVisible': false,
        'options': [
          "Pássaros",
          "Barulho de água",
          "Aspirador de pó",
          "Choro de criança",
          "Telefone tocando",
          "Sem som"
        ],
      },
    ],
  },
  48: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Observe a imagem e selecione qual alternativa corresponde ao que você vê.',
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        //'body_type':
        'body': "assets/Ebbinghaus.png", // body_type: image
        'radioIsVisible': false,
        'options_columns_size': 1,
        'options': [
          'A Reta A é maior que a Reta B',
          'A Reta A é menor que a Reta B',
          'Retas A e B, são do mesmo tamanho',
        ],
      },
    ],
  },
  49: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Responda !!',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'options_columns_size': 2,
        'radioIsVisible': false,
        'body':
            'Serão exibidos diversos pontos e ao clicar sobre estes pontos, você poderá compor imagens, uma vez que os pontos serão conectados por linhas retas. Escolha uma das sugestões fornecidas, selecionando a opção e inicie o processo de desenho. O tempo disponível é flexível, permitindo que você retorne ou apague conforme necessário.\n',
        'options': [
          'Avião',
          'Borboleta',
          'Casa',
          'Estrela',
          'Quadrado',
          'Não quero em fazer',
        ],
        'has_divider': false,
      },
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'options_style': 'dotLine',
        'options': ' ', // Quando for dotLine colar uma string com espaço
      },
    ],
  },
  50: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Você tem sentido mais fadiga ou perda de energia quase todos os dias?',
      'Você vivenciou algum evento traumático?',
      'Você tem escutado Zumbido no ouvido?',
      'Você tem dificuldades em jogar fora objetos usados ou sem valor, mesmo quando não têm valor sentimental. Ultimamente guarda muitas coisas, papeis, recibos, com a ideia de que poderá precisar algum dia?',
      'Você apresenta comportamentos repetitivos (p. ex., lavar as mãos, organizar, verificar) ou atos mentais (p. ex., orar, contar ou repetir palavras em silêncio).',
      'Você tem visto algo estranho como figuras, sombras, fogo, fantasmas, demônios, pessoas estranhas ou algo do tipo, no seu dia a dia?',
    ],
  },
  51: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Jogo dos 5 (cinco) erros',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body':
            'Serão apresentadas duas imagens em paralelo: uma considerada \'verdadeira\' e a outra \'falsa\'. Na segunda figura, há 5 alterações que você deve identificar, apontando as discrepâncias por meio de cliques nos locais correspondentes.\n',
      },
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'options_style': 'fiveErrors',
        'options': [
          'assets/five_errors1.jpg',
          'assets/five_errors2.jpg',
        ]
      },
    ],
  },
  52: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Nos últimos meses, você tem ouvido vozes de pessoas estranhas?',
      'As vozes são seu próprio pensamento em voz alta?',
      'Alguém tem desejado envenená-lo?',
      'Você tem dificuldade para relaxar? Está sempre ocupado?',
      'Você vem apresentando sensações de falta de ar ou sufocamento?',
      'Você está vivenciando um estado de luto prolongado e persistente, que se estende por um período superior a 12 meses, caracterizado por uma intensa saudade, preocupação e apatia em relação ao futuro?',
    ],
  },
  53: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': "Qual das imagens abaixo completa a sequência a seguir?",
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/intel_2.png',
        'mim_size_awnser': 1,
        'max_size_awnser': 1,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
          'assets/intel_2a.png',
          'assets/intel_2b.png',
          'assets/intel_2c.png',
          'assets/intel_2d.png',
          'assets/intel_2e.png',
          'assets/intel_2f.png'
        ],
      },
    ],
  },
  54: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Você tem-se irritado com mais facilidade que antes?',
      'Nos últimos meses você sente dificuldades de parar de se preocupar?',
      'Você pensa muitas coisas ao mesmo tempo?',
      'Você sente dificuldade em se concentrar?',
      'Evita realizar atividades profissionais ou estudantis que impliquem contato interpessoal, pois tem muito medo de críticas, desaprovação ou rejeição?',
      'Você não acha que tem fraquezas e muito menos evita ambientes, pois consegue tudo o que quer?',
    ],
  },
  55: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atenção !!',
    'delay': 3,
    'itens': "Na próxima tela será reproduzida algumas palavras. Fique atento.",
  },
  56: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/audios/quatro_palavras.mp3',
        'options_columns_size': 1,
      },
    ],
  },
  57: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Selecione 1 ou 2 imagens que poderia representar você ou seu jeito de ser.',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': '', // body_type: audio
        'mim_size_awnser': 1,
        'max_size_awnser': 2,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
          'assets/questao45leao.png',
          'assets/questao45coquetel.png',
          'assets/questao45humburgue.png',
          'assets/questao45gato.png',
          'assets/questao45carro.png',
          'assets/questao45cachorro.png',
          'assets/questao45passaro.png',
          'assets/questao45cerveja.png',
          'assets/questao45cocacola.png',
          'assets/questao45cafe.png',
          'assets/questao45bombons.png',
          'assets/questao45casa.png',
        ]
      },
    ],
  },
  58: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Você acredita que precisa fazer as coisas de forma perfeita, caso contrário não será aceito (a)? ',
      'Você acredita que as pessoas estão julgando suas atitudes e comportamentos, mesmo que não estejam dizendo?',
      'Você tem ideias negativas, como pensar em morrer?',
      'Você se sente inadequado (a) inquieto (a) e conversa de forma excessiva?',
      'Você costuma adiar ou evitar fazer as coisas até o último minuto? Possui o perfil de procrastinar?',
      'Tem relutado em delegar tarefas ou de trabalhar com outras pessoas, pois precisa estar no controle de tudo.',
      'Você percebe que se esforça de forma intensa para evitar ser abandonado (a)?',
    ],
  },
  59: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Responda de acordo com o som escutado anteriormente!!',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': 'Qual das opções corresponde ao som escutado?\n',
        'options_columns_size': 1,
        'radioIsVisible': false,
        'options': [
          "Rua - Madeira - Paz - Pastel",
          "Lua - Cadeira - Raiz - Chapéu",
          "Rua - Cadeira - Paz - Chapéu",
          "Lua - Cadeira - Paz - Pastel",
        ],
      },
    ],
  },
  60: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Dentre as opções abaixo marque a expressão que melhor corresponde a emoção básica descrita.',
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/questao48.png',
        'title': 'a) Nojo:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
      {
        'title': 'b)	Tristeza:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
      {
        'title': 'c)	Medo:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
      {
        'title': 'd)	Raiva:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
      {
        'title': 'e)	Alegria:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
      {
        'title': 'f)	Surpresa:',
        'options_columns_size': 6,
        'radioIsVisible': false,
        'options': [
          "1",
          "2",
          "3",
          "4",
          "5",
          "6",
        ],
        'has_divider': true,
      },
    ],
  },
  61: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atenção !!',
    'delay': 3,
    'itens':
        "Nas próximas 4 telas serão exibidas diversas expressões de diferentes sentimentos. Em cada tela, marque no mínimo 2 e no máximo 6 expressões que melhor correspondem como você tem se sentido nos últimos meses.",
  },
  62: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Selecione 1 a 3 imagens que poderia representar você ou seu jeito de ser.',
    'itens': [
      {
        'mim_size_awnser': 1,
        'max_size_awnser': 3,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
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
        ]
      },
    ],
  },
  63: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Selecione 1 a 3 imagens que poderia representar você ou seu jeito de ser.',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': '', // body_type: audio
        'mim_size_awnser': 1,
        'max_size_awnser': 3,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
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
        ]
      },
    ],
  },
  64: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Selecione 1 a 3 imagens que poderia representar você ou seu jeito de ser.',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': '', // body_type: audio
        'mim_size_awnser': 1,
        'max_size_awnser': 3,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
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
        ]
      },
    ],
  },
  65: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Selecione 1 a 3 imagens que poderia representar você ou seu jeito de ser.',
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body': '', // body_type: audio
        'mim_size_awnser': 1,
        'max_size_awnser': 3,
        'options_style':
            'multiSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 3,
        'options': [
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
        ]
      },
    ],
  },
  66: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Avalie e responda !!',
    'itens': [
      {
        'body':
            "Selecione as palavras que você mais gosta e, ao mesmo tempo, lhe descreveria. A quantidade é ilimitada, pode escolher quantas palavras quiser, desde que elas fazem sentido na sua vida.",
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'max_size_awnser': 65,
        'mim_size_awnser': 1,
        'options_columns_size': 2,
        'options_style': 'multiSelect', // singleSelect,multiSelect,textForm
        'options': [
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
        ]
      },
    ],
  },
  67: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Atenção !!',
    'delay': 3,
    'itens':
        "Na próxima tela será reproduzida uma lista de 10 pares de palavras relacionadas logicamente entre si (p. ex., alto-baixo). Depois, você será solicitado para preencher a palavra faltante.\n\nFique atento, você terá que memorizar todos os pares.\n\nQuando estiver pronto é so clicar em próximo...",
  },
  68: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'itens': [
      {
        'body_hasFrame': true, //Imprime um quadro em volta do body
        'body': 'assets/audios/dez_palavras.mp3',
        'options_columns_size': 1,
      },
    ],
  },
  69: {
    'hasProx': true,
    'isSendAnswer': true,
    'type': 'form',
    'header': "Complete com o par correspondente escutado anteriormente",
    'itens': [
      {
        'options_style': 'textForm',
        'options_columns_size': 1,
        'options': [
          'chuva -',
          'criança -',
          '- verão',
          'mostro -',
          '- água',
          'dinheiro -',
          '- pequeno',
          'livro -',
          '- móvel',
        ],
      },
    ],
  },
  70: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'yes_no',
    'header': "Responda as questões abaixo:",
    'options': [
      'Você se preocupa com a internet (pensa sobre atividades virtuais anteriores ou fica antecipando quando ocorrerá a próxima conexão)?',
      'Você sente necessidade de usar a internet por períodos cada vez maiores para se sentir satisfeito?',
      'Você já se esforçou repetidas vezes para controlar, diminuir ou parar de usar a internet, mas fracassou?',
      'Você fica inquieto, mal-humorado, deprimido ou irritável quando tenta diminuir, parar de usar a internet ou quando o uso é restringido?',
      'Você fica online mais tempo do que pretendia originalmente?',
      'Você já prejudicou ou correu o risco de perder um relacionamento significativo, emprego ou oportunidade educacional ou profissional por causa de internet?',
      'Você já mentiu para familiares, terapeutas ou outras pessoas para esconder a extensão do seu envolvimento com a internet?',
      'Você usa a internet como uma maneira de fugir de problemas ou de aliviar um humor desagradável (por exemplo, sentimento de impotência, solidão, culpa, tristeza, ansiedade, depressão)?',
    ],
  },
  71: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Com que frequência você pausa e consome estas substâncias?',
    'itens': [
      {
        'title': '1) Cafeina:',
        'options_columns_size': 1,
        'radioIsVisible': true,
        'options': [
          'Nunca ',
          'Uma vez por mês ou menos (raramente)',
          'Duas a quatro vezes ao mês (às vezes)',
          'Duas a três vezes por semana',
          'Na maioria dos dias ou sempre',
        ],
        'has_divider': true,
      },
      {
        'title': '2)	Álcool:',
        'radioIsVisible': true,
        'options_columns_size': 1,
        'options': [
          'Nunca ',
          'Uma vez por mês ou menos (raramente)',
          'Duas a quatro vezes ao mês (às vezes)',
          'Duas a três vezes por semana',
          'Na maioria dos dias ou sempre',
        ],
        'has_divider': true,
      },
      {
        'title': '3)	Tabaco:',
        'radioIsVisible': true,
        'options_columns_size': 1,
        'options': [
          'Nunca ',
          'Uma vez por mês ou menos (raramente)',
          'Duas a quatro vezes ao mês (às vezes)',
          'Duas a três vezes por semana',
          'Na maioria dos dias ou sempre',
        ],
        'has_divider': true,
      },
      {
        'title': '4)	Maconha:',
        'radioIsVisible': true,
        'options_columns_size': 1,
        'options': [
          'Nunca ',
          'Uma vez por mês ou menos (raramente)',
          'Duas a quatro vezes ao mês (às vezes)',
          'Duas a três vezes por semana',
          'Na maioria dos dias ou sempre',
        ],
        'has_divider': true,
      },
      {
        'title': '5)	Cocaína/crack:',
        'radioIsVisible': true,
        'options_columns_size': 1,
        'options': [
          'Nunca ',
          'Uma vez por mês ou menos (raramente)',
          'Duas a quatro vezes ao mês (às vezes)',
          'Duas a três vezes por semana',
          'Na maioria dos dias ou sempre',
        ],
      },
    ],
  },
  72: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Escolha !!',
    'delay': 3,
    'itens': [
      {
        'body_hasFrame': false, //Imprime um quadro em volta do body
        'body':
            'Daltonismo é o termo usado para denominar a falta de sensibilidade ocular que algumas pessoas possuem na percepção de determinadas cores. Você tem Daltonismo? Já foi diagnosticado por um profissional especializado? Se sim, você pode optar por não realizar este teste; no entanto, se preferir tentar, isso não resultará em desvantagem. Basta clicar em \'SIM\' para prosseguir com a atividade.\n',
      },
      {
        'options_style':
            'singleSelect', //singleSelect,multiSelect,textForm,multiSelect
        'radioIsVisible': false,
        'options_columns_size': 3,
        'options': [
          'Sim',
          'Não',
          'Pular',
        ]
      },
    ],
  },
  /*
  73: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Falta Fazer',
    'delay': 3,
    'itens':
        'Marque a cor que você mais gosta e pinte os retângulos e os círculos das figuras abaixo.\n\nFaça da forma que mais te agrada.',
  },
*/
  73: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Encontre os objetos!',
    'itens': [
      {
        'body_hasFrame': false,
        'body':
            'Marque a cor que você mais gosta e pinte os retângulos e os círculos das figuras abaixo.\n\nFaça da forma que mais te agrada.\n',
        'options_style': 'arvoreCiculos',
        'options_columns_size': 3,
        'options': [
          'Azul',
          'Verde',
          'Laranja',
          'Amarelo',
          'Vermelho',
          'Rosa',
          'Marrom',
          'Preto',
          'Branco',
        ],
        'colors': [
          Colors.blue,
          Colors.green,
          Colors.orange,
          Colors.yellow,
          Colors.red,
          Colors.pink,
          Colors.grey,
          Colors.black,
          Colors.white24,
        ],
        'imagem': 'assets/arvore_circulos.png',
      },
    ],
  },
  74: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header': 'Selecione qual dia da semana é hoje:',
    'itens': [
      {
        'options_style':
            'singleSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 2,
        'options': [
          'Segunda-feira',
          'Terça-feira',
          'Quarta-feira',
          'Quinta-feira',
          'Sexta-feira',
          'Sábado',
          'Domingo',
        ]
      },
    ],
  },
  75: const {
    'hasProx': true,
    'isSendAnswer': true,
    'style': 'form',
    'header':
        'Quanto tempo, aproximadamente, você acha que investiu para fazer este teste?',
    'itens': [
      {
        'options_style':
            'singleSelect', //singleSelect,multiSelect,textForm,multiSelect
        'options_columns_size': 2,
        'options': [
          '5 minutos',
          '15 minutos',
          '30 minutos',
          '40 minutos',
          '60 minutos',
          'Mais que 1 hora',
        ]
      },
    ],
  },
  76: const {
    'hasProx': true,
    'isSendAnswer': false,
    'style': 'form',
    'header': 'Parabéns!!!!',
    'delay': 3,
    'itens':
        "Você terminou o questionário, agradeçemos muito pela sua disponibilidade.\n\nOBS.: Você ja pode fechar esta página.",
  },
};
