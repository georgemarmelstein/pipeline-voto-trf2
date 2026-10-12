#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converte PDFs de processos judiciais para arquivos de texto.

METODO PADRAO: OCR (Tesseract) — REGRA, nao preferencia.
Processos judiciais frequentemente contem documentos escaneados, portanto OCR
e o metodo padrao e o modo --digital e PROIBIDO para autos (perde as paginas
escaneadas silenciosamente).

O OCR roda em JANELAS de paginas com pool de threads (ver extrair_texto_ocr):
pico de RAM constante (~jobs x 2 x 6,5 MB) em vez de proporcional ao PDF, e os
nucleos da maquina de fato usados. O texto e identico ao do desenho serial —
garantido por tests/converter-pdf/test_ocr_paralelo.py.

Dependencias:
    pip install pdfplumber pdf2image pytesseract
    + Tesseract OCR instalado no sistema (com idioma portugues)
    + Poppler (para pdf2image no Windows)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional


# =============================================================================
# CONFIGURACAO DE CAMINHOS (adaptado para skill)
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

# Caminho do Poppler no Windows (baixar de https://github.com/oschwartz10612/poppler-windows/releases)
_default_poppler = Path.home() / "poppler" / "poppler-24.08.0" / "Library" / "bin"
if _default_poppler.exists():
    POPPLER_PATH = str(_default_poppler)
else:
    POPPLER_PATH = os.environ.get("POPPLER_PATH", None)

# Caminho do tessdata (verifica varios locais)
# Prioridade: 1) skill/tessdata, 2) ~/tessdata, 3) padrao do sistema
_tessdata_skill = SCRIPT_DIR / "tessdata"
_tessdata_home = Path.home() / "tessdata"

if _tessdata_skill.exists():
    TESSDATA_DIR = _tessdata_skill
elif _tessdata_home.exists():
    TESSDATA_DIR = _tessdata_home
else:
    TESSDATA_DIR = None  # Usa padrao do sistema


# =============================================================================
# PARAMETROS DE OCR
# =============================================================================

# 150 DPI e suficiente para texto de peticao/decisao e custa ~6,5 MB de RAM por
# pagina (1240x1755 RGB). Subir para 300 quadruplica a RAM sem ganho de acuracia
# em documento de texto — so vale para fac-simile ruim, e ai caso a caso.
OCR_DPI = 150
OCR_LANG = 'por'

# Pagina cujo OCR volta com menos caracteres uteis que este limiar e tratada como
# SUSPEITA, nao como vazia: digitalizacao virada de lado/cabeca para baixo devolve
# lixo ou nada, e fac-simile ruim a 150 DPI perde o que aparece a 300. Nesses casos
# entra o resgate (orientacoes + alta resolucao). Medido em autos reais: paginas que
# saiam com 3 caracteres voltaram com 527.
LIMIAR_PAGINA_MAGRA = 200
OCR_DPI_RESGATE = 300

# Marcador de perda VISIVEL. Pagina sem texto reconhecido continua tendo marcador:
# pagina que some em silencio nao aparece como falha, e o TXT vira prova.
SEM_TEXTO = '[SEM TEXTO RECONHECIDO]'

# Vocabulario-ancora para aferir se o OCR produziu PORTUGUES ou lixo. Medido em
# autos reais: pagina lida de cabeca para baixo devolve praticamente o MESMO numero
# de caracteres que a lida certa (1534 contra 1568 na p703 de um processo de 895
# paginas), so que ilegivel — ou seja, tamanho nao distingue orientacao certa de
# errada, conteudo distingue. Sao palavras funcionais e do jargao forense, que
# aparecem em qualquer peca e nunca sobrevivem a uma leitura espelhada.
PALAVRAS_COMUNS_PT = frozenset("""
de da do das dos a o as os e ou que em no na nos nas um uma uns umas para por com sem
sobre ao aos pelo pela pelos pelas nao se ja foi ser sao como mais mas quando onde qual
ante apos ate entre contra desde perante sua seu suas seus este esta esse essa aquele
processo autos juiz juiza reu re autor autora parte partes fls folha artigo art lei
codigo penal civil sentenca decisao acordao recurso peticao prazo audiencia testemunha
ministerio publico justica vara comarca federal estadual tribunal poder judiciario
data assinado documento original copia digitalmente conforme requerido defesa acusacao
""".split())

# Abaixo desta taxa de palavras comuns, o texto e tratado como ILEGIVEL e a pagina
# entra no resgate por orientacao. Aferido no processo real: das 895 paginas, apenas
# 1 ficou abaixo de 6% — logo o caminho rapido segue rapido.
LIMIAR_PORTUGUESIDADE = 0.06

