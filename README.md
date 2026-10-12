# pipeline-voto-trf2

Sistema agêntico para [Claude Code](https://claude.com/claude-code) que transforma os autos de um
recurso do **TRF2** (apelação, agravo, remessa necessária) num **acórdão minutado** (ementa,
relatório e voto), auditado e acompanhado de uma prancha de conferência humana.

É inteligência aumentada: o pipeline prepara a minuta e aponta o que precisa ser conferido; quem
decide é o magistrado.

## O percurso

```
/pipeline-voto <autos.pdf>

0   Preparação: número CNJ (exige TRF2), OCR dos autos, retomada pelo gate
1   linha-tempo-recursal        cronologia, quem recorreu de quê, peças-chave
2   relator-recursal            relatório descritivo
3   triador-recursal            rota (pesquisa / probática) e desvios (embargos, recurso prejudicado)
3.6 [pesquisa]  jurisprudência do TRF2 (trf2-eproc) ∥ precedentes vinculantes (BNP)
3.7 [probática] tribunal adversarial: inventário → teses → réplicas → juiz-mediador
4   analisador-recursal         análise capítulo a capítulo, no método Marmelstein
5   redator-voto                voto em minuta limpa
6   redator-ementa              ementa no padrão estruturado do CNJ
7   merge_voto.py               acórdão = ementa + relatório + voto
8   juiz-parafrase ∥ verificador-coerencia-acordao
9   gates finais, proveniência e prancha de conferência
```

Cada etapa é validada por script (`scripts/verificar_voto.py`); uma falha no meio não refaz o que
já passou.

## Instalação

Requisitos: Python 3.10+, [Claude Code](https://claude.com/claude-code), Tesseract OCR com o idioma
português e Poppler.

```bash
git clone https://github.com/georgemarmelstein/pipeline-voto-trf2.git
cd pipeline-voto-trf2
pip install -r requirements.txt
```

Os dois servidores MCP (`trf2-eproc` e `bnp-api`) estão em `.claude/mcp-servers/` e já vêm
registrados no `.mcp.json`. Ao abrir o Claude Code nesta pasta, aprove-os.

## Uso

1. Baixe do eProc o PDF integral do processo. O nome do arquivo (ou o argumento) precisa conter o
   número CNJ.
2. No Claude Code, dentro desta pasta:

   ```
   /pipeline-voto "C:\caminho\5000000-00.2024.4.02.5101.pdf"
   ```

   Flags: `--opus` (raciocínio em Opus) e `--turma="8ª Turma Especializada"`.
3. O resultado fica em `data/voto/<numero>/`:
   - `<numero>-acordao.md`: o acórdão minutado;
   - `<numero>-conferencia-fontes.md`: a prancha, com os precedentes a conferir e as pendências;
   - `<numero>-analise.md`: a análise que fundamenta o voto.

## Kanban

Para ver os casos num quadro:

```bash
python scripts/ingerir_kanban.py <numero> --tipo voto
cd frontend && iniciar.bat        # ou: python -m uvicorn app.main:app --port 5000
```

Abra http://127.0.0.1:5000 e filtre por "Voto".

## Limites conhecidos

- Os precedentes do TRF2 não têm verificador automático de proveniência: saem como `SEM_ADAPTADOR`
  e o acórdão fica marcado como bloqueado para assinatura automática até a conferência humana.
- Itens regimentais do TRF2 (sessão virtual, ampliação do colegiado do art. 942 do CPC) estão
  marcados "A CONFERIR" no perfil do tribunal.
- O PDF do eProc de 2º grau costuma não trazer os autos do 1º grau; a análise registra o que falta.

## Sigilo

`data/` está no `.gitignore`. Autos, minutas e pesquisas de processos reais nunca devem ser
versionados nem publicados.
