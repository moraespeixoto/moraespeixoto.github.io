#!/usr/bin/env python3
"""Leitura, mesclagem e escrita dos arquivos de dados/.

A regra de mesclagem, valida para as duas ferramentas de coleta:

  - registro novo entra;
  - registro que ja existe so tem preenchidos os campos VAZIOS — o que voce
    escreveu a mao nunca e sobrescrito;
  - nenhum registro e apagado.

Os arquivos sao reescritos pelo yaml.safe_dump, que nao preserva comentarios:
o cabecalho de cada arquivo e reemitido por CABECALHOS, e qualquer comentario
que voce adicionar no meio dos dados se perde na proxima coleta. Anotacoes
duradouras vao no README.md.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("Falta o PyYAML. Instale com:  python3 -m pip install pyyaml")

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"

CABECALHOS = {
    "publicacoes.yml": """# Publicacoes. Mantido pelas ferramentas de coleta; edicao a mao e preservada.
#   python3 ferramentas/importa_lattes.py CURRICULO.xml
#   python3 ferramentas/coleta_publicacoes.py
# Campos: tipo (artigo|livro|capitulo|evento|preprint|dados|relatorio),
# doi (so o sufixo), url, publicar (false esconde sem apagar), fonte.
# Ver README.md. Comentarios no meio deste arquivo se perdem na proxima coleta.
""",
    "orientacoes.yml": """# Orientacoes. Mantido por ferramentas/importa_lattes.py.
# Campos: nivel (pos-doutorado|doutorado|mestrado|iniciacao|tcc),
# situacao (concluida|em andamento), lattes (so o numero do ID), publicar.
# Ver README.md. Comentarios no meio deste arquivo se perdem na proxima coleta.
""",
    "projetos.yml": """# Projetos de pesquisa e projetos de dados/codigo.
# Ver README.md. Comentarios no meio deste arquivo se perdem na proxima coleta.
""",
}


# --------------------------------------------------------------------------- #

def carregar(nome: str) -> dict:
    caminho = DADOS / nome
    if not caminho.exists():
        return {}
    with caminho.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _limpar(valor):
    """Colapsa o espaco em branco das strings.

    Os blocos `>` do YAML deixam quebras e um \\n final; sem isso, cada
    round-trip de coleta reescreve o mesmo texto com mais espaco em volta.
    """
    if isinstance(valor, str):
        # A linha em branco separa paragrafo e sobrevive; o resto colapsa.
        paragrafos = re.split(r"\n\s*\n", valor)
        limpos = [re.sub(r"\s+", " ", p).strip() for p in paragrafos]
        return "\n\n".join(p for p in limpos if p)
    if isinstance(valor, list):
        return [_limpar(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items()}
    return valor


def salvar(nome: str, dados: dict) -> None:
    caminho = DADOS / nome
    corpo = yaml.safe_dump(_limpar(dados), allow_unicode=True, sort_keys=False,
                           default_flow_style=False, width=100)
    caminho.write_text(CABECALHOS.get(nome, "") + "\n" + corpo, encoding="utf-8")


# --------------------------------------------------------------------------- #

def normaliza_doi(valor) -> str:
    """Devolve o sufixo canonico do DOI, em minusculas."""
    s = str(valor or "").strip()
    if not s:
        return ""
    s = re.sub(r"^\s*(https?://)?(dx\.)?doi\.org/", "", s, flags=re.I)
    s = re.sub(r"^doi:\s*", "", s, flags=re.I)
    return s.strip().lower()


def chave_titulo(valor) -> str:
    """Titulo reduzido a letras e digitos, sem acento — para casar duplicatas."""
    s = str(valor or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "", s.lower())
    return s


def indexar(registros: list[dict]) -> dict[str, dict]:
    """Mapa de chave -> registro. Um registro pode entrar por DOI e por titulo."""
    indice: dict[str, dict] = {}
    for reg in registros:
        doi = normaliza_doi(reg.get("doi"))
        if doi:
            indice.setdefault("doi:" + doi, reg)
        titulo = chave_titulo(reg.get("titulo"))
        if titulo:
            indice.setdefault("tit:" + titulo, reg)
    return indice


def mesclar(existentes: list[dict], novos: list[dict]) -> tuple[list[dict], int, int]:
    """Mescla `novos` em `existentes`. Devolve (lista, n_incluidos, n_completados)."""
    indice = indexar(existentes)
    incluidos = 0
    completados = 0

    for novo in novos:
        doi = normaliza_doi(novo.get("doi"))
        titulo = chave_titulo(novo.get("titulo"))
        alvo = None
        if doi:
            alvo = indice.get("doi:" + doi)
        if alvo is None and titulo:
            alvo = indice.get("tit:" + titulo)

        if alvo is None:
            existentes.append(novo)
            if doi:
                indice["doi:" + doi] = novo
            if titulo:
                indice["tit:" + titulo] = novo
            incluidos += 1
            continue

        mudou = False
        for campo, valor in novo.items():
            if campo in ("publicar", "destaque", "fonte"):
                continue
            if valor in (None, "", 0, []):
                continue
            atual = alvo.get(campo)
            if atual in (None, "", 0, []):
                alvo[campo] = valor
                mudou = True
        if mudou:
            completados += 1
            if doi and not indice.get("doi:" + doi):
                indice["doi:" + doi] = alvo

    return existentes, incluidos, completados


def ordenar_publicacoes(registros: list[dict]) -> list[dict]:
    return sorted(registros, key=lambda p: (-(p.get("ano") or 0),
                                            str(p.get("titulo") or "")))