# Abaixo deste numero de palavras a taxa nao tem significado estatistico (formulario
# de AR dos Correios, carimbo). Essas paginas ja sao cobertas pelo limiar de tamanho.
MIN_PALAVRAS_PARA_AFERIR = 25


# =============================================================================
# PADROES DE POLUICAO DO PJE (para remocao)
# =============================================================================

PADROES_POLUICAO = [
    # Rodapes de assinatura eletronica do PJe (TRF1 a TRF5)
    r'Assinado eletronicamente por:.*?(?:Num\.|Pág\.).*?(?:\d+|\n)',
    r'Assinado eletronicamente por:[^\n]*\n',

    # URLs do PJe
    r'https?://pje\d?g?\.trf\d\.jus\.br/[^\s\n]*',
    r'https?://[^\s]*ConsultaDocumento[^\s\n]*',

    # Numero do documento PJe
    r'Numero do documento:\s*\d+',
    r'Número do documento:\s*\d+',

    # Rodapes de tribunais superiores
    r'Documento:\s*\d+\s*-\s*Inteiro Teor[^\n]*',
    r'Site certificado[^\n]*',
    r'DJ:\s*\d{2}/\d{2}/\d{4}\s*Página\s*\d+\s*de\s*\d+',

    # Codigo de validacao
    r'Codigo de validacao:\s*[A-Za-z0-9]+',
    r'Código de validação:\s*[A-Za-z0-9]+',

    # Marcadores de pagina do PDF (rodape)
    r'Pag\.\s*\d+\s*de\s*\d+',
    r'Página\s*\d+\s*de\s*\d+',
    r'- Pág\.\s*\d+',

    # Carimbos de certificacao digital
    r'Este documento foi assinado digitalmente[^\n]*',
    r'Documento assinado digitalmente[^\n]*',
    r'Para verificar.*?acesse[^\n]*',

    # Linhas so com numeros de documento/pagina
    r'^Num\.\s*\d+\s*$',

    # Data/hora de geracao do documento
    r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s+Num\.\s*\d+',
]

# Padroes de cabecalhos/rodapes de escritorios (repetitivos)
PADROES_ESCRITORIOS = [
    # Telefones e emails repetidos
    r'(?:Fone|Tel|Telefone)s?:?\s*\(?\d{2}\)?\s*\d{4,5}[-.]\d{4}[^\n]*',
    r'e-?mail:\s*[^\s@]+@[^\s@]+\.[^\s\n]+',

    # Enderecos de escritorios (quando repetem muito)
    r'(?:Av\.|Avenida|Rua|R\.)[^,\n]+,\s*n[°o]?\s*\d+[^\n]*CEP[^\n]*',

    # Filiais repetidas
    r'Filiais?:[^\n]+',
]


def remover_poluicao_pje(texto: str) -> Tuple[str, int]:
    """
    Remove poluicao especifica do PJe (rodapes, URLs, metadados repetitivos).

    Args:
        texto: Texto bruto extraido do PDF

    Returns:
        Tupla (texto_limpo, quantidade_removida)
    """
    tamanho_original = len(texto)

    # Aplicar todos os padroes de poluicao
    for padrao in PADROES_POLUICAO:
        texto = re.sub(padrao, '', texto, flags=re.MULTILINE | re.IGNORECASE)

    # Remover linhas que sao apenas separadores ou espacos
    texto = re.sub(r'^[\s\-_=]{10,}$', '', texto, flags=re.MULTILINE)

    # Remover linhas vazias consecutivas (mais de 2)
    texto = re.sub(r'\n{4,}', '\n\n\n', texto)

    quantidade_removida = tamanho_original - len(texto)
    return texto, quantidade_removida


def remover_cabecalhos_repetitivos(texto: str) -> str:
    """
    Remove cabecalhos/rodapes de escritorios que se repetem em cada pagina.
    So remove se aparecer muitas vezes (indicando repeticao em paginas).

    Args:
        texto: Texto do processo

    Returns:
        Texto sem cabecalhos repetitivos
    """
    linhas = texto.split('\n')

    # Contar frequencia de cada linha (normalizada)
    frequencia = {}
    for linha in linhas:
        linha_norm = linha.strip().lower()
        if len(linha_norm) > 20:  # Ignorar linhas muito curtas
            frequencia[linha_norm] = frequencia.get(linha_norm, 0) + 1

    # Identificar linhas que aparecem muitas vezes (provavelmente cabecalhos)
    num_paginas = texto.count('[PAGINA ')
    limite_repeticao = max(5, num_paginas * 0.3)  # 30% das paginas ou minimo 5

    linhas_repetitivas = {
        linha for linha, count in frequencia.items()
        if count >= limite_repeticao
    }

    # Filtrar linhas repetitivas (exceto marcadores de pagina)
    linhas_filtradas = []
    for linha in linhas:
        linha_norm = linha.strip().lower()
        if linha_norm in linhas_repetitivas and '[pagina' not in linha_norm:
            continue
        linhas_filtradas.append(linha)

    return '\n'.join(linhas_filtradas)


