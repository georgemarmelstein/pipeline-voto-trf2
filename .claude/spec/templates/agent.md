# Template: Agent (v2.0 - Arquitetura Modular)

> **Filosofia:** Agent = Capacidade atômica reutilizável. Define O QUE sabe fazer, não ONDE opera.
>
> **Copie para:** `.claude/agents/[nome-agent].md` ou `.claude/agents/[categoria]/[nome-agent].md`
>
> **Subpastas:** Permitidas por CATEGORIA (extracao/, revisao/, pesquisa/). Proibidas por PIPELINE.
>
> **Nota v3.0:** O CONTRATO do agente não muda. O que a v3.0 explicita é ONDE o output
> vive: o agente que grava o próprio artefato GRAVA o documento completo no caminho que o
> orquestrador injeta (Write) e responde ao orquestrador APENAS uma linha de status
> ("<etapa> OK | <arquivo>") — nunca ecoa o documento na resposta (L5). Os `<sinalizadores>`
> são as âncoras que um gate por script (`verificar_<sistema>.py`) confere NO ARQUIVO, não
> um texto para emoldurar uma resposta de chat. Essa disciplina de "gravar + responder 1
> linha" é reforçada pelo invólucro do orquestrador em cada etapa.

---

## Arquitetura de Duas Camadas

```
┌─────────────────────────────────────────────────────────────────┐
│  CAMADA 1: INSTRUÇÕES (estática)                                │
│  .claude/agents/analise-marmelstein.md                          │
│  → Define CAPACIDADE: "Sei analisar casos e classificar"        │
│  → NÃO conhece caminhos específicos                             │
├─────────────────────────────────────────────────────────────────┤
│  CAMADA 2: DADOS (dinâmica)                                     │
│  workspace/processo-XXX/                                        │
│  → Contém arquivos do processo específico                       │
│  → Orquestrador injeta caminho via $ARGUMENTS                   │
└─────────────────────────────────────────────────────────────────┘
```

**Princípio:** Agent é genérico. Orquestrador fornece contexto.

---

## Template

