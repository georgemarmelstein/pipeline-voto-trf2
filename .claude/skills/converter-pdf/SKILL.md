---
name: converter-pdf
description: Converte PDFs judiciais para TXT via OCR. Use com /baixar-converter.
context: fork
agent: executor-de-scripts
allowed-tools: Bash, Read, Write
---

# Converter PDF para Texto

REGRA ABSOLUTA: Execute o script existente. NAO crie codigo novo.

## Script

```bash
python .claude/skills/converter-pdf/scripts/pdf_para_txt.py \
  --input CAMINHO_PDF \
  --output DIRETORIO_SAIDA
```

## Argumentos

| Argumento | Obrigatorio | Descricao |
|-----------|-------------|-----------|
| `--input` | Sim | Arquivo PDF ou diretorio |
| `--output` | Nao | Diretorio de saida (padrao: ./textos) |
| `--limite` | Nao | Maximo de arquivos (0 = todos) |
| `--digital` | Nao | Usar pdfplumber ao inves de OCR (PROIBIDO p/ processo judicial: perde paginas escaneadas) |
| `--strict-ocr` | Nao | Falha se o OCR quebrar, em vez de cair para extracao digital (recomendado nos pipelines) |

Exit code: 0 = tudo OK; 1 = alguma conversao falhou. Se o OCR quebrar SEM `--strict-ocr`,
o fallback digital imprime `[AVISO]` e grava `"usou_ocr": false` no `conversao_log.json` —
checar isso e obrigacao do checkpoint do pipeline.

## Limites operacionais (OCR em escala)

O OCR roda em JANELAS de paginas com pool de threads. O pico de RAM e CONSTANTE
(~`jobs` x 2 x 6,5 MB), NAO cresce com o tamanho do PDF:

| Medida (150 DPI, medida em i9-13980HX) | Valor |
|----------------------------------------|-------|
| RAM por pagina renderizada | 6,5 MB (1240x1755 RGB) |
| OCR por pagina | ~0,96 s em 1 thread |
| Render por pagina | ~0,07 s (7% do custo; o OCR e 93%) |
| Pico de RAM, `--jobs 12` | ~160 MB, para PDF de qualquer tamanho |

- `--jobs N` controla os workers (padrao: nucleos-2, teto 12). Pico de RAM e
  velocidade escalam com N.
- **O teto antigo de "no maximo 2 conversoes simultaneas" NAO vale mais.** Ele
  existia porque o desenho anterior carregava o PDF INTEIRO em RAM (~6,5 GB num
  processo de 1000 paginas), o que jogava maquinas de 16GB no swap. Com janelas,
  varias conversoes simultaneas cabem — o limite agora e CPU, nao memoria.
- Rodando N conversoes em paralelo, dividir os workers: `--jobs (nucleos-2)/N`.
  Somar mais processos tesseract que nucleos so aumenta a disputa.
- PDFs gigantes seguem sem timeout: 1000 paginas com `--jobs 12` levam ~1,5 min,
  mas OCR e I/O-sensivel e a estimativa varia com a qualidade do escaneamento.

## Exemplos

### Converter um PDF
```bash
python .claude/skills/converter-pdf/scripts/pdf_para_txt.py \
  --input data/sentenca/0000009-99.2015.4.05.8100/0000009-99.2015.4.05.8100.pdf \
  --output data/sentenca/0000009-99.2015.4.05.8100/
```

### Converter em lote
```bash
python .claude/skills/converter-pdf/scripts/pdf_para_txt.py \
  --input data/sentenca/ \
  --output data/sentenca/ \
  --limite 10
```

### PDF digital (mais rapido)
```bash
python .claude/skills/converter-pdf/scripts/pdf_para_txt.py \
  --input documento.pdf \
  --output ./textos \
  --digital
```

## Retorno Esperado

Retorne APENAS:
- Status (sucesso/erro)
- Caminho do arquivo TXT gerado
- Estatisticas resumidas (paginas, caracteres, reducao %)

NAO inclua:
- Output completo do script
- Conteudo do texto extraido

## Documentacao

Para casos de borda e detalhes tecnicos, consulte:
`references/documentacao-completa.md`