def detectar_paginas_vazias(texto: str) -> str:
    """
    DECLARA (nao apaga) as paginas sem conteudo util reconhecido.

    O desenho anterior deletava o corpo da pagina magra, o que produzia perda
    silenciosa: o TXT ficava com menos paginas do que o PDF sem que nada
    acusasse a falta. Num documento que vira prova, a pagina ilegivel tem de
    aparecer como ilegivel — quem le precisa saber que ali havia algo e que o
    OCR nao alcancou, para ir conferir o original.

    Args:
        texto: Texto com marcadores [PAGINA X]

    Returns:
        Texto com as paginas vazias marcadas por SEM_TEXTO
    """
    # Dividir por paginas
    partes = re.split(r'(={60}\n\[PAGINA \d+\]\n={60})', texto)

    resultado = []
    for i, parte in enumerate(partes):
        # Se for marcador de pagina, manter
        if re.match(r'={60}\n\[PAGINA \d+\]\n={60}', parte):
            resultado.append(parte)
        else:
            # Pagina sem conteudo util vira perda DECLARADA, nunca buraco mudo
            texto_limpo = re.sub(r'\s+', '', parte)
            if len(texto_limpo) > 0 or SEM_TEXTO in parte:
                resultado.append(parte)
            else:
                resultado.append(f"\n{SEM_TEXTO}\n")

    return ''.join(resultado)


# =============================================================================
# EXTRACAO DE TEXTO
# =============================================================================

def extrair_texto_pdfplumber(pdf_path: str) -> Tuple[str, int]:
    """
    Extrai texto usando pdfplumber (melhor para PDFs com tabelas).

    Args:
        pdf_path: Caminho para o arquivo PDF

    Returns:
        Tupla (texto_extraido, num_paginas)
    """
    try:
        import pdfplumber

        texto_total = []
        num_paginas = 0

        with pdfplumber.open(pdf_path) as pdf:
            num_paginas = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                texto = page.extract_text()
                if texto:
                    texto_total.append(f"\n{'='*60}\n[PAGINA {i}]\n{'='*60}\n")
                    texto_total.append(texto)

        return '\n'.join(texto_total), num_paginas

    except ImportError:
        raise ImportError("pdfplumber nao instalado. Instale com: pip install pdfplumber")
    except Exception as e:
        raise Exception(f"Erro pdfplumber: {e}")


def extrair_texto_pypdf2(pdf_path: str) -> Tuple[str, int]:
    """
    Extrai texto usando PyPDF2 (fallback).

    Args:
        pdf_path: Caminho para o arquivo PDF

    Returns:
        Tupla (texto_extraido, num_paginas)
    """
    try:
        from PyPDF2 import PdfReader

        texto_total = []
        reader = PdfReader(pdf_path)
        num_paginas = len(reader.pages)

        for i, page in enumerate(reader.pages, 1):
            texto = page.extract_text()
            if texto:
                texto_total.append(f"\n{'='*60}\n[PAGINA {i}]\n{'='*60}\n")
                texto_total.append(texto)

        return '\n'.join(texto_total), num_paginas

    except ImportError:
        raise ImportError("PyPDF2 nao instalado. Instale com: pip install PyPDF2")
    except Exception as e:
        raise Exception(f"Erro PyPDF2: {e}")


def _configurar_ocr() -> None:
    """Aponta pytesseract/poppler/tessdata para os caminhos desta maquina.

    Idempotente: pode ser chamada em qualquer worker sem efeito colateral.
    """
    import pytesseract

    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

    if TESSDATA_DIR is not None:
        os.environ['TESSDATA_PREFIX'] = str(TESSDATA_DIR)

    if POPPLER_PATH and os.path.exists(POPPLER_PATH):
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')


def _kwargs_poppler() -> dict:
    """poppler_path explicito quando conhecido (nao depender so do PATH)."""
    if POPPLER_PATH and os.path.exists(POPPLER_PATH):
        return {'poppler_path': POPPLER_PATH}
    return {}