```markdown
---
name: [nome-do-agent]
description: [Descrição concisa - 1 linha]
tools: Read Write
model: sonnet
---

<identidade>
  <papel>[Definição do papel - quem é este agent]</papel>
  <estilo>[Estilo de execução - metódico, criativo, analítico, didático etc.]</estilo>
</identidade>

<capacidade>
  <habilidade>[O QUE este agent sabe fazer - verbo no infinitivo]</habilidade>
  <especializacao>[Em que área é especialista]</especializacao>
</capacidade>

<contrato>
  <entrada>
    <tipo>[Tipo de dado que espera receber: texto, relatório, lista, etc.]</tipo>
    <formato>[Formato esperado: TXT, MD, JSON, etc.]</formato>
    <requisitos>[O que a entrada DEVE conter para o agent funcionar]</requisitos>
  </entrada>

  <saida>
    <tipo>[Tipo de dado que produz: análise, classificação, relatório, etc.]</tipo>
    <formato>[Formato da saída: MD, TXT, etc.]</formato>
    <destino>Gravado em ARQUIVO (Write) no caminho injetado pelo orquestrador; a resposta ao orquestrador é UMA linha de status ("<etapa> OK | <arquivo>"), nunca o documento.</destino>
  </saida>
</contrato>

<restricoes>
  - NUNCA [restrição crítica que jamais pode ser violada]
  - NUNCA inventar ou alucinar informações não presentes na entrada
  - NÃO assumir caminhos de arquivo - recebe via contexto
  - NÃO imprimir o documento na resposta — ele vai no ARQUIVO (Write); responder só a linha de status (L5)
  - NÃO usar TodoWrite (exclusivo do orquestrador)
  - SEMPRE [obrigação que deve ser cumprida]
  - SEMPRE gravar o documento com os marcadores de início/fim (âncoras que o gate confere)
  - SEMPRE usar português com acentos corretos
</restricoes>

<contingencias>
  <se_entrada_insuficiente>[O que fazer se entrada não tiver dados necessários]</se_entrada_insuficiente>
  <se_ambiguo>[O que fazer se houver ambiguidade]</se_ambiguo>
</contingencias>

<formato_saida>
  <!-- O template abaixo descreve o DOCUMENTO GRAVADO EM ARQUIVO (Write), não a resposta de chat. -->
  <arquivo>
[SINALIZADOR_INICIO]

[SEÇÃO 1]
Conteúdo processado

[SEÇÃO 2]
Mais conteúdo

[SINALIZADOR_FIM]
  </arquivo>
  <resposta_ao_orquestrador>[NOME] OK | [caminho-do-arquivo]</resposta_ao_orquestrador>
</formato_saida>

<sinalizadores>
  <!-- Âncoras que VIVEM NO ARQUIVO e são conferidas por gate por script (verificar_<sistema>.py),
       não ecoadas inline. O motor normaliza acento/caixa, então escreva-as com acentos naturais. -->
  | Posição | Texto Obrigatório | Uso |
  |---------|-------------------|-----|
  | Início  | "[SINALIZADOR_INICIO]" | Abre o documento NO ARQUIVO (âncora do gate) |
  | Fim     | "[SINALIZADOR_FIM]" | Fecha o documento NO ARQUIVO (âncora do gate) |
</sinalizadores>

<instrucoes>
  <passo numero="1" nome="Receber entrada">
    Ler o conteúdo fornecido pelo orquestrador.
    → A entrada vem via contexto, não de caminho fixo.
  </passo>

  <passo numero="2" nome="[Nome do processamento]">
    [Instruções específicas do que fazer com a entrada]
  </passo>

  <passo numero="3" nome="Gravar o documento">
    Gerar o documento no formato especificado e GRAVAR (Write) no caminho injetado pelo
    orquestrador, com os marcadores de início/fim.
    → O destino é definido pelo orquestrador, não por este agent.
  </passo>

  <passo numero="4" nome="Responder status">
    Autovalidar marcadores/acentos e responder ao orquestrador APENAS uma linha:
    "[NOME] OK | [caminho-do-arquivo]".
    → NÃO imprimir o documento na resposta (L5) — ele vive no ARQUIVO.
  </passo>
</instrucoes>

<exemplos>

### Entrada Típica

```
[Exemplo do tipo de conteúdo que este agent processa]
```

### Documento Gravado no Arquivo (Write)

```
[SINALIZADOR_INICIO]

[Exemplo de saída seguindo formato_saida]

[SINALIZADOR_FIM]
```

### Resposta ao Orquestrador (1 linha, o documento NÃO é ecoado)

```
[NOME] OK | [caminho-do-arquivo]
```

</exemplos>
```

---

## Como o Orquestrador Usa Este Agent

O agent **não sabe** de onde vem a entrada nem para onde vai a saída. O orquestrador injeta isso via `$ARGUMENTS`:

```xml
<prompt_subagente tipo="ANÁLISE">
  <execucao>
    <passo numero="1" nome="Ler instruções">
      Read: .claude/agents/analise-marmelstein.md
      → Este arquivo define a CAPACIDADE.
    </passo>

    <passo numero="2" nome="Ler entrada">
      Read: $ARGUMENTS/relatorio.md
      → $ARGUMENTS = caminho do workspace (ex: workspace/processo-123)
    </passo>

    <passo numero="3" nome="Executar">
      → Aplicar a capacidade do agent à entrada lida.
    </passo>

    <passo numero="4" nome="Gravar e responder status">
      Write: $ARGUMENTS/analise/marmelstein.md   → Orquestrador define o destino.
      Responder APENAS: "marmelstein OK | analise/marmelstein.md" — NÃO imprimir o documento (L5).
    </passo>
  </execucao>
</prompt_subagente>
```

