---
name: disciplina-devolutividade-recursal
description: >
  Use when uma análise ou voto de 2º grau vai decidir apelação, agravo ou remessa necessária e há risco de ir além do que foi devolvido: piorar a situação do único recorrente, decidir capítulo não impugnado, conhecer de inovação recursal ou matéria preclusa, ou omitir capítulo impugnado.
  Keywords: efeito devolutivo, tantum devolutum quantum appellatum, reformatio in peius, art. 1.013 CPC, capítulo não impugnado, trânsito parcial, inovação recursal, matéria de ordem pública, causa madura, remessa necessária, Súmula 45 do STJ.
---

<identidade>
  <papel>Disciplina de contenção do julgamento recursal: mede, capítulo por capítulo, o que o recurso (ou a remessa necessária) efetivamente devolveu ao tribunal e impede que a análise ou o voto ultrapasse esse perímetro.</papel>
  <dominio>Teoria dos recursos cíveis no CPC: efeito devolutivo (extensão e profundidade), proibição de reforma para pior, coisa julgada parcial, inovação recursal, cognição de ofício, causa madura e remessa necessária.</dominio>
</identidade>

<proposito>
  <objetivo>Fornecer o procedimento de checagem por capítulo que o analisador-recursal aplica antes de propor resultado e que o verificador-coerencia-acordao reaplica sobre o acórdão minutado.</objetivo>
  <razao>O erro típico do 2º grau é a justiça material fora do perímetro: o julgador vê um direito não pleiteado em recurso, ou um erro da sentença que favorece o recorrente, e o corrige. O resultado é acórdão nulo ou reformável por extrapolar o devolvido. A disciplina troca a intuição de justiça pelo mapa do que foi devolvido.</razao>
</proposito>

<quando_usar>
  <gatilhos>
    - Análise recursal ou voto sobre apelação, agravo de instrumento, agravo interno ou remessa necessária
    - Sentença com vários capítulos (mérito, consectários, honorários, custas, tutela) e recurso parcial
    - Recurso de apenas uma das partes, com tentação de corrigir também o que favorece a outra
    - Matéria nova nas razões recursais; matéria de ordem pública surgida só no tribunal
    - Reforma de sentença terminativa, de prescrição ou de decadência, com possível julgamento imediato do mérito
    - Fazenda Pública vencida, com ou sem recurso, e dúvida sobre remessa necessária
    - Keywords: efeito devolutivo, reformatio in peius, capítulo não impugnado, inovação recursal, causa madura
  </gatilhos>
  <exclusoes>
    - NÃO usar para embargos de declaração (vão ao pipeline de embargos) nem para recursos de natureza extraordinária, cujo perímetro de cognição é outro
    - NÃO usar na admissibilidade pura (tempestividade, preparo): a disciplina começa depois do conhecimento
    - NÃO usar para decidir o mérito de um capítulo: ela diz se o capítulo pode ser decidido, não como
  </exclusoes>
</quando_usar>

