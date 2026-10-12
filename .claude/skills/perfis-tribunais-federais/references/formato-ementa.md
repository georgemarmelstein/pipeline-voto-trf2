# Formato de ementa: padrão estruturado do CNJ (default dos perfis)

> Valor do campo `formato_ementa` nos perfis: `cnj-estruturada`.
> Fonte das regras: o prompt especializado do ecossistema,
> `superjurista-produto/conteudo/prontos/prompts/escrita/ementa-cnj.md` (casa única do padrão de
> ementa CNJ). Este guia o adapta ao acórdão de 2º grau em regime de minuta limpa: mesmas regras de
> redação, sem markdown (o acórdão é documento de publicação). Mudou o prompt, mude este guia.
> O número e a data do ato normativo do CNJ NÃO são afirmados aqui.

## Ato normativo de origem

ato_normativo_cnj: A CONFERIR (número, data e redação do ato do CNJ que instituiu a ementa estruturada; conferir no portal oficial do CNJ antes de citar em qualquer documento)

## Estrutura e regras de redação

1. Cabeçalho (primeira linha do documento): começa com "EMENTA: " e segue com a verbetação TODA EM
   MAIÚSCULAS, em segmentos separados por ponto, nesta ordem:
   RAMO DO DIREITO. CLASSE PROCESSUAL. PALAVRAS-CHAVE DO ASSUNTO PRINCIPAL, DO MAIS GERAL AO MAIS
   ESPECÍFICO, CADA UMA SEGUIDA DE PONTO. CONCLUSÃO.
   A conclusão é o resultado em poucas palavras (ex.: RECURSO PROVIDO. / APELAÇÃO DESPROVIDA.).

2. I. CASO EM EXAME
   Item 1: o caso, com os fatos relevantes e o pedido principal (no 2º grau: a decisão recorrida,
   quem recorreu e o que pede), de forma objetiva e sintética. Um só item.

3. II. QUESTÃO EM DISCUSSÃO
   Uma questão: "A questão em discussão consiste em ...".
   Duas ou mais: "Há [número por extenso] questões em discussão: (i) definir se ...; (ii) estabelecer
   se ...; (iii) determinar se ...". Tudo num único item numerado.

4. III. RAZÕES DE DECIDIR
   Cada justificativa autônoma é um item numerado (a numeração continua a das seções anteriores).
   Redação concisa e objetiva; UMA ideia central por item; quantos itens forem necessários, na
   ordem do voto.

5. IV. DISPOSITIVO E TESE
   Item numerado com o resultado: "Recurso provido.", "Recurso desprovido.", "Recurso parcialmente
   provido.", "Recurso não conhecido." (ou a formulação adequada, ex.: "Apelação provida para ...").
   O resultado é idêntico ao dispositivo do voto.
   Em seguida, em linha própria: "Tese de julgamento: 1. [tese]. 2. [tese]." Cada tese é frase
   completa, com maiúscula inicial e ponto final; só as teses que o voto efetivamente firmou.

6. Blocos finais, cada um em linha própria:
   "Dispositivos relevantes citados: CF/1988, art. X; Lei nº Y/AAAA, art. Z; CPC, arts. W e V."
   Só as normas que o voto cita. Se o voto não citar nenhuma: "Dispositivos relevantes citados: não
   há menção expressa a dispositivos legais no voto."
   "Jurisprudência relevante citada: STF, [classe] nº [número], Rel. Min. [nome], j. [data]; STJ,
   Tema [n]; TRF2, [Turma], [classe] nº [número], Rel. [nome], j. [data]."
   Só os citáveis que o voto efetivamente cita, com os dados que constam do voto/citáveis (nunca
   completar relator ou data de memória). Se o voto não citar nenhum: "Jurisprudência relevante
   citada: não há menção expressa a precedentes no voto."

## Regras gerais

- Linguagem clara, objetiva e simples; sem juridiquês desnecessário.
- Nada na ementa que não esteja no voto: a ementa deriva do voto, não decide nem acrescenta.
- Regime de minuta limpa: sem markdown (nada de #, **, *, listas com hífen, régua), sem aspas de
  fonte, sem sinalizadores no corpo. O marcador [FIM_EMENTA] é removido na montagem do acórdão.
- Referências a precedentes seguem o contrato citáveis/praxe: o que não é citável não entra no bloco
  de jurisprudência.
- Proibido usar dado de exemplo: o esqueleto abaixo mostra só a forma.

## Variação por tribunal

default: cnj-estruturada para TRF1 a TRF6. Se o tribunal adotar modelo próprio de ementa, o campo formato_ementa do perfil indica `tribunal`, e o modelo local deve ser confirmado (A CONFERIR NO REGIMENTO) e fornecido ao redator, nunca presumido. Flag do pipeline: --perfil-ementa=cnj|tribunal.

## Esqueleto de referência (somente forma; nenhum dado é real)

EMENTA: RAMO DO DIREITO. CLASSE PROCESSUAL. ASSUNTO GERAL. ASSUNTO ESPECÍFICO. CONCLUSÃO.

I. CASO EM EXAME
1. Apelação interposta por [parte] contra sentença que [resultado], pedindo [pretensão recursal].

II. QUESTÃO EM DISCUSSÃO
2. Há duas questões em discussão: (i) definir se [questão]; (ii) estabelecer se [questão].

III. RAZÕES DE DECIDIR
3. [Justificativa autônoma 1.]
4. [Justificativa autônoma 2.]

IV. DISPOSITIVO E TESE
5. Recurso provido.
Tese de julgamento: 1. [Tese firmada no voto.]

Dispositivos relevantes citados: [normas citadas no voto].
Jurisprudência relevante citada: [citáveis citados no voto].