def _jobs_padrao() -> int:
    """Workers de OCR: deixa 2 nucleos para o SO, teto de 12.

    Teto porque cada worker e um processo tesseract.exe; acima disso a disputa
    por I/O e cache passa a comer o ganho.
    """
    n = os.cpu_count() or 4
    return max(1, min(12, n - 2))


def _caracteres_uteis(texto: str) -> int:
    """Conta caracteres ignorando espaco em branco (a medida de conteudo real)."""
    return len(''.join((texto or '').split()))


def _palavras(texto: str) -> list:
    """Palavras de DUAS letras ou mais do texto, em minusculas.

    O corte de uma letra nao e cosmetico: OCR de pagina virada cospe tokens
    soltos como 'a' e 'o' (de 'Beawj19a', por exemplo), que por acaso sao
    palavras portuguesas legitimas e por isso inflavam a taxa de legibilidade a
    ponto de lixo passar por texto. De duas letras para cima, 'de/do/da/em/que'
    continuam dando sinal de sobra e o ruido some.
    """
    achadas = re.findall(r'[a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+', (texto or '').lower())
    return [p for p in achadas if len(p) >= 2]


def _taxa_portugues(texto: str) -> float:
    """Fracao das palavras que sao portugues corrente (0.0 a 1.0).

    E a medida de LEGIBILIDADE do OCR. Texto lido na orientacao errada sai com
    tamanho parecido com o certo, mas quase sem palavra reconhecivel: 'informe o
    processo' vira 'ossadosd o auoul'.

    NAO aplica piso de palavras: entre dois candidatos, a taxa informa mesmo com
    poucas palavras, e zera-la faria um trecho legivel curto empatar com lixo e
    perder no desempate por tamanho. O piso vale para SUSPEITAR de uma pagina
    (_texto_suspeito), nao para COMPARAR candidatos.
    """
    palavras = _palavras(texto)
    if not palavras:
        return 0.0
    return sum(1 for p in palavras if p in PALAVRAS_COMUNS_PT) / len(palavras)


def _qualidade(texto: str) -> tuple:
    """Nota comparavel de um candidato de OCR: (legibilidade, tamanho).

    A ordem importa: PRIMEIRO legibilidade, depois tamanho. Escolher pelo maior
    texto faria a pagina virada vencer a pagina certa por uma dezena de caracteres
    de ruido — foi exatamente o erro que esta funcao existe para impedir.
    """
    return (round(_taxa_portugues(texto), 3), _caracteres_uteis(texto))


def _texto_suspeito(texto: str) -> bool:
    """True se a pagina merece o resgate: curta demais OU ilegivel demais."""
    if _caracteres_uteis(texto) < LIMIAR_PAGINA_MAGRA:
        return True
    if len(_palavras(texto)) < MIN_PALAVRAS_PARA_AFERIR:
        return False
    return _taxa_portugues(texto) < LIMIAR_PORTUGUESIDADE


def ocr_pagina(imagem, pdf_path: str = None, pagina: int = None) -> str:
    """OCR de UMA pagina, com resgate de pagina magra.

    Politica UNICA de OCR de pagina — usada tanto pela producao quanto pelo
    padrao-ouro do teste de regressao, para que o teste prove o paralelismo sem
    petrificar a politica.

    Passo 1: OCR na orientacao original (caminho comum, barato).
    Passo 2: se o resultado for SUSPEITO — curto demais OU ilegivel demais —, tenta
             90/180/270 graus. Digitalizacao virada devolve lixo espelhado, e o lixo
             tem o mesmo tamanho do texto certo: quem escolhe e a legibilidade.
    Passo 3: se AINDA for suspeito e soubermos de que PDF/pagina se trata,
             re-renderiza so aquela pagina a 300 DPI e repete os 4 angulos.

    O criterio de escolha e deterministico — _qualidade() ordena por legibilidade
    e so depois por tamanho, com empate resolvido pelo primeiro angulo testado —
    para que o texto nao dependa da ordem de execucao nem do numero de workers.

    Args:
        imagem: Pagina ja renderizada (PIL.Image)
        pdf_path: Caminho do PDF, se o resgate em alta resolucao for possivel
        pagina: Numero da pagina (1-based) para o resgate

    Returns:
        O melhor texto obtido (string vazia se nada for reconhecido)
    """
    import pytesseract

    def bruto(img):
        return pytesseract.image_to_string(img, lang=OCR_LANG)

    melhor = bruto(imagem)
    if not _texto_suspeito(melhor):
        return melhor

    for angulo in (90, 180, 270):
        girada = imagem.rotate(-angulo, expand=True)
        try:
            candidato = bruto(girada)
        finally:
            try:
                girada.close()
            except Exception:
                pass
        if _qualidade(candidato) > _qualidade(melhor):
            melhor = candidato

    if not _texto_suspeito(melhor):
        return melhor
    if not pdf_path or not pagina:
        return melhor

    # Resgate em alta resolucao: so para a pagina suspeita, entao o custo e raro
    try:
        from pdf2image import convert_from_path
        alta = convert_from_path(pdf_path, dpi=OCR_DPI_RESGATE,
                                 first_page=pagina, last_page=pagina,
                                 **_kwargs_poppler())
    except Exception:
        return melhor

    try:
        for angulo in (0, 90, 180, 270):
            img = alta[0] if angulo == 0 else alta[0].rotate(-angulo, expand=True)
            try:
                candidato = bruto(img)
            finally:
                if angulo != 0:
                    try:
                        img.close()
                    except Exception:
                        pass
            if _qualidade(candidato) > _qualidade(melhor):
                melhor = candidato
    finally:
        for img in alta:
            try:
                img.close()
            except Exception:
                pass

    return melhor


