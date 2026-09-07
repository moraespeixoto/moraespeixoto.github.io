#!/usr/bin/env python3
"""Coleta publicacoes no ORCID, Crossref, DataCite, Zenodo e OSF.

    python3 ferramentas/coleta_publicacoes.py
    python3 ferramentas/coleta_publicacoes.py --so orcid,crossref
    python3 ferramentas/coleta_publicacoes.py --seco     # nao grava, so mostra

Os identificadores vem de dados/perfil.yml (bloco `ids`). Cada fonte e opcional:
sem ORCID configurado, as fontes que dependem dele sao puladas.

O resultado e mesclado em dados/publicacoes.yml preservando o que voce editou —
ver ferramentas/comum.py. Registros novos entram com publicar: true e o campo
`fonte` dizendo de onde vieram.

Precisa de rede aberta. Em ambiente com egress restrito (o container do Claude
Code na web, por exemplo) as chamadas falham e o script diz qual host caiu.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402

# O Crossref pede um contato no User-Agent; em troca, roteia para o pool rapido.
CONTATO = "vpeixoto@pq.uenf.br"
AGENTE = ("site-vitorpeixoto/1.0 "
          f"(https://github.com/moraespeixoto/moraespeixoto.github.io; mailto:{CONTATO})")
TEMPO_LIMITE = 30

TIPOS_CROSSREF = {
    "journal-article": "artigo",
    "book": "livro",
    "monograph": "livro",
    "edited-book": "livro",
    "book-chapter": "capitulo",
    "book-part": "capitulo",
    "proceedings-article": "evento",
    "posted-content": "preprint",
    "dataset": "dados",
    "report": "relatorio",
}

TIPOS_ORCID = {
    "JOURNAL_ARTICLE": "artigo",
    "BOOK": "livro",
    "BOOK_CHAPTER": "capitulo",
    "CONFERENCE_PAPER": "evento",
    "PREPRINT": "preprint",
    "DATA_SET": "dados",
    "REPORT": "relatorio",
}


# --------------------------------------------------------------------------- #

def busca_json(url: str, cabecalhos: dict | None = None):
    pedido = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": AGENTE,
        **(cabecalhos or {}),
    })
    with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def texto(valor) -> str:
    return str(valor or "").strip()


def ano_de(*candidatos) -> int:
    for c in candidatos:
        if isinstance(c, dict):
            c = c.get("value") or c.get("year")
        s = texto(c)[:4]
        if s.isdigit():
            return int(s)
    return 0


# --------------------------------------------------------------------------- #
# fontes
# --------------------------------------------------------------------------- #

def de_orcid(ids: dict) -> list[dict]:
    orcid = texto(ids.get("orcid"))
    if not orcid:
        return []
    dados = busca_json(f"https://pub.orcid.org/v3.0/{orcid}/works")
    registros = []
    for grupo in dados.get("group", []):
        resumos = grupo.get("work-summary") or []
        if not resumos:
            continue
        obra = resumos[0]
        titulo = ((obra.get("title") or {}).get("title") or {}).get("value")
        if not titulo:
            continue
        doi = ""
        for ext in ((obra.get("external-ids") or {}).get("external-id") or []):
            if texto(ext.get("external-id-type")).lower() == "doi":
                doi = comum.normaliza_doi(ext.get("external-id-value"))
                break
        registros.append({
            "tipo": TIPOS_ORCID.get(texto(obra.get("type")), "artigo"),
            "ano": ano_de((obra.get("publication-date") or {}).get("year")),
            "titulo": titulo,
            "autores": "",
            "veiculo": texto((obra.get("journal-title") or {}).get("value")),
            "detalhe": "",
            "doi": doi,
            "url": texto((obra.get("url") or {}).get("value")),
            "fonte": "orcid",
            "publicar": True,
        })
    return registros


def _do_crossref(itens: list[dict]) -> list[dict]:
    registros = []
    for it in itens:
        titulos = it.get("title") or []
        if not titulos:
            continue
        autores = "; ".join(
            " ".join(x for x in [texto(a.get("given")), texto(a.get("family"))] if x)
            or texto(a.get("name"))
            for a in (it.get("author") or [])
        )
        partes = it.get("issued", {}).get("date-parts") or [[]]
        detalhe = ", ".join(x for x in [
            f"v. {it['volume']}" if it.get("volume") else "",
            f"n. {it['issue']}" if it.get("issue") else "",
            f"p. {it['page']}" if it.get("page") else "",
        ] if x)
        registros.append({
            "tipo": TIPOS_CROSSREF.get(texto(it.get("type")), "artigo"),
            "ano": ano_de(partes[0][0] if partes[0] else None),
            "titulo": titulos[0],
            "autores": autores,
            "veiculo": (it.get("container-title") or [""])[0] or texto(it.get("publisher")),
            "detalhe": detalhe,
            "doi": comum.normaliza_doi(it.get("DOI")),
            "url": texto(it.get("URL")),
            "fonte": "crossref",
            "publicar": True,
        })
    return registros


def de_crossref(ids: dict) -> list[dict]:
    orcid = texto(ids.get("orcid"))
    if not orcid:
        return []
    url = ("https://api.crossref.org/works?rows=200&mailto="
           + urllib.parse.quote(CONTATO)
           + "&filter=orcid:" + urllib.parse.quote(orcid))
    dados = busca_json(url)
    return _do_crossref((dados.get("message") or {}).get("items") or [])


def de_crossref_nome(ids: dict, nome: str) -> list[dict]:
    """Busca por nome. Ruidosa: entra com publicar: false para voce triar."""
    if not nome:
        return []
    url = ("https://api.crossref.org/works?rows=100&mailto="
           + urllib.parse.quote(CONTATO)
           + "&query.author=" + urllib.parse.quote(nome))
    dados = busca_json(url)
    registros = _do_crossref((dados.get("message") or {}).get("items") or [])
    for r in registros:
        r["fonte"] = "crossref-nome"
        r["publicar"] = False
    return registros


def de_datacite(ids: dict) -> list[dict]:
    orcid = texto(ids.get("orcid"))
    if not orcid:
        return []
    consulta = f'creators.nameIdentifiers.nameIdentifier:"https://orcid.org/{orcid}"'
    url = ("https://api.datacite.org/dois?page[size]=200&query="
           + urllib.parse.quote(consulta))
    dados = busca_json(url)
    registros = []
    for it in dados.get("data", []):
        attr = it.get("attributes") or {}
        titulos = attr.get("titles") or []
        if not titulos:
            continue
        autores = "; ".join(texto(c.get("name")) for c in (attr.get("creators") or []))
        registros.append({
            "tipo": "dados",
            "ano": ano_de(attr.get("publicationYear")),
            "titulo": texto(titulos[0].get("title")),
            "autores": autores,
            "veiculo": texto(attr.get("publisher")),
            "detalhe": "",
            "doi": comum.normaliza_doi(attr.get("doi")),
            "url": texto(attr.get("url")),
            "fonte": "datacite",
            "publicar": True,
        })
    return registros


def de_zenodo(ids: dict, nome: str) -> list[dict]:
    consulta = texto(ids.get("zenodo_query")) or nome
    if not consulta:
        return []
    url = ("https://zenodo.org/api/records?size=100&q="
           + urllib.parse.quote(f'creators.name:"{consulta}"'))
    dados = busca_json(url)
    registros = []
    for it in (dados.get("hits") or {}).get("hits", []):
        meta = it.get("metadata") or {}
        titulo = texto(meta.get("title"))
        if not titulo:
            continue
        autores = "; ".join(texto(c.get("name")) for c in (meta.get("creators") or []))
        registros.append({
            "tipo": "dados",
            "ano": ano_de(meta.get("publication_date")),
            "titulo": titulo,
            "autores": autores,
            "veiculo": "Zenodo",
            "detalhe": "",
            "doi": comum.normaliza_doi(meta.get("doi") or it.get("doi")),
            "url": texto(it.get("links", {}).get("self_html") or it.get("links", {}).get("html")),
            "fonte": "zenodo",
            "publicar": True,
        })
    return registros


def de_osf(ids: dict) -> list[dict]:
    osf = texto(ids.get("osf"))
    if not osf:
        return []
    registros = []
    for recurso, tipo in (("preprints", "preprint"), ("nodes", "dados")):
        url = f"https://api.osf.io/v2/users/{osf}/{recurso}/?page[size]=100"
        try:
            dados = busca_json(url)
        except urllib.error.HTTPError as erro:
            print(f"    osf/{recurso}: HTTP {erro.code}")
            continue
        for it in dados.get("data", []):
            attr = it.get("attributes") or {}
            titulo = texto(attr.get("title"))
            if not titulo:
                continue
            registros.append({
                "tipo": tipo,
                "ano": ano_de(attr.get("date_published") or attr.get("date_created")),
                "titulo": titulo,
                "autores": "",
                "veiculo": "OSF",
                "detalhe": "",
                "doi": comum.normaliza_doi(attr.get("doi")),
                "url": (it.get("links") or {}).get("html") or
                       f"https://osf.io/{texto(it.get('id'))}/",
                "fonte": "osf",
                "publicar": True,
            })
    return registros


# --------------------------------------------------------------------------- #

def main() -> None:
    argumentos = sys.argv[1:]
    seco = "--seco" in argumentos
    filtro = None
    for arg in argumentos:
        if arg.startswith("--so"):
            valor = arg.split("=", 1)[1] if "=" in arg else \
                (argumentos[argumentos.index(arg) + 1] if arg == "--so" and
                 len(argumentos) > argumentos.index(arg) + 1 else "")
            filtro = {f.strip() for f in valor.split(",") if f.strip()}

    perfil = comum.carregar("perfil.yml")
    ids = perfil.get("ids") or {}
    nome = texto(perfil.get("nome"))

    fontes = [
        ("orcid", lambda: de_orcid(ids)),
        ("crossref", lambda: de_crossref(ids)),
        ("datacite", lambda: de_datacite(ids)),
        ("zenodo", lambda: de_zenodo(ids, nome)),
        ("osf", lambda: de_osf(ids)),
        ("crossref-nome", lambda: de_crossref_nome(ids, nome)),
    ]

    colhidos: list[dict] = []
    for rotulo, funcao in fontes:
        if filtro and rotulo not in filtro:
            continue
        print(f"  {rotulo} ...", end=" ", flush=True)
        try:
            registros = funcao()
        except urllib.error.HTTPError as erro:
            print(f"HTTP {erro.code} — pulando")
            continue
        except urllib.error.URLError as erro:
            print(f"sem resposta ({erro.reason}) — pulando")
            continue
        except (TimeoutError, json.JSONDecodeError) as erro:
            print(f"falhou ({erro}) — pulando")
            continue
        print(f"{len(registros)} registros")
        colhidos.extend(registros)

    if not colhidos:
        print("\nNada colhido. Confira os ids em dados/perfil.yml e a rede.")
        return

    arquivo = comum.carregar("publicacoes.yml")
    atuais = arquivo.get("publicacoes") or []
    antes = len(atuais)
    juntas, incluidas, completadas = comum.mesclar(atuais, colhidos)

    print(f"\n{antes} registros antes · {incluidas} novos · "
          f"{completadas} completados · {len(juntas)} no total")

    if seco:
        print("--seco: nada foi gravado.")
        return

    arquivo["publicacoes"] = comum.ordenar_publicacoes(juntas)
    comum.salvar("publicacoes.yml", arquivo)
    print("dados/publicacoes.yml atualizado.")
    print("\nRevise os registros com fonte: crossref-nome (entram desligados)")
    print("e rode:  python3 ferramentas/gera_site.py")


if __name__ == "__main__":
    main()