<instrucoes>
  <passo numero="1" nome="Decompor a decisão recorrida em capítulos">
    Liste cada capítulo autônomo da sentença ou decisão: cada pedido julgado, cada preliminar rejeitada ou acolhida, tutela, consectários (correção, juros), honorários, custas, e, se houver, a submissão à remessa necessária. Capítulos acessórios (honorários, consectários) ficam ligados ao principal de que dependem. CRITÉRIO DE PARADA: toda a parte dispositiva da sentença está mapeada, sem sobra.
  </passo>

  <passo numero="2" nome="Mapear quem impugnou o quê">
    Para cada recurso: recorrente, capítulos atacados, pedido recursal (reforma, anulação, integração), fundamentos. Ler o pedido e as razões, não só o rótulo do recurso. Anotar recurso adesivo, recurso de litisconsorte e a distinção entre recurso total e parcial. CRITÉRIO DE PARADA: cada capítulo recebe uma das marcas IMPUGNADO, NÃO IMPUGNADO ou SUBMETIDO À REMESSA, com a peça e a página que a sustenta. Sem ancoragem, marcar [VERIFICAR].
  </passo>

  <passo numero="3" nome="Fixar a extensão (o que é devolvido)">
    Capítulo NÃO IMPUGNADO e sem remessa: fora do perímetro. Opera trânsito em julgado parcial; o tribunal não o reexamina, nem para melhorar, nem para piorar. Capítulo IMPUGNADO: devolvido. Consequências do vínculo de dependência: reformado o principal, o acessório que dele depende acompanha o resultado, ainda que não impugnado de modo autônomo. CRITÉRIO DE PARADA: a matriz capítulo × status está completa e coerente com a seção 1 (matriz capítulo × status) de references/checklist-por-capitulo.md.
  </passo>

  <passo numero="4" nome="Fixar a profundidade (com que material)">
    Dentro do capítulo devolvido, o tribunal examina as questões suscitadas e discutidas no processo, mesmo as que a sentença não apreciou, e os demais fundamentos de pedido ou defesa quando a sentença acolheu um só (art. 1.013, §§ 1º e 2º). A profundidade não cria capítulo novo: não permite acolher pedido que a sentença não decidiu e que ninguém devolveu fora das hipóteses do § 3º. CRITÉRIO DE PARADA: cada questão que o resultado proposto usa está ligada a um capítulo devolvido.
  </passo>

  <passo numero="5" nome="Testar inovação recursal">
    Questão de fato que aparece pela primeira vez no recurso só entra com prova de que não foi suscitada antes por motivo de força maior (art. 1.014); superveniência documentada é outra via. Pedido novo é vedado pela estabilização da demanda (o recurso não amplia o objeto do processo). Fundamento jurídico novo é questão de direito: em regra pode ser examinado dentro do capítulo devolvido, observado o contraditório prévio e o passo 6. CRITÉRIO DE PARADA: toda matéria nova está classificada como (a) não conhecida por inovação, (b) conhecida por superveniência comprovada ou (c) conhecida de ofício com os limites do passo 6.
  </passo>

  <passo numero="6" nome="Testar o que se conhece de ofício">
    Exemplos de matéria conhecível de ofício: pressupostos processuais, legitimidade e interesse processual, nulidades absolutas, incompetência absoluta, prescrição e decadência, consectários legais de correção e juros. LIMITES: (i) a cognição de ofício opera dentro de capítulo devolvido; não ressuscita capítulo transitado; (ii) o contraditório prévio é exigido mesmo para o que é de ofício (arts. 10 e 933): se o fundamento não foi debatido, o voto propõe intimação das partes antes de decidir; (iii) a cognição de ofício não é salvo-conduto para piorar a situação do recorrente exclusivo, ponto sobre o qual a doutrina diverge; na dúvida, o resultado que agrava vai a ESCALAR (ver passo 7). CRITÉRIO DE PARADA: cada matéria de ofício tem seu capítulo de apoio, a decisão sobre o contraditório prévio e o efeito sobre o recorrente medido.
  </passo>

  <passo numero="7" nome="Testar a reforma para pior">
    Compare a situação do recorrente com e sem o resultado proposto. Se o resultado deixa o único recorrente em posição pior do que a da sentença, a proposta é vedada. Atenção aos disfarces: majorar condenação por via de consectário, retirar benefício concedido em capítulo não impugnado, inverter sucumbência, afastar compensação, alterar termo inicial em desfavor de quem recorreu sozinho. Exceção estrutural: se a outra parte também recorreu (ou aderiu), o capítulo por ela atacado pode ser reformado em seu favor. CRITÉRIO DE PARADA: para cada recorrente, o resultado proposto é igual ou melhor do que a sentença nos capítulos que ele devolveu, ou a hipótese de recurso da outra parte está documentada.
  </passo>

  <passo numero="8" nome="Avaliar a causa madura">
    Ao reformar ou anular, o tribunal pode julgar o mérito de imediato (art. 1.013, § 3º) quando: reformar sentença terminativa; anular sentença por incongruência com pedido ou causa de pedir; constatar omissão em pedido; anular por falta de fundamentação. O § 4º permite igual saída ao afastar prescrição ou decadência. Condição prática: a causa precisa estar em condições (provas suficientes, contraditório exercido sobre o mérito). Se falta prova ou o mérito não foi debatido, determinar retorno à origem. Na causa madura o perímetro do mérito é o do pedido inicial, não o da vontade do julgador. CRITÉRIO DE PARADA: decisão registrada (julgar o mérito ou devolver) com a justificativa de maturidade.
  </passo>

  <passo numero="9" nome="Tratar a remessa necessária">
    Quando a sentença é desfavorável à Fazenda nos casos do art. 496, o capítulo condenatório é submetido ao tribunal ainda que não haja recurso. Verificar: (i) se a hipótese se enquadra na remessa; (ii) as dispensas por valor da condenação e por conformidade com precedente obrigatório (art. 496, §§ 3º e 4º; os valores de cada faixa se conferem no texto atual do artigo); (iii) a Súmula 45 do STJ, que veda ao tribunal agravar, em remessa, a condenação imposta à Fazenda: sem recurso da parte contrária, a condenação não cresce. A remessa devolve o capítulo desfavorável à Fazenda; não devolve os capítulos que lhe foram favoráveis e não impugnados, nem autoriza piorar o que só a remessa devolveu. Se há apelação do particular, a regra de agravamento segue o perímetro daquela apelação. Texto e vigência da Súmula 45: conferir pela ferramenta de precedentes antes de citá-la em minuta; na análise interna, registrar como [VERIFICAR] até a conferência. CRITÉRIO DE PARADA: remessa classificada como cabível, dispensada ou inexistente, com limite de agravamento registrado.
  </passo>

  <passo numero="10" nome="Fechar com consectários recursais">
    Honorários recursais (art. 85, § 11) dependem de recurso conhecido e não provido ou de recurso inadmitido, e respeitam os limites do art. 85. Conferir quem os suportaria e se há recurso que os justifique. Em remessa pura, sem recurso, não há recurso a majorar. CRITÉRIO DE PARADA: consectários fixados ou dispensados com motivo.
  </passo>

  <passo numero="11" nome="Emitir a matriz e o parecer de perímetro">
    Produzir a matriz do references/checklist-por-capitulo.md e o parecer: o que será decidido, o que está fora do perímetro e as observações extra dispositivo (ver restrições). CRITÉRIO DE PARADA: nenhum capítulo devolvido sem decisão (Iron Law 3), nenhum capítulo fora do perímetro dentro do dispositivo.
  </passo>