def extrair_texto_ocr(pdf_path: str, verbose: bool = False,
                      jobs: Optional[int] = None,
                      janela: Optional[int] = None) -> Tuple[str, int]:
    """
    Extrai texto usando OCR (pytesseract + pdf2image). Metodo PADRAO para
    processos judiciais — documentos escaneados so saem por aqui.

    Estrategia (v2): o PDF e renderizado em JANELAS de paginas e cada janela e
    OCRada por um POOL de threads. Isso ataca os dois gargalos do desenho antigo:

      - RAM: antes o PDF INTEIRO virava imagem de uma vez (~6,5 MB por pagina a
        150 DPI, ou seja ~6,5 GB num processo de 1000 paginas, o que estourava a
        memoria e jogava a maquina no swap). Agora vive em memoria no maximo uma
        janela: o pico passa a ser CONSTANTE (~janela x 6,5 MB), independente do
        tamanho do processo.
      - CPU: antes uma pagina por vez, em uma unica thread. Como pytesseract e
        pdftoppm executam em subprocessos (o GIL fica livre durante a espera),
        um pool de threads satura os nucleos disponiveis.

    O TEXTO PRODUZIDO E IDENTICO ao do desenho serial — mesma ordem de paginas,
    mesmos marcadores, mesma politica de OCR por pagina (ocr_pagina, com resgate
    de orientacao e alta resolucao) e mesma regra de DECLARAR a pagina sem texto
    em vez de omiti-la. Isso e verificado por tests/converter-pdf/test_ocr_paralelo.py,
    que compara caractere a caractere. Velocidade nunca justifica divergencia: o
    TXT vira prova.

    Args:
        pdf_path: Caminho para o arquivo PDF
        verbose: Se True, mostra progresso detalhado (padrao: False)
        jobs: Workers de OCR em paralelo (padrao: nucleos-2, teto 12)
        janela: Paginas renderizadas por vez (padrao: jobs x 2). Controla o
            pico de RAM: pico ~= janela x 6,5 MB.

    Returns:
        Tupla (texto_extraido, num_paginas)
    """
    try:
        from concurrent.futures import ThreadPoolExecutor
        from pdf2image import convert_from_path, pdfinfo_from_path
        import pytesseract

        _configurar_ocr()
        kw_poppler = _kwargs_poppler()

        jobs = jobs if jobs and jobs > 0 else _jobs_padrao()
        janela = janela if janela and janela > 0 else max(jobs * 2, 2)

        num_paginas = pdfinfo_from_path(pdf_path, **kw_poppler)["Pages"]

        def ocr_de(par):
            # Cada chamada dispara um tesseract.exe proprio: o GIL fica livre
            # durante a espera, entao threads bastam para paralelizar de fato.
            pagina, imagem = par
            return ocr_pagina(imagem, pdf_path=pdf_path, pagina=pagina)

        texto_total = []
        marcos = {int(num_paginas * p): f"{int(p*100)}%" for p in [0.25, 0.5, 0.75]}

        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for inicio in range(1, num_paginas + 1, janela):
                fim = min(inicio + janela - 1, num_paginas)

                # Renderiza SO esta janela — o pico de RAM nao cresce com o PDF
                imagens = convert_from_path(pdf_path, dpi=OCR_DPI,
                                            first_page=inicio, last_page=fim,
                                            **kw_poppler)
                try:
                    # pool.map preserva a ordem de entrada: paginas saem em sequencia
                    textos = list(pool.map(
                        ocr_de, enumerate(imagens, inicio)))
                finally:
                    # Libera as imagens da janela antes de renderizar a proxima
                    for imagem in imagens:
                        try:
                            imagem.close()
                        except Exception:
                            pass
                    del imagens

                for deslocamento, texto in enumerate(textos):
                    i = inicio + deslocamento
                    # Marcador SEMPRE — pagina sem texto e perda declarada, nao
                    # pagina que some. O leitor tem de conseguir auditar o buraco.
                    texto_total.append(f"\n{'='*60}\n[PAGINA {i}]\n{'='*60}\n")
                    texto_total.append(texto if (texto and texto.strip()) else SEM_TEXTO)
                    if verbose and i in marcos:
                        print(f"    [OCR] {marcos[i]} concluido...")

        return '\n'.join(texto_total), num_paginas

    except ImportError as e:
        raise ImportError(
            f"Dependencias de OCR nao instaladas: {e}\n"
            "Instale com: pip install pdf2image pytesseract\n"
            "E instale o Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
        )
    except Exception as e:
        raise Exception(f"Erro OCR: {e}")