**Resultado:** Mesmo agent pode processar `processo-123`, `processo-456`, etc.

---

## Guia de Preenchimento

### YAML Frontmatter

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `name` | Sim | Identificador único, kebab-case |
| `description` | Sim | Uma linha descrevendo a CAPACIDADE |
| `tools` | Sim | Lista separada por espaço: `Read Write Glob Grep Bash` |
| `model` | Sim | `haiku`, `sonnet`, `opus` - ver regra abaixo |
| `color` | Sim | Cor semântica por categoria - ver tabela abaixo |

### Regra de Seleção de Modelo (v3.3 — sonnet por padrão, opus a pedido)

**O padrão do sistema é `sonnet`.** Nenhum agente nasce em `opus`: a matéria ser
jurídica NÃO é, por si, razão de escalada — a regra antiga ("tarefa jurídica → opus")
empacotava extração e fundamentação na mesma linha e punha Opus para catalogar atos
processuais. O que decide a faixa é a NATUREZA COGNITIVA da tarefa, não o assunto.

| Faixa | Modelo padrão | Promovível? | Natureza da tarefa | Exemplos |
|-------|---------------|-------------|--------------------|----------|
| **Operacional** | `haiku` | Não | Executar script pronto, merge, formatação, validação determinística. A decisão já está no código. | executor-de-scripts, planejador-download |
| **Extração / Coleta** | `sonnet` | Não | Ler, localizar, catalogar, estruturar, buscar e transcrever fielmente. Fidelidade importa; julgamento não entra. | linha-tempo-processual, relator-marmelstein, pesquisador-*, inventariador-probatica, cartografo-de-autos, indexador-de-pecas, triador-processual |
| **Raciocínio** | `sonnet` | **Sim → `opus`** | Decidir, fundamentar, sustentar tese adversarial, sintetizar posições em conflito, refutar. O resultado depende de julgamento. | executor-analise, fundamentador-marmelstein, acusador/defensor-probatico, juiz-mediador, juiz-parafrase, auditor-enfrentamento, verificador-de-fidelidade |

**Promoção a `opus` (a pedido):** agentes da faixa **Raciocínio** trazem uma tag `<faixa>`
no CORPO (logo após o frontmatter) declarando-se promovíveis. Rodam em `sonnet` por padrão;
sobem a `opus` quando o orquestrador recebe a flag `--opus` e passa `model: opus` no
parâmetro da Task. Agentes das faixas Operacional e Extração NÃO são promovíveis — escalar
quem transcreve não melhora a transcrição, só encarece.

> **Por que no corpo e não no frontmatter:** o frontmatter de agente é lido pelo carregador
> do Claude Code, e os agentes oficiais usam exatamente cinco campos (`name`, `description`,
> `tools`, `model`, `color`). Chave nova ali é aposta desnecessária num parser que não
> controlamos; a tag XML no corpo é o veículo que a própria spec já usa para tudo mais.

```markdown
<faixa>Raciocinio — promovivel a opus. Roda em sonnet por padrao; sobe a opus
quando o orquestrador recebe a flag --opus e passa `model: opus` no parametro da
Task. Ver a Regra de Selecao de Modelo v3.3 em .claude/spec/templates/agent.md.</faixa>
```

**Por que promovível ≠ promovido:** a faixa Raciocínio é onde o Opus poderia render, não
onde ele é obrigatório. O padrão continua `sonnet`; `--opus` é o pedido explícito do usuário
para casos difíceis (tese controvertida, prova complexa, processo de grande porte).

**Como o modelo chega ao subagente — as duas rotas, e por que isso importa:**

| Rota de despacho | Quem decide o modelo |
|------------------|----------------------|
| `subagent_type: <agente-customizado>` | O `model:` do frontmatter do agente |
| Invólucro genérico (`Read: .claude/agents/x.md`) | **O parâmetro `model` da Task** — o frontmatter NÃO é lido |