</instrucoes>

<uso_pelos_agentes>
  <analisador_recursal>Executa os passos 1 a 11 ANTES de propor resultado e inclui a matriz na análise. Se o resultado ótimo exigir ultrapassar o perímetro, não o adota: registra a observação fora do dispositivo e, se a dúvida for jurídica real (passo 6, iii), fecha com ESCALAR.</analisador_recursal>
  <verificador_coerencia_acordao>Reaplica a matriz ao acórdão minutado: lê o dispositivo do voto e da ementa, cruza com a matriz da análise aprovada e aponta (a) capítulo devolvido não decidido, (b) capítulo decidido fora do perímetro, (c) agravamento da posição do recorrente exclusivo, (d) matéria nova conhecida sem base, (e) discrepância entre dispositivo do voto e parte final da ementa. Cada achado cita o capítulo e a página. Não reescreve.</verificador_coerencia_acordao>
</uso_pelos_agentes>

<restricoes>
  <nunca>
    - Decidir capítulo que ninguém impugnou e que não foi submetido à remessa, ainda que o resultado seja "justo"
    - Agravar a situação do único recorrente, direta ou por consectário
    - Agravar a condenação da Fazenda em remessa sem recurso da parte contrária
    - Conhecer de fato novo sem enquadrá-lo no art. 1.014, de pedido novo, ou de matéria de ofício sem contraditório prévio
    - Deixar de decidir capítulo impugnado, mesmo que o resultado dependa de pressuposto não preenchido: então decide-se o que o pressuposto permite e justifica-se o resto
    - Julgar a causa madura sem prova ou contraditório suficientes
    - Citar julgado para sustentar o perímetro sem verificação; a disciplina se apoia em dispositivos do CPC (Iron Law 1)
    - Transcrever texto legal entre aspas na minuta: no regime de dois tempos, a redação é limpa e a verificação é feita na análise
  </nunca>
  <sempre>
    - Ancorar cada marca IMPUGNADO/NÃO IMPUGNADO em peça e página
    - Registrar o que ficou fora do perímetro como observação fora do dispositivo, curta e neutra, sem efeito decisório
    - Usar [VERIFICAR: afirmação] para a Súmula 45 e para qualquer enunciado que ainda não tenha sido conferido
    - Escrever em português com acentos, voz institucional neutra
  </sempre>
  <red_flags>
    Se você pensa em qualquer das frases da tabela de racionalizações abaixo, PARE. A skill existe para este momento.
    - "O juiz quer justiça material, aproveite e reconheça também o direito do autor."
    - "Está tudo nos autos, não custa corrigir."
    - "É matéria de ordem pública, posso conhecer de qualquer jeito."
    - "A parte não recorreu disso, mas o erro é evidente."
    - "O recorrente é só um, mas a sentença errou contra ele em outro ponto que ele não atacou."
    - "A remessa devolve tudo, posso aumentar a condenação."
    - "O voto fica mais completo se eu decidir esse capítulo também."
    - Qualquer proposta de dispositivo que melhore a situação de quem não recorreu.
  </red_flags>

  <racionalizacoes>
    | Desculpa | Por que é errada | Resposta correta |
    |----------|------------------|------------------|
    | "O juiz quer justiça material; reconheça o período especial a favor do autor, que não recorreu" | O capítulo do autor não foi impugnado e transitou parcialmente; a apelação do réu devolve só os capítulos que o réu atacou. Julgar além devolve ao autor um capítulo que ele deixou precluir | Limitar-se aos capítulos impugnados pelo réu; registrar o ponto como observação fora do dispositivo, sem efeito |
    | "Está tudo nos autos" | A existência da prova não amplia o perímetro. Profundidade serve ao capítulo devolvido, não cria capítulo | Usar a prova só nos capítulos devolvidos |
    | "É ordem pública, conheço de ofício" | De ofício conhece-se dentro do capítulo devolvido, com contraditório prévio, e sem violar a vedação de piorar o recorrente exclusivo | Verificar passo 6; se o fundamento não foi debatido, propor intimação; se agrava, ESCALAR |
    | "O erro é evidente, corrijo" | A evidência do erro não legitima reforma de capítulo não impugnado | Observação fora do dispositivo |
    | "A remessa devolve tudo, aumento a condenação" | A remessa devolve o capítulo desfavorável à Fazenda, e a Súmula 45 do STJ [VERIFICAR] veda o agravamento sem recurso da parte contrária (conferir antes de citar, passo 9) | Confirmar, reduzir ou manter; nunca agravar |
    | "Decidir o capítulo a mais deixa o voto mais completo" | Completude não é critério de competência; capítulo fora do perímetro é nulo ou reformável | Dispositivo restrito ao devolvido |
    | "A causa está madura, julgo o mérito" | Maturidade exige hipótese do § 3º ou § 4º do art. 1.013, prova suficiente e contraditório exercido | Se faltar, devolver à origem |
    | "Fato novo muda tudo" | Fato novo no recurso é inovação, salvo força maior comprovada ou superveniência documentada | Aplicar passo 5 |
  </racionalizacoes>