def verificar_pdf_escaneado(texto: str, num_paginas: int) -> bool:
    """
    Verifica se o PDF provavelmente e escaneado (pouco texto extraido)
    ou possui fontes com encoding corrompido (cid:XXX).

    Args:
        texto: Texto extraido
        num_paginas: Numero de paginas do PDF

    Returns:
        True se provavelmente escaneado ou corrompido
    """
    if num_paginas == 0:
        return True

    # Remover marcadores de pagina para contar texto real
    texto_real = re.sub(r'={60}\n\[PAGINA \d+\]\n={60}', '', texto)
    texto_real = texto_real.strip()

    # Calcular caracteres por pagina
    chars_por_pagina = len(texto_real) / num_paginas if num_paginas > 0 else 0

    # PDFs digitais normalmente tem 1500-3000 chars por pagina
    # PDFs escaneados tem muito menos (ou zero)
    if chars_por_pagina < 200:
        return True

    # Verificar se ha texto corrompido com (cid:XXX) - fontes com encoding quebrado
    cid_count = len(re.findall(r'\(cid:\d+\)', texto_real))
    if cid_count > 50:
        return True

    # Verificar se texto parece corrompido/invertido
    palavras_teste = ['processo', 'autor', 'reu', 'juiz', 'sentenca', 'decisao', 'peticao', 'direito']
    texto_lower = texto_real[:50000].lower()

    palavras_encontradas = sum(1 for p in palavras_teste if p in texto_lower)

    # Se encontrar menos de 2 palavras comuns em 50k chars, provavelmente esta corrompido
    if chars_por_pagina > 200 and palavras_encontradas < 2:
        return True

    return False


# =============================================================================
# LIMPEZA DE TEXTO
# =============================================================================

def limpar_texto(texto: str) -> str:
    """
    Limpa e normaliza o texto extraido (limpeza basica).

    Args:
        texto: Texto bruto

    Returns:
        Texto limpo
    """
    # Remover multiplas linhas em branco
    texto = re.sub(r'\n{3,}', '\n\n', texto)

    # Remover espacos multiplos
    texto = re.sub(r'[ \t]+', ' ', texto)

    # Remover espacos no inicio/fim das linhas
    linhas = [linha.strip() for linha in texto.split('\n')]
    texto = '\n'.join(linhas)

    # Remover caracteres de controle (exceto newline e tab)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)

    return texto


