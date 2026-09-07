#!/usr/bin/env python3
"""Importa publicacoes, orientacoes e projetos de um curriculo Lattes.

    python3 ferramentas/importa_lattes.py ~/Downloads/curriculo.xml
    python3 ferramentas/importa_lattes.py ~/Downloads/curriculo.zip

O Lattes nao tem API aberta e a pagina do curriculo e protegida por captcha —
nao da para raspar. O caminho oficial e exportar o XML:

    lattes.cnpq.br -> entre no seu curriculo -> "Atualizar curriculo"
    -> menu "Exportar" -> XML. Vem um .zip com curriculo.xml dentro.

O parser nao depende dos nomes exatos das tags (que mudam entre versoes do
schema): ele acha os nos de producao pelo sufixo do nome e le os atributos de
todos os descendentes, escolhendo por prefixo de atributo.

A mesclagem preserva o que voce editou a mao — ver ferramentas/comum.py.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

# Tag da producao -> tipo usado em dados/publicacoes.yml
TIPOS = {
    "ARTIGO-PUBLICADO": "artigo",
    "LIVRO-PUBLICADO-OU-ORGANIZADO": "livro",
    "CAPITULO-DE-LIVRO-PUBLICADO": "capitulo",
    "TRABALHO-EM-EVENTOS": "evento",
    "TEXTO-EM-JORNAL-OU-REVISTA": "relatorio",
}

# Sufixo da tag de orientacao -> nivel. A situacao NAO sai daqui: vem de
# "EM-ANDAMENTO" estar ou nao no nome da tag. O Lattes usa o mesmo sufixo de
# nivel nos dois casos (ORIENTACOES-CONCLUIDAS-PARA-MESTRADO e
# ORIENTACAO-EM-ANDAMENTO-DE-MESTRADO), entao amarrar situacao ao sufixo
# classificava toda orientacao em andamento como concluida.
NIVEIS = {
    "PARA-POS-DOUTORADO": "pos-doutorado",
    "PARA-DOUTORADO": "doutorado",
    "PARA-MESTRADO": "mestrado",
    "DE-POS-DOUTORADO": "pos-doutorado",
    "DE-DOUTORADO": "doutorado",
    "DE-MESTRADO": "mestrado",
    "DE-INICIACAO-CIENTIFICA": "iniciacao",
    "DE-APERFEICOAMENTO-ESPECIALIZACAO": "tcc",
    "DE-MONOGRAFIA-DE-CONCLUSAO-DE-CURSO-APERFEICOAMENTO-E-ESPECIALIZACAO": "tcc",
}

# Siglas que continuam em caixa alta quando um titulo TODO EM MAIUSCULAS e
# normalizado, e nomes proprios que precisam voltar com inicial maiuscula.
# Complete as duas listas se um titulo novo trouxer uma sigla ou um nome que
# ainda nao esteja aqui.
SIGLAS = {"TSE", "TRE", "PNI", "SUS", "IDEB", "IBGE", "RJ", "SP", "MG", "ABCP",
          "PEA", "IUPERJ", "UENF", "CNPq", "FAPERJ", "PT", "PSDB", "MDB", "ONG"}
PROPRIOS = ["Brasil", "Covid-19", "Bacia de Campos", "Campos Basin",
            "Rio de Janeiro", "Norte Fluminense", "Noroeste Fluminense",
            "Lula", "Bolsonaro", "Constituicao", "America Latina"]


# --------------------------------------------------------------------------- #
# leitura do arquivo
# --------------------------------------------------------------------------- #

def abrir(caminho: Path) -> ElementTree.Element:
    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            nomes = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if not nomes:
                sys.exit(f"Nenhum .xml dentro de {caminho}")
            bruto = z.read(nomes[0])
    else:
        bruto = caminho.read_bytes()

    # O Lattes exporta em ISO-8859-1; alguns exports vem em UTF-8.
    for codec in ("iso-8859-1", "utf-8"):
        try:
            texto = bruto.decode(codec)
            return ElementTree.fromstring(texto)
        except (UnicodeDecodeError, ElementTree.ParseError):
            continue
    sys.exit(f"Nao consegui ler {caminho} como XML do Lattes.")


def atributos(no: ElementTree.Element) -> dict[str, str]:
    """Todos os atributos do no e de seus descendentes, achatados."""
    acumulado: dict[str, str] = {}
    for filho in no.iter():
        for chave, valor in filho.attrib.items():
            valor = (valor or "").strip()
            if valor and chave not in acumulado:
                acumulado[chave] = valor
    return acumulado


def primeiro(attrs: dict[str, str], *prefixos: str) -> str:
    """Primeiro atributo cujo nome comeca por um dos prefixos."""
    for prefixo in prefixos:
        for chave, valor in attrs.items():
            if chave.startswith(prefixo):
                return valor
    return ""


def ano_de(attrs: dict[str, str]) -> int:
    for chave, valor in attrs.items():
        if chave.startswith("ANO"):
            achado = re.search(r"\b(1[89]\d{2}|20\d{2})\b", valor)
            if achado:
                return int(achado.group(1))
    return 0


def _sentenciar(trecho: str) -> str:
    """Passa um trecho TODO EM MAIUSCULAS para caixa de sentenca."""
    palavras = []
    for palavra in trecho.split(" "):
        nucleo = re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", palavra)
        if nucleo.upper() in SIGLAS:
            palavras.append(palavra.upper())
        else:
            palavras.append(palavra.lower())
    texto = " ".join(palavras)
    for i, c in enumerate(texto):  # maiuscula na primeira letra do trecho
        if c.isalpha():
            texto = texto[:i] + c.upper() + texto[i + 1:]
            break
    for proprio in PROPRIOS:
        texto = re.sub(re.escape(proprio), proprio, texto, flags=re.I)
    return texto


def normaliza_titulo(titulo: str) -> str:
    """O Lattes guarda muitos titulos em caixa alta; aqui viram legiveis.

    Trabalha por trecho separado por ":" — um titulo costuma ter o principal em
    maiusculas e o subtitulo ja em caixa normal, e so o primeiro deve mudar.
    """
    titulo = titulo.strip()
    if not titulo:
        return ""
    saida = []
    for trecho in titulo.split(":"):
        letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", trecho)
        # 3 letras ou menos pode ser sigla solta; nao mexe.
        if len(letras) > 3 and letras == letras.upper():
            saida.append(_sentenciar(trecho.strip()))
        else:
            saida.append(trecho.strip())
    return ": ".join(p for p in saida if p)


def normaliza_nome(nome: str) -> str:
    """Nome de pessoa em caixa alta vira caixa de titulo.

    Parte do Lattes guarda o nome do orientando como "CESARIA CATARINA...".
    Preposicoes ficam em minuscula, como se escreve nome em portugues.
    """
    nome = nome.strip()
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", nome)
    if len(letras) <= 3 or letras != letras.upper():
        return nome  # ja esta em caixa mista: nao mexe
    minusculas = {"de", "da", "do", "das", "dos", "e", "di", "del", "van", "von"}
    palavras = []
    for i, palavra in enumerate(nome.split()):
        baixa = palavra.lower()
        palavras.append(baixa if i and baixa in minusculas else baixa.capitalize())
    return " ".join(palavras)


def normaliza_link(bruto: str, doi: str = "") -> str:
    """HOME-PAGE-DO-TRABALHO costuma vir como "[url][doi:10.x/y]".

    Devolve so a URL do primeiro grupo. Quando ela nao existe, cai no DOI.
    """
    bruto = (bruto or "").strip()
    if bruto:
        grupo = re.sub(r"^\[([^\]]*)\].*$", r"\1", bruto).strip()
        # o proprio Lattes tem entradas com protocolo duplicado
        grupo = re.sub(r"^https?://(https?://)", r"\1", grupo)
        if grupo.startswith("http://") or grupo.startswith("https://"):
            return grupo
    return ""


def autores_de(no: ElementTree.Element) -> str:
    nomes: list[tuple[int, str]] = []
    for filho in no.iter():
        if not filho.tag.endswith("AUTORES"):
            continue
        # O nome de citacao e a forma academica e e o que o site do NERD usa;
        # o nome completo entra so quando a citacao esta vazia. O campo pode
        # trazer varias formas separadas por ";" — vale a primeira.
        nome = filho.attrib.get("NOME-PARA-CITACAO") or \
            filho.attrib.get("NOME-COMPLETO-DO-AUTOR") or ""
        nome = nome.split(";")[0]
        if not nome.strip():
            continue
        try:
            ordem = int(filho.attrib.get("ORDEM-DE-AUTORIA") or 99)
        except ValueError:
            ordem = 99
        nomes.append((ordem, nome.strip()))
    nomes.sort(key=lambda x: x[0])
    return "; ".join(n for _, n in nomes)


# --------------------------------------------------------------------------- #
# extracao
# --------------------------------------------------------------------------- #

def extrai_publicacoes(raiz: ElementTree.Element) -> list[dict]:
    registros = []
    for no in raiz.iter():
        tag = no.tag.rsplit("}", 1)[-1]
        tipo = TIPOS.get(tag)
        if tipo is None:
            continue
        attrs = atributos(no)
        # A ordem importa: o no de um capitulo carrega TITULO-DO-CAPITULO e
        # TITULO-DO-LIVRO (o livro que o contem). Procurar o titulo proprio
        # primeiro, por tipo, evita rotular o capitulo com o nome do livro.
        if tipo == "capitulo":
            titulo = primeiro(attrs, "TITULO-DO-CAPITULO", "TITULO-DO-LIVRO")
        elif tipo == "evento":
            titulo = primeiro(attrs, "TITULO-DO-TRABALHO", "TITULO")
        elif tipo == "livro":
            titulo = primeiro(attrs, "TITULO-DO-LIVRO", "TITULO")
        else:
            titulo = primeiro(attrs, "TITULO-DO-ARTIGO", "TITULO-DO-TEXTO", "TITULO")
        if not titulo:
            continue
        if tipo == "capitulo":
            veiculo = attrs.get("TITULO-DO-LIVRO", "")
        elif tipo == "evento":
            veiculo = primeiro(attrs, "NOME-DO-EVENTO", "TITULO-DOS-ANAIS")
        elif tipo == "livro":
            veiculo = attrs.get("NOME-DA-EDITORA", "")
        else:
            veiculo = primeiro(attrs, "TITULO-DO-PERIODICO-OU-REVISTA",
                               "TITULO-DO-JORNAL-OU-REVISTA")

        detalhe = ", ".join(x for x in [
            f"v. {attrs['VOLUME']}" if attrs.get("VOLUME") else "",
            f"n. {attrs['FASCICULO']}" if attrs.get("FASCICULO") else "",
            (f"p. {attrs.get('PAGINA-INICIAL')}-{attrs.get('PAGINA-FINAL')}"
             if attrs.get("PAGINA-INICIAL") else ""),
        ] if x)

        doi = comum.normaliza_doi(attrs.get("DOI"))
        registros.append({
            "tipo": tipo,
            "ano": ano_de(attrs),
            "titulo": normaliza_titulo(titulo),
            "autores": autores_de(no),
            "veiculo": veiculo,
            "detalhe": detalhe,
            "doi": doi,
            "url": normaliza_link(primeiro(attrs, "HOME-PAGE-DO-TRABALHO"), doi),
            "fonte": "lattes",
            "publicar": True,
        })
    return registros


def extrai_orientacoes(raiz: ElementTree.Element) -> list[dict]:
    registros = []
    for no in raiz.iter():
        tag = no.tag.rsplit("}", 1)[-1]
        if "ORIENTAC" not in tag or "DADOS-BASICOS" in tag or "DETALHAMENTO" in tag:
            continue
        # O sufixo mais longo que casa manda: "PARA-DOUTORADO" antes de "DE-MESTRADO".
        casados = [suf for suf in NIVEIS if tag.endswith(suf)]
        if not casados:
            continue
        nivel = NIVEIS[max(casados, key=len)]
        situacao = "em andamento" if "EM-ANDAMENTO" in tag else "concluida"

        attrs = atributos(no)
        # Concluida usa NOME-DO-ORIENTADO; em andamento, NOME-DO-ORIENTANDO.
        orientando = normaliza_nome(
            primeiro(attrs, "NOME-DO-ORIENTADO", "NOME-DO-ORIENTANDO"))
        titulo = primeiro(attrs, "TITULO-DO-TRABALHO", "TITULO")
        if not orientando and not titulo:
            continue

        # Idem para o vinculo: os dois blocos nomeiam os campos diferente.
        instituicao = primeiro(attrs, "NOME-DA-INSTITUICAO", "NOME-INSTITUICAO")
        curso = primeiro(attrs, "NOME-DO-CURSO", "NOME-CURSO")
        programa = " — ".join(x for x in [curso, instituicao] if x)

        registros.append({
            "nivel": nivel,
            "ano": ano_de(attrs),
            "orientando": orientando,
            "titulo": normaliza_titulo(titulo),
            "programa": programa,
            "situacao": situacao,
            "lattes": primeiro(attrs, "NUMERO-ID-ORIENTADO"),
            "url": "",
            "publicar": True,
        })
    return registros


def extrai_projetos(raiz: ElementTree.Element) -> list[dict]:
    registros = []
    for no in raiz.iter():
        tag = no.tag.rsplit("}", 1)[-1]
        if tag != "PROJETO-DE-PESQUISA":
            continue
        attrs = atributos(no)
        titulo = primeiro(attrs, "NOME-DO-PROJETO")
        if not titulo:
            continue
        inicio = attrs.get("ANO-INICIO", "").strip()
        fim = attrs.get("ANO-FIM", "").strip()
        if fim in ("0", "0000"):  # o Lattes usa 0 para projeto sem termino
            fim = ""
        situacao = "concluido" if fim else "em andamento"
        periodo = f"{inicio} — {fim}" if (inicio and fim) else (inicio or fim)
        registros.append({
            "titulo": titulo,
            "agencia": primeiro(attrs, "NOME-DA-AGENCIA", "NOME-INSTITUICAO"),
            "processo": "",
            "periodo": periodo,
            "situacao": situacao,
            "resumo": primeiro(attrs, "DESCRICAO-DO-PROJETO"),
            "publicar": False,  # entram desligados: conferir antes de publicar
        })
    return registros


# --------------------------------------------------------------------------- #

def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    caminho = Path(sys.argv[1]).expanduser()
    if not caminho.exists():
        sys.exit(f"Arquivo nao encontrado: {caminho}")

    raiz = abrir(caminho)

    # publicacoes
    arquivo = comum.carregar("publicacoes.yml")
    atuais = arquivo.get("publicacoes") or []
    novas = extrai_publicacoes(raiz)
    juntas, incluidas, completadas = comum.mesclar(atuais, novas)
    arquivo["publicacoes"] = comum.ordenar_publicacoes(juntas)
    comum.salvar("publicacoes.yml", arquivo)
    print(f"publicacoes  {len(novas)} lidas do Lattes · "
          f"{incluidas} novas · {completadas} completadas · {len(juntas)} no total")

    # orientacoes
    arquivo = comum.carregar("orientacoes.yml")
    atuais = arquivo.get("orientacoes") or []
    novas = extrai_orientacoes(raiz)
    # Casam por nome do orientando; se o registro daqui ainda nao tem nome
    # (semente montada a mao), casam pelo titulo do trabalho.
    # A chave leva o NIVEL junto com o nome. So o nome nao serve: e comum o
    # mesmo orientando fazer mestrado e depois doutorado aqui, e a chave por
    # nome fundia as duas orientacoes em uma. E as chaves so entram quando o
    # valor existe — senao todo registro sem nome casaria com os outros sem nome.
    def chaves(o: dict) -> list[str]:
        nivel = str(o.get("nivel") or "")
        saida = []
        if comum.chave_titulo(o.get("orientando")):
            saida.append(f"nome:{nivel}:" + comum.chave_titulo(o["orientando"]))
        if comum.chave_titulo(o.get("titulo")):
            saida.append(f"tit:{nivel}:" + comum.chave_titulo(o["titulo"]))
        return saida

    indice: dict[str, dict] = {}
    for o in atuais:
        for k in chaves(o):
            indice.setdefault(k, o)

    incluidas = completadas = 0
    for nova in novas:
        alvo = None
        for k in chaves(nova):
            alvo = indice.get(k)
            if alvo is not None:
                break
        if alvo is None:
            atuais.append(nova)
            for k in chaves(nova):
                indice.setdefault(k, nova)
            incluidas += 1
            continue
        mudou = False
        for campo, valor in nova.items():
            if campo == "publicar" or valor in (None, "", 0):
                continue
            if alvo.get(campo) in (None, "", 0):
                alvo[campo] = valor
                mudou = True
        # O Lattes e a fonte autorizada: registro completo entra no ar.
        if alvo.get("orientando") and not alvo.get("publicar"):
            alvo["publicar"] = True
            mudou = True
        completadas += int(mudou)
    arquivo["orientacoes"] = sorted(
        atuais, key=lambda o: (-(o.get("ano") or 0), str(o.get("orientando") or "")))
    comum.salvar("orientacoes.yml", arquivo)
    print(f"orientacoes  {len(novas)} lidas do Lattes · "
          f"{incluidas} novas · {completadas} completadas · {len(atuais)} no total")

    # projetos
    arquivo = comum.carregar("projetos.yml")
    atuais = arquivo.get("pesquisa") or []
    novos = extrai_projetos(raiz)
    juntos, incluidos, completados = comum.mesclar(atuais, novos)
    arquivo["pesquisa"] = juntos
    comum.salvar("projetos.yml", arquivo)
    print(f"projetos     {len(novos)} lidos do Lattes · "
          f"{incluidos} novos (com publicar: false) · {completados} completados")

    print("\nAgora rode:  python3 ferramentas/gera_site.py")


if __name__ == "__main__":
    main()