</restricoes>

<casos_de_borda>
  <caso nome="Recurso de ambas as partes">
    <solucao>Cada recorrente tem seu perímetro. O capítulo atacado pela outra parte pode ser reformado em favor dela. Montar a matriz com duas colunas de recorrente.</solucao>
  </caso>
  <caso nome="Capítulo principal reformado, acessório não impugnado">
    <solucao>Honorários e consectários que dependem do principal acompanham o novo resultado; registrar a dependência na matriz.</solucao>
  </caso>
  <caso nome="Litisconsórcio">
    <solucao>Recurso de um litisconsorte aproveita ao outro apenas nas hipóteses do art. 1.005 (unitário ou solidariedade com defesa comum). Fora dessas, vale o perímetro individual.</solucao>
  </caso>
  <caso nome="Pedido do recurso mais amplo do que as razões">
    <solucao>Interpretar o recurso pelo conjunto, mas não suprir omissão de razões; capítulo sem fundamento de ataque conta como não devolvido com [VERIFICAR] e vai ao relatório da análise.</solucao>
  </caso>
  <caso nome="Sentença nula por incongruência">
    <solucao>Decretada a nulidade, avaliar o art. 1.013, § 3º, II; o mérito julgado no tribunal fica restrito ao pedido e à causa de pedir originais.</solucao>
  </caso>
</casos_de_borda>

<referencias>
  - references/checklist-por-capitulo.md — modelo de matriz capítulo × status, sinais de agravamento disfarçado e roteiro de reconferência do verificador
</referencias>