def extrair_metadados_texto(texto: str) -> dict:
    """
    Extrai metadados basicos do texto do processo.

    Args:
        texto: Texto do processo

    Returns:
        Dicionario com metadados extraidos
    """
    metadados = {}

    # Numero do processo (padrao CNJ)
    match = re.search(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', texto)
    if match:
        metadados['numero_cnj'] = match.group()

    # Classe processual
    match = re.search(r'Classe:\s*([^\n]+)', texto, re.IGNORECASE)
    if match:
        metadados['classe'] = match.group(1).strip()

    # Autor/Requerente
    match = re.search(r'(?:Autor|Requerente|Impetrante)(?:\(a\))?:\s*([^\n]+)', texto, re.IGNORECASE)
    if match:
        metadados['autor'] = match.group(1).strip()

    # Reu/Requerido
    match = re.search(r'(?:Reu|Réu|Requerido|Impetrado)(?:\(a\))?:\s*([^\n]+)', texto, re.IGNORECASE)
    if match:
        metadados['reu'] = match.group(1).strip()

    # Assunto
    match = re.search(r'Assunto:\s*([^\n]+)', texto, re.IGNORECASE)
    if match:
        metadados['assunto'] = match.group(1).strip()

    # Orgao julgador
    match = re.search(r'(?:Orgao|Órgão)\s*(?:Julgador)?:\s*([^\n]+)', texto, re.IGNORECASE)
    if match:
        metadados['orgao_julgador'] = match.group(1).strip()

    # Valor da causa
    match = re.search(r'Valor\s*(?:da\s*Causa)?:\s*R?\$?\s*([\d.,]+)', texto, re.IGNORECASE)
    if match:
        metadados['valor_causa'] = match.group(1).strip()

    return metadados


# =============================================================================
# PROCESSAMENTO PRINCIPAL
# =============================================================================

def processar_pdf(pdf_path: Path, output_dir: Path, usar_ocr: bool = True, verbose: bool = False,
                  strict_ocr: bool = False, jobs: Optional[int] = None) -> dict:
    """
    Processa um PDF e salva o texto extraido.

    Args:
        pdf_path: Caminho do PDF
        output_dir: Diretorio de saida
        usar_ocr: Se True, usa OCR (padrao). Se False, usa extracao digital.
        verbose: Se True, mostra progresso detalhado (padrao: False)
        strict_ocr: Se True, falha quando o OCR quebra em vez de cair para a
            extracao digital (que perde paginas escaneadas)
        jobs: Workers de OCR em paralelo (None = nucleos-2, teto 12)

    Returns:
        Dicionario com resultado do processamento
    """
    nome_base = pdf_path.stem
    output_path = output_dir / f"{nome_base}.txt"

    resultado = {
        'arquivo_origem': str(pdf_path),
        'arquivo_destino': str(output_path),
        'sucesso': False,
        'metodo': None,
        'paginas': 0,
        'caracteres_bruto': 0,
        'caracteres_limpo': 0,
        'poluicao_removida': 0,
        'usou_ocr': usar_ocr,
        'metadados': {},
        'erro': None
    }

    texto = None
    num_paginas = 0

    if usar_ocr:
        # PADRAO: OCR (melhor para processos judiciais com documentos escaneados)
        try:
            texto, num_paginas = extrair_texto_ocr(str(pdf_path), verbose=verbose, jobs=jobs)
            resultado['metodo'] = 'OCR (Tesseract)'
        except Exception as e:
            if strict_ocr:
                # Regra do pipeline: melhor falhar visivel que TXT com paginas perdidas
                resultado['erro'] = f"OCR falhou (strict-ocr, sem fallback): {e}"
                return resultado
            # Fallback para extracao digital — AVISADO, pois perde paginas escaneadas
            print(f"[AVISO] {pdf_path.name}: OCR falhou ({str(e)[:60]}); "
                  f"fallback digital pode perder paginas escaneadas")
            try:
                texto, num_paginas = extrair_texto_pdfplumber(str(pdf_path))
                resultado['metodo'] = 'pdfplumber (fallback)'
                resultado['usou_ocr'] = False
            except Exception as e2:
                resultado['erro'] = f"OCR: {e}; pdfplumber: {e2}"
    else:
        # MODO DIGITAL: extracao rapida sem OCR (para PDFs digitais)
        try:
            texto, num_paginas = extrair_texto_pdfplumber(str(pdf_path))
            resultado['metodo'] = 'pdfplumber'
        except Exception as e:
            # Tentar OCR silenciosamente se extracao digital falhar
            try:
                texto, num_paginas = extrair_texto_ocr(str(pdf_path), verbose=verbose, jobs=jobs)
                resultado['metodo'] = 'OCR (fallback)'
                resultado['usou_ocr'] = True
            except Exception as e2:
                resultado['erro'] = f"pdfplumber: {e}; OCR: {e2}"

    resultado['paginas'] = num_paginas

    if not texto or len(texto.strip()) < 100:
        resultado['erro'] = "PDF sem texto extraivel (documento escaneado sem OCR disponivel)"
        return resultado

    resultado['caracteres_bruto'] = len(texto)

    # Limpeza basica
    texto = limpar_texto(texto)

    # Limpeza agressiva de poluicao do PJe
    texto, poluicao_removida = remover_poluicao_pje(texto)
    resultado['poluicao_removida'] = poluicao_removida

    # Remover cabecalhos repetitivos
    texto = remover_cabecalhos_repetitivos(texto)

    # Remover paginas vazias
    texto = detectar_paginas_vazias(texto)

    # Limpeza final
    texto = re.sub(r'\n{3,}', '\n\n', texto)

    resultado['caracteres_limpo'] = len(texto)

    # Extrair metadados
    resultado['metadados'] = extrair_metadados_texto(texto)

    # Calcular reducao
    if resultado['caracteres_bruto'] > 0:
        reducao = (1 - resultado['caracteres_limpo'] / resultado['caracteres_bruto']) * 100
    else:
        reducao = 0

    # Adicionar cabecalho ao arquivo
    cabecalho = f"""# Texto Extraido de Processo Judicial
# Arquivo origem: {pdf_path.name}
# Data extracao: {datetime.now().isoformat()}
# Metodo: {resultado['metodo']}
# Paginas: {resultado['paginas']}
# Caracteres (bruto): {resultado['caracteres_bruto']}
# Caracteres (limpo): {resultado['caracteres_limpo']}
# Reducao: {reducao:.1f}%

"""

    # Salvar
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cabecalho)
        f.write(texto)

    resultado['sucesso'] = True
    return resultado