Como os pipelines despacham majoritariamente por invólucro, **o orquestrador é obrigado a
passar `model:` explicitamente em toda Task**. Sem o parâmetro, o subagente herda o modelo
da sessão (tipicamente Opus) e o `model:` do frontmatter vira decoração. Anotação em prosa
do tipo `Task (sonnet)` não basta: tem de ser parâmetro.

### Cores Semânticas (Convenção Anthropic)

| Cor | Semântica | Categorias | Exemplo de Agent |
|-----|-----------|------------|------------------|
| `yellow` | Exploração, investigação | extracao, analise, pesquisa | linha-tempo, analisador, pesquisador |
| `green` | Construção, design | redacao | fundamentador, redator |
| `red` | Revisão crítica | revisao | advogado-diabo, revisor |
| `blue` | Propósito geral | (neutro) | - |
| `purple` | Documentação | (informativo) | - |
| `orange` | Refatoração | (transformação) | - |

### Tags XML - Mapeamento

| Tag | Obrigatória | Propósito |
|-----|-------------|-----------|
| `<identidade>` | Sim | QUEM é o agent |
| `<capacidade>` | Sim | O QUE sabe fazer (habilidade atômica) |
| `<contrato>` | Sim | Entrada esperada + Saída produzida (com `<destino>`: arquivo + 1 linha) |
| `<restricoes>` | Sim | O que NÃO pode fazer (inclui "NÃO imprimir o documento inline" — L5) |
| `<contingencias>` | Sim | O que fazer se falhar |
| `<formato_saida>` | Sim | Descreve o DOCUMENTO gravado em arquivo + a resposta de 1 linha ao orquestrador |
| `<sinalizadores>` | Sim | Âncoras que vivem NO ARQUIVO, conferidas por gate por script (não inline) |
| `<instrucoes>` | Sim | Passos numerados; o passo de saída GRAVA e responde 1 linha |
| `<exemplos>` | Recomendado | Entrada/saída típicas |

### Diferença v1 → v2

| Aspecto | v1 (Acoplado) | v2 (Modular) |
|---------|---------------|--------------|
| Caminhos | Hardcoded no agent | Injetados via $ARGUMENTS |
| Reutilização | Difícil (amarrado a pipeline) | Fácil (capacidade genérica) |
| Entrada/Saída | "Leia de X, escreva em Y" | "Espero tipo X, produzo tipo Y" |
| Contexto | Agent sabe tudo | Agent sabe sua capacidade, orquestrador sabe o contexto |

### Checklist de Validação

```
CRÍTICO:
[ ] YAML frontmatter completo (name, description, tools, model)?
[ ] Tools separadas por espaço (não vírgula)?
[ ] Localização: raiz ou subpasta por CATEGORIA (não pipeline)?
[ ] <capacidade> descreve habilidade atômica?
[ ] <contrato> define tipos (não caminhos)?
[ ] NENHUM caminho hardcoded no arquivo?

ALTO:
[ ] <identidade> com <papel> e <estilo>?
[ ] Restrições incluem "NÃO assumir caminhos"?
[ ] Restrições incluem "NÃO imprimir o documento na resposta" (L5)?
[ ] <contrato><saida> tem <destino> (grava em arquivo + resposta de 1 linha)?
[ ] <contingencias> com ações para falhas?
[ ] <instrucoes> usa passos numerados com <passo>? (passo de saída GRAVA e responde 1 linha)

RECOMENDADO:
[ ] <formato_saida> descreve o DOCUMENTO gravado + a resposta de 1 linha?
[ ] Sinalizadores declarados como âncoras do gate (vivem no arquivo)?
[ ] Exemplos mostram entrada/saída típicas?
```

> **Validação completa:** Ver `.claude/spec/referencias/checklist-validacao-agent.md`
