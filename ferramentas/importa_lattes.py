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

# Sufixo da tag de orientacao -> (nivel, situacao)
NIVEIS = {
    "PARA-POS-DOUTORADO": ("pos-doutorado", "concluida"),
    "PARA-DOUTORADO": ("doutorado", "concluida"),
    "PARA-MESTRADO": ("mestrado", "concluida"),
    "DE-INICIACAO-CIENTIFICA": ("iniciacao", "concluida"),
    "DE-POS-DOUTORADO": ("pos-doutorado", "em andamento"),
    "DE-DOUTORADO": ("doutorado", "em andamento"),
    "DE-MESTRADO": ("mestrado", "em andamento"),
    "DE-APERFEICOAMENTO-ESPECIALIZACAO": ("tcc", "concluida"),
    "DE-MONOGRAFIA-DE-CONCLUSAO-DE-CURSO-APERFEICOAMENTO-E-ESPECIALIZACAO":
        ("tcc", "concluida"),
}


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


def autores_de(no: ElementTree.Element) -> str:
    nomes: list[tuple[int, str]] = []
    for filho in no.iter():
        if not filho.tag.endswith("AUTORES"):
            continue
        nome = filho.attrib.get("NOME-COMPLETO-DO-AUTOR") or \
            filho.attrib.get("NOME-PARA-CITACAO") or ""
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

        registros.append({
            "tipo": tipo,
            "ano": ano_de(attrs),
            "titulo": titulo,
            "autores": autores_de(no),
            "veiculo": veiculo,
            "detalhe": detalhe,
            "doi": comum.normaliza_doi(attrs.get("DOI")),
            "url": primeiro(attrs, "HOME-PAGE-DO-TRABALHO"),
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
        casados = [(s, v) for s, v in NIVEIS.items() if tag.endswith(s)]
        if not casados:
            continue
        _, (nivel, situacao) = max(casados, key=lambda x: len(x[0]))

        attrs = atributos(no)
        orientando = primeiro(attrs, "NOME-DO-ORIENTADO")
        titulo = primeiro(attrs, "TITULO-DO-TRABALHO", "TITULO")
        if not orientando and not titulo:
            continue

        instituicao = primeiro(attrs, "NOME-DA-INSTITUICAO")
        curso = primeiro(attrs, "NOME-DO-CURSO")
        programa = " — ".join(x for x in [curso, instituicao] if x)

        registros.append({
            "nivel": nivel,
            "ano": ano_de(attrs),
            "orientando": orientando,
            "titulo": titulo,
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
    indice: dict[str, dict] = {}
    for o in atuais:
        if o.get("orientando"):
            indice.setdefault("nome:" + comum.chave_titulo(o["orientando"]), o)
        if o.get("titulo"):
            indice.setdefault("tit:" + comum.chave_titulo(o["titulo"]), o)

    incluidas = completadas = 0
    for nova in novas:
        alvo = indice.get("nome:" + comum.chave_titulo(nova.get("orientando")))
        if alvo is None and nova.get("titulo"):
            alvo = indice.get("tit:" + comum.chave_titulo(nova["titulo"]))
        if alvo is None:
            atuais.append(nova)
            if nova.get("orientando"):
                indice["nome:" + comum.chave_titulo(nova["orientando"])] = nova
            if nova.get("titulo"):
                indice.setdefault("tit:" + comum.chave_titulo(nova["titulo"]), nova)
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