def main():
    parser = argparse.ArgumentParser(
        description='Converte PDFs de processos judiciais para texto. PADRAO: OCR (Tesseract)'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Diretorio com PDFs ou arquivo PDF individual'
    )
    parser.add_argument(
        '--output',
        default='./textos',
        help='Diretorio de saida para arquivos TXT (padrao: ./textos)'
    )
    parser.add_argument(
        '--limite',
        type=int,
        default=0,
        help='Limitar quantidade de arquivos (0 = todos)'
    )
    parser.add_argument(
        '--digital',
        action='store_true',
        help='Usar extracao digital (pdfplumber) em vez de OCR. Mais rapido, mas falha em escaneados.'
    )
    parser.add_argument(
        '--strict-ocr',
        action='store_true',
        help='Falha quando o OCR quebra, em vez de cair para extracao digital (protege contra perda de paginas escaneadas)'
    )
    parser.add_argument(
        '--jobs', '-j',
        type=int,
        default=0,
        help='Workers de OCR em paralelo (0 = automatico: nucleos-2, teto 12). '
             'Pico de RAM ~= jobs x 2 x 6,5 MB, constante no tamanho do PDF.'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mostra progresso detalhado (padrao: output minimo)'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    usar_ocr = not args.digital
    verbose = args.verbose

    # Listar PDFs
    if input_path.is_file():
        pdfs = [input_path]
    else:
        pdfs = sorted(input_path.glob('*.pdf'))

    if args.limite > 0:
        pdfs = pdfs[:args.limite]

    if not pdfs:
        print("[AVISO] Nenhum PDF encontrado")
        return 1

    # Cabecalho compacto
    metodo = 'digital' if not usar_ocr else 'OCR'
    print(f"[INICIO] {len(pdfs)} PDFs -> {output_dir} ({metodo})")

    sucesso = 0
    falha = 0
    total_bruto = 0
    total_limpo = 0
    resultados = []

    for i, pdf in enumerate(pdfs, 1):
        resultado = processar_pdf(pdf, output_dir, usar_ocr, verbose=verbose,
                                  strict_ocr=args.strict_ocr,
                                  jobs=(args.jobs or None))
        resultados.append(resultado)

        if resultado['sucesso']:
            sucesso += 1
            total_bruto += resultado['caracteres_bruto']
            total_limpo += resultado['caracteres_limpo']

            reducao = 0
            if resultado['caracteres_bruto'] > 0:
                reducao = (1 - resultado['caracteres_limpo'] / resultado['caracteres_bruto']) * 100

            # Output compacto: uma linha por arquivo
            print(f"[OK] {pdf.name}: {resultado['paginas']}p, {resultado['caracteres_limpo']//1000}k chars, -{reducao:.0f}%")
        else:
            falha += 1
            print(f"[ERRO] {pdf.name}: {resultado['erro'][:50]}")

    # Resumo compacto
    if total_bruto > 0:
        reducao_total = (1 - total_limpo / total_bruto) * 100
        print(f"[FIM] {sucesso}/{len(pdfs)} OK, {total_limpo//1000}k chars total, -{reducao_total:.0f}%")
    else:
        print(f"[FIM] {sucesso}/{len(pdfs)} OK")

    # Salvar log (detalhes ficam aqui, nao no output)
    import json
    log_path = output_dir / 'conversao_log.json'
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump({
            'data': datetime.now().isoformat(),
            'sucesso': sucesso,
            'falha': falha,
            'caracteres_bruto': total_bruto,
            'caracteres_limpo': total_limpo,
            'resultados': resultados
        }, f, indent=2, ensure_ascii=False)

    # Exit code honesto: 1 se qualquer conversao falhou (checkpoints confiam no rc)
    return 0 if falha == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
