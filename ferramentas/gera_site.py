#!/usr/bin/env python3
"""Gera o site estatico na raiz do repositorio a partir dos arquivos de dados/.

    python3 ferramentas/gera_site.py

Nao ha template engine: o site tem cinco paginas e a montagem cabe em funcoes
que devolvem HTML. Todo texto vindo de dados/ passa por `e()` antes de entrar
no HTML.
"""

from __future__ import annotations

import html
import shutil
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    sys.exit("Falta o PyYAML. Instale com:  python3 -m pip install pyyaml")

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
ATIVOS = RAIZ / "ativos"

# O site sai na raiz do repositorio, e nao em docs/, porque este e o repositorio
# <usuario>.github.io: o GitHub Pages publica a raiz do branch por padrao. Em
# docs/ o Pages caia no padrao e servia o README renderizado como home. O
# .nojekyll escrito aqui embaixo desliga o Jekyll, que senao transformaria o
# README em index.html. Fonte e saida convivem na raiz: o conteudo esta em
# dados/, os ativos em ativos/, e todo .html da raiz e gerado.
SAIDA = RAIZ

PAGINAS = [
    ("index.html", "Início"),
    ("publicacoes.html", "Publicações"),
    ("orientacoes.html", "Orientações"),
    ("projetos.html", "Projetos"),
    ("nerd.html", "O NERD"),
]

ROTULO_TIPO = {
    "artigo": "Artigos",
    "livro": "Livros",
    "capitulo": "Capítulos",
    "evento": "Trabalhos em eventos",
    "preprint": "Preprints",
    "dados": "Dados e software",
    "relatorio": "Relatórios",
}

ROTULO_NIVEL = {
    "pos-doutorado": "Pós-doutorado",
    "doutorado": "Doutorado",
    "mestrado": "Mestrado",
    "iniciacao": "Iniciação científica",
    "tcc": "Trabalho de conclusão",
}

ORDEM_NIVEL = ["pos-doutorado", "doutorado", "mestrado", "iniciacao", "tcc"]


# --------------------------------------------------------------------------- #
# utilidades
# --------------------------------------------------------------------------- #

def e(valor) -> str:
    """Escapa para HTML. None e 0 viram string vazia."""
    if valor is None:
        return ""
    return html.escape(str(valor).strip(), quote=True)


def fora(href) -> str:
    """Atributos para um link que sai do site: abre em aba nova.

    Quem clica no ORCID, no Lattes ou num DOI espera consultar e voltar; sem
    isto o site perdia a aba para o destino. A decisao e tomada pelo HREF, e nao
    caso a caso na chamada, para que um link novo nasca com o comportamento
    certo sem ninguem precisar lembrar.

    So endereco absoluto http(s) sai: as paginas do proprio site, os `mailto:` e
    as ancoras continuam na mesma aba, que e o que se espera delas.

    `rel` acompanha por seguranca, nao por estilo: sem `noopener` a pagina de
    destino recebe `window.opener` e pode reescrever o endereco desta.
    """
    h = str(href or "").strip().lower()
    if not h.startswith(("http://", "https://")):
        return ""
    return ' target="_blank" rel="noopener noreferrer"'


def ler(nome: str) -> dict:
    caminho = DADOS / nome
    if not caminho.exists():
        sys.exit(f"Arquivo de dados ausente: {caminho}")
    with caminho.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# Preprint nao e publicacao avaliada por pares, e somar os dois numa lista so
# infla a producao. Eles ficam na pagina, sob filtro proprio, mas fora da visao
# padrao e fora dos destaques da home.
TIPOS_FORA_DO_GERAL = {"preprint"}


def fora_do_geral(pub: dict) -> bool:
    return (pub.get("tipo") or "") in TIPOS_FORA_DO_GERAL


def publicaveis(itens):
    """Mantem apenas os registros com publicar diferente de false."""
    return [i for i in (itens or []) if i.get("publicar", True)]


def paragrafos(texto: str) -> str:
    """Converte um bloco de texto em <p>, um por linha em branco."""
    if not texto:
        return ""
    blocos = [b.strip() for b in str(texto).split("\n\n") if b.strip()]
    return "\n".join(f"<p>{e(b)}</p>" for b in blocos)


def url_lattes(ident) -> str:
    ident = str(ident or "").strip()
    return f"http://lattes.cnpq.br/{ident}" if ident else ""


def avatar(membro: dict) -> str:
    """Foto do membro, ou as iniciais quando nao ha foto."""
    foto = str(membro.get("foto") or "").strip()
    nome = str(membro.get("nome") or "").strip()
    if foto:
        return (f'<img class="vp-avatar" src="fotos/{e(foto)}" '
                f'alt="{e(nome)}" loading="lazy">')
    # Primeiro e ultimo nome, ignorando preposicoes: "Vitor de Moraes Peixoto"
    # vira VP, e nao VM.
    partes = [x for x in nome.split()
              if x.lower() not in {"de", "da", "do", "das", "dos", "e"}]
    if len(partes) >= 2:
        iniciais = (partes[0][0] + partes[-1][0]).upper()
    elif partes:
        iniciais = partes[0][0].upper()
    else:
        iniciais = "?"
    return f'<div class="vp-avatar vp-avatar-vazio" aria-hidden="true">{e(iniciais)}</div>'


def repo_slug(perfil: dict) -> str:
    """`usuario/repositorio` deste site, para o link do rodape."""
    ids = perfil.get("ids") or {}
    return f"{str(ids.get('github') or '').strip()}/{str(ids.get('repo') or '').strip()}"


# --------------------------------------------------------------------------- #
# moldura
# --------------------------------------------------------------------------- #

def navbar(perfil: dict, atual: str) -> str:
    links = []
    for arquivo, rotulo in PAGINAS:
        atributo = ' aria-current="page"' if arquivo == atual else ""
        links.append(f'<a class="vp-link" href="{arquivo}"{atributo}>{e(rotulo)}</a>')
    return f"""<nav class="vp-nav">
<div class="vp-wrap vp-nav-int">
<a class="vp-marca" href="index.html">{e(perfil.get("nome_curto") or perfil.get("nome"))}</a>
{chr(10).join(links)}
<button class="vp-tema" type="button" id="vp-tema" aria-label="Alternar tema claro e escuro">tema</button>
</div>
</nav>"""


def rodape(perfil: dict) -> str:
    endereco = "\n".join(str(l) for l in (perfil.get("endereco") or []))
    perfis = "".join(
        f'<li><a href="{e(p.get("url"))}"{fora(p.get("url"))}>{e(p.get("rotulo"))}</a></li>'
        for p in (perfil.get("perfis") or [])
    )
    return f"""<footer class="vp-rodape">
<div class="vp-wrap">
<div class="vp-rodape-grid">
<div>
<p class="vp-rodape-titulo">Endereço</p>
<p>{e(endereco)}</p>
</div>
<div>
<p class="vp-rodape-titulo">Perfis</p>
<ul>{perfis}</ul>
</div>
<div>
<p class="vp-rodape-titulo">O site</p>
<p>Gerado a partir dos arquivos em <code>dados/</code>.
Código e conteúdo em <a href="https://github.com/{e(repo_slug(perfil))}" target="_blank" rel="noopener noreferrer">github.com/{e(repo_slug(perfil))}</a>.</p>
</div>
</div>
<div class="vp-rodape-fim">{e(perfil.get("nome"))} · Atualizado em {date.today().strftime("%d/%m/%Y")}</div>
</div>
</footer>"""


# A ESCOLHA de tema tem de ser aplicada antes da primeira pintura, e por isso
# este pedaco vai no <head>, antes da folha de estilo: quem salvou "escuro" num
# sistema claro via a pagina pintar clara e so depois virar. O resto do
# comportamento (o botao) continua no fim do <body>, onde o botao ja existe.
SCRIPT_TEMA_CEDO = """<script>
(function () {
  try {
    var salvo = localStorage.getItem("vp-tema");
    if (salvo) document.documentElement.setAttribute("data-tema", salvo);
  } catch (erro) { /* navegacao privada: segue no tema do sistema */ }
})();
</script>"""

SCRIPT_TEMA = """<script>
(function () {
  var raiz = document.documentElement;
  var botao = document.getElementById("vp-tema");
  if (!botao) return;
  botao.addEventListener("click", function () {
    var escuro = raiz.getAttribute("data-tema") === "escuro";
    if (!raiz.getAttribute("data-tema")) {
      escuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
    }
    var novo = escuro ? "claro" : "escuro";
    raiz.setAttribute("data-tema", novo);
    try { localStorage.setItem("vp-tema", novo); } catch (erro) { /* idem */ }
  });
})();
</script>"""

SCRIPT_FILTRO = """<script>
(function () {
  var botoes = document.querySelectorAll("[data-filtro]");
  var itens = document.querySelectorAll("[data-tipo]");
  if (!botoes.length) return;
  botoes.forEach(function (botao) {
    botao.addEventListener("click", function () {
      var alvo = botao.getAttribute("data-filtro");
      botoes.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === botao));
      });
      itens.forEach(function (item) {
        // "todos" quer dizer "todos os publicados": o que esta marcado como
        // fora do geral (preprint) so aparece pelo filtro proprio.
        var mostra = alvo === "todos"
          ? item.getAttribute("data-fora-do-geral") !== "1"
          : item.getAttribute("data-tipo") === alvo;
        item.hidden = !mostra;
      });
    });
  });
})();
</script>"""


def pagina(perfil: dict, arquivo: str, titulo: str, descricao: str,
           corpo: str, scripts: str = "") -> str:
    nome = perfil.get("nome", "")
    titulo_completo = nome if arquivo == "index.html" else f"{titulo} · {nome}"
    base = str(perfil.get("site_url") or "").rstrip("/")
    canonical = ""
    if base:
        endereco = base + "/" + ("" if arquivo == "index.html" else arquivo)
        canonical = (f'<link rel="canonical" href="{e(endereco)}">\n'
                     f'<meta property="og:url" content="{e(endereco)}">')
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo_completo)}</title>
<meta name="description" content="{e(descricao)}">
<meta name="author" content="{e(nome)}">
<meta property="og:title" content="{e(titulo_completo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:type" content="website">
{canonical}
<link rel="icon" href="fav.png">
{SCRIPT_TEMA_CEDO}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="estilo.css">
</head>
<body>
{navbar(perfil, arquivo)}
<main>
{corpo}
</main>
{rodape(perfil)}
{SCRIPT_TEMA}
{scripts}
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# blocos reutilizados
# --------------------------------------------------------------------------- #

def cabecalho_pagina(kicker: str, titulo: str, lead: str = "") -> str:
    linha_lead = f'<p class="vp-lead">{e(lead)}</p>' if lead else ""
    return f"""<div class="vp-hero">
<div class="vp-wrap vp-secao">
<span class="vp-kicker">{e(kicker)}</span>
<h1>{e(titulo)}</h1>
{linha_lead}
</div>
</div>"""


def links_publicacao(pub: dict) -> str:
    partes = []
    doi = str(pub.get("doi") or "").strip()
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
        partes.append(f'<a class="vp-doi" href="https://doi.org/{e(doi)}"'
                      f' target="_blank" rel="noopener noreferrer">doi:{e(doi)}</a>')
    url = str(pub.get("url") or "").strip()
    if url:
        rotulo = "texto integral" if doi else "acessar"
        partes.append(f'<a class="vp-ext" href="{e(url)}"{fora(url)}>{rotulo}</a>')
    if not partes:
        return ""
    return f'<div class="vp-links">{"".join(partes)}</div>'


def item_publicacao(pub: dict) -> str:
    ano = pub.get("ano") or ""
    ano_txt = e(ano) if ano and str(ano) != "0" else "s/d"
    titulo = e(pub.get("titulo"))
    url = str(pub.get("url") or "").strip()
    doi = str(pub.get("doi") or "").strip()
    destino = f"https://doi.org/{doi.replace('https://doi.org/', '')}" if doi else url
    titulo_html = f'<a href="{e(destino)}"{fora(destino)}>{titulo}</a>' if destino else titulo

    veiculo = e(pub.get("veiculo"))
    detalhe = e(pub.get("detalhe"))
    linha_veiculo = ""
    if veiculo or detalhe:
        junto = f"<em>{veiculo}</em>" if veiculo else ""
        if detalhe:
            junto = f"{junto}, {detalhe}" if junto else detalhe
        linha_veiculo = f'<p class="vp-veiculo">{junto}</p>'

    autores = e(pub.get("autores"))
    linha_autores = f'<p class="vp-autores">{autores}</p>' if autores else ""

    marca = ' data-fora-do-geral="1" hidden' if fora_do_geral(pub) else ""
    return f"""<li class="vp-item" data-tipo="{e(pub.get("tipo") or "artigo")}"{marca}>
<div class="vp-ano">{ano_txt}</div>
<div>
<p class="vp-item-titulo">{titulo_html}</p>
{linha_autores}
{linha_veiculo}
{links_publicacao(pub)}
</div>
</li>"""


def caixa_vazia(texto: str, comando: str = "") -> str:
    bloco = f'<div class="vp-codigo">{e(comando)}</div>' if comando else ""
    return f'<div class="vp-vazio"><p>{e(texto)}</p>{bloco}</div>'


# --------------------------------------------------------------------------- #
# paginas
# --------------------------------------------------------------------------- #

def pagina_inicio(perfil, pubs, projetos, equipe) -> str:
    ids = perfil.get("ids", {})

    perfis = "".join(
        f'<li><a href="{e(p.get("url"))}"{fora(p.get("url"))}>{e(p.get("rotulo"))}</a></li>'
        for p in (perfil.get("perfis") or [])
    )

    linhas = "".join(
        f'<div class="vp-card vp-card-teal"><h3>{e(l.get("titulo"))}</h3>'
        f'<p>{e(l.get("texto"))}</p></div>'
        for l in (perfil.get("linhas") or [])
    )

    publicados = [p for p in pubs if not fora_do_geral(p)]
    destaques = [p for p in publicados if p.get("destaque")][:4]
    if not destaques:
        destaques = publicados[:4]
    lista_destaques = "".join(item_publicacao(p) for p in destaques)

    codigo_destaque = [c for c in publicaveis(projetos.get("codigo")) if c.get("destaque")]
    bloco_codigo = ""
    if codigo_destaque:
        c = codigo_destaque[0]
        destino = c.get("url") or f"https://github.com/{ids.get('github')}/{c.get('repo')}"
        bloco_codigo = f"""<div class="vp-card vp-card-laranja">
<span class="vp-kicker vp-kicker-laranja">Software</span>
<h3>{e(c.get("nome"))}</h3>
<p>{e(c.get("resumo"))}</p>
<p style="margin-top:12px"><a class="vp-btn vp-btn-nu" href="{e(destino)}"{fora(destino)}>Ver o pacote &rarr;</a></p>
</div>"""

    n_membros = len(equipe.get("membros") or [])
    nucleo = equipe.get("nucleo", {})

    return f"""<div class="vp-hero">
<div class="vp-wrap vp-hero-grid">
<div class="vp-hero-texto">
<span class="vp-kicker">{e(perfil.get("kicker"))}</span>
<h1>{e(perfil.get("nome"))}</h1>
<p class="vp-lead">{e(perfil.get("resumo"))}</p>
<div class="vp-cta">
<a class="vp-btn vp-btn-laranja" href="publicacoes.html">Publicações</a>
<a class="vp-btn vp-btn-claro" href="projetos.html">Projetos</a>
<a class="vp-btn vp-btn-nu" href="orientacoes.html">Orientações</a>
</div>
<ul class="vp-perfis">{perfis}</ul>
</div>
<div class="vp-cartao-perfil">
<p class="vp-cartao-perfil-titulo">Vínculo</p>
<dl>
<dt>Cargo</dt><dd>{e(perfil.get("titulo"))}</dd>
<dt>Instituição</dt><dd>{e(perfil.get("instituicao"))}</dd>
<dt>Programa</dt><dd>{e(perfil.get("programa"))}</dd>
<dt>Grupo</dt><dd><a href="nerd.html">{e(nucleo.get("nome"))} — {e(nucleo.get("nome_completo"))}</a> · {n_membros} integrantes</dd>
<dt>Contato</dt><dd><a href="mailto:{e(perfil.get("email"))}">{e(perfil.get("email"))}</a></dd>
</dl>
</div>
</div>
</div>

<div class="vp-wrap vp-secao">
<span class="vp-kicker">O que eu pesquiso</span>
<h2>Quatro linhas, um mesmo objeto: como a competição política se forma e o que ela produz</h2>
<div class="vp-grade-4" style="margin-top:28px">{linhas}</div>
</div>

<div class="vp-secao-sup">
<div class="vp-wrap vp-secao">
<span class="vp-kicker vp-kicker-laranja">Em destaque</span>
<h2>Trabalhos recentes</h2>
<ul class="vp-lista" style="margin-top:24px">{lista_destaques}</ul>
<p style="margin-top:24px"><a class="vp-btn vp-btn-claro" href="publicacoes.html">Ver todas as publicações</a></p>
</div>
</div>

<div class="vp-wrap vp-secao">
<div class="vp-grade-2">
<div>
<span class="vp-kicker">Sobre</span>
<h2>Percurso</h2>
<div style="margin-top:18px">{paragrafos(perfil.get("bio"))}</div>
</div>
<div>{bloco_codigo}</div>
</div>
</div>"""


def pagina_publicacoes(perfil, pubs) -> str:
    if not pubs:
        corpo = caixa_vazia(
            "Nenhuma publicação no ar ainda em dados/publicacoes.yml.",
            "python3 ferramentas/importa_lattes.py ~/Downloads/curriculo.xml\n"
            "python3 ferramentas/coleta_publicacoes.py\n"
            "python3 ferramentas/gera_site.py",
        )
        return cabecalho_pagina("Produção", "Publicações") + \
            f'<div class="vp-wrap vp-secao">{corpo}</div>'

    tipos = []
    for p in pubs:
        t = p.get("tipo") or "artigo"
        if t not in tipos:
            tipos.append(t)
    ordem = [t for t in ROTULO_TIPO if t in tipos] + [t for t in tipos if t not in ROTULO_TIPO]

    filtros = ['<button class="vp-filtro" type="button" data-filtro="todos" aria-pressed="true">Tudo</button>']
    for t in ordem:
        filtros.append(
            f'<button class="vp-filtro" type="button" data-filtro="{e(t)}" '
            f'aria-pressed="false">{e(ROTULO_TIPO.get(t, t.title()))}</button>'
        )

    itens = "".join(item_publicacao(p) for p in pubs)
    publicados = [p for p in pubs if not fora_do_geral(p)]
    n_doi = sum(1 for p in publicados if str(p.get("doi") or "").strip())
    n_fora = len(pubs) - len(publicados)

    # A contagem e a dos publicados, porque e o que a visao padrao mostra. Os
    # preprints entram numa segunda frase, com o que os distingue: dizer "131
    # registros" e mostrar 126 e o tipo de incoerencia que ninguem reporta e
    # todo mundo nota.
    lead = (f"{len(publicados)} publicações, {n_doi} com DOI. Cada item leva ao "
            "texto — pelo DOI quando existe, pela página do periódico quando não.")
    if n_fora:
        lead += (f" Há ainda {n_fora} preprints, no filtro próprio: são textos "
                 "depositados e ainda não avaliados por pares, e por isso ficam "
                 "fora da contagem acima.")

    return cabecalho_pagina("Produção", "Publicações", lead) + f"""
<div class="vp-wrap vp-secao">
<div class="vp-filtros">{"".join(filtros)}</div>
<ul class="vp-lista">{itens}</ul>
</div>"""


def pagina_orientacoes(perfil, orientacoes) -> str:
    if not orientacoes:
        corpo = caixa_vazia(
            "A lista de orientações ainda não foi publicada. Ela está no seu "
            "currículo Lattes e entra por uma linha de comando: baixe o XML do "
            "currículo em lattes.cnpq.br e rode a importação.",
            "python3 ferramentas/importa_lattes.py ~/Downloads/curriculo.xml\n"
            "python3 ferramentas/gera_site.py",
        )
        return cabecalho_pagina("Formação", "Orientações") + \
            f'<div class="vp-wrap vp-secao">{corpo}</div>'

    grupos: dict[str, list] = {}
    for o in orientacoes:
        grupos.setdefault(o.get("nivel") or "mestrado", []).append(o)

    ordem = [n for n in ORDEM_NIVEL if n in grupos] + \
            [n for n in grupos if n not in ORDEM_NIVEL]

    secoes = []
    for nivel in ordem:
        itens = sorted(grupos[nivel], key=lambda o: (-(o.get("ano") or 0),
                                                     str(o.get("orientando") or "")))
        linhas = []
        for o in itens:
            ano = o.get("ano") or 0
            ano_txt = e(ano) if ano else "&mdash;"
            nome = e(o.get("orientando")) or "<em>nome a preencher</em>"
            lattes = url_lattes(o.get("lattes"))
            if lattes:
                nome = f'<a href="{e(lattes)}"{fora(lattes)}>{nome}</a>'
            titulo = e(o.get("titulo"))
            url = str(o.get("url") or "").strip()
            if titulo and url:
                titulo = f'<a href="{e(url)}"{fora(url)}>{titulo}</a>'
            tag = "" if o.get("situacao") == "concluida" else \
                '<span class="vp-tag">em andamento</span>'
            linha_titulo = f'<p class="vp-autores">{titulo}</p>' if titulo else ""
            linhas.append(f"""<li class="vp-item">
<div class="vp-ano">{ano_txt}</div>
<div>
<p class="vp-item-titulo">{nome}{tag}</p>
{linha_titulo}
<p class="vp-veiculo">{e(o.get("programa"))}</p>
</div>
</li>""")
        secoes.append(f"""<div style="margin-top:44px">
<span class="vp-kicker">{e(ROTULO_NIVEL.get(nivel, nivel.title()))}</span>
<h2>{len(itens)} {"orientação" if len(itens) == 1 else "orientações"}</h2>
<ul class="vp-lista" style="margin-top:20px">{"".join(linhas)}</ul>
</div>""")

    lead = "Teses, dissertações, pós-doutorados e iniciações científicas."
    return cabecalho_pagina("Formação", "Orientações", lead) + \
        f'<div class="vp-wrap vp-secao">{"".join(secoes)}</div>'


def pagina_projetos(perfil, projetos) -> str:
    github = perfil.get("ids", {}).get("github", "")

    pesquisa = publicaveis(projetos.get("pesquisa"))
    cartoes_pesquisa = []
    for p in pesquisa:
        meta = " · ".join(x for x in [e(p.get("agencia")), e(p.get("processo")),
                                      e(p.get("periodo"))] if x)
        tag = "" if p.get("situacao") == "concluido" else \
            '<span class="vp-tag">em andamento</span>'
        resumo = f'<p style="margin-top:10px">{e(p.get("resumo"))}</p>' if p.get("resumo") else ""
        # Sem agencia nem processo o <p> saia vazio e deixava um degrau entre o
        # titulo e o resumo — visivel so no cartao que nao tem financiamento.
        linha_meta = f'<p class="vp-fraco">{meta}</p>' if meta else ""
        cartoes_pesquisa.append(f"""<div class="vp-card vp-card-teal">
<h3>{e(p.get("titulo"))}{tag}</h3>
{linha_meta}
{resumo}
</div>""")

    codigo = publicaveis(projetos.get("codigo"))
    cartoes_codigo = []
    for c in codigo:
        repo = str(c.get("repo") or "").strip()
        links = []
        if c.get("url"):
            links.append(f'<a class="vp-ext" href="{e(c["url"])}"{fora(c["url"])}>site</a>')
        if repo and github:
            links.append(f'<a class="vp-ext" href="https://github.com/{e(github)}/{e(repo)}"'
                         f' target="_blank" rel="noopener noreferrer">codigo</a>')
        bloco = f'<div class="vp-links">{"".join(links)}</div>' if links else ""
        cartoes_codigo.append(f"""<div class="vp-card">
<h3>{e(c.get("nome"))}</h3>
<p>{e(c.get("resumo"))}</p>
{bloco}
</div>""")

    secao_codigo = ""
    if cartoes_codigo:
        secao_codigo = f"""<div class="vp-secao-sup">
<div class="vp-wrap vp-secao">
<span class="vp-kicker vp-kicker-laranja">Dados e código</span>
<h2>Software, bases e material de replicação</h2>
<div class="vp-grade-3" style="margin-top:28px">{"".join(cartoes_codigo)}</div>
</div>
</div>"""

    lead = "Projetos financiados e o código que sai deles."
    return cabecalho_pagina("Pesquisa", "Projetos", lead) + f"""
<div class="vp-wrap vp-secao">
<span class="vp-kicker">Projetos de pesquisa</span>
<h2>Financiamento e agenda</h2>
<div class="vp-grade-2" style="margin-top:28px">{"".join(cartoes_pesquisa)}</div>
</div>
{secao_codigo}"""


def pagina_nerd(perfil, equipe) -> str:
    nucleo = equipe.get("nucleo", {})

    objetivos = "".join(
        f'<li style="margin-bottom:10px">{e(o)}</li>'
        for o in (nucleo.get("objetivos") or [])
    )

    cartoes = []
    for m in (equipe.get("membros") or []):
        lattes = url_lattes(m.get("lattes"))
        nome = e(m.get("nome"))
        nome_html = f'<a href="{e(lattes)}"{fora(lattes)}>{nome}</a>' if lattes else nome
        contatos = []
        if m.get("email"):
            contatos.append(f'<a href="mailto:{e(m["email"])}">{e(m["email"])}</a>')
        if lattes:
            contatos.append(f'<a href="{e(lattes)}"{fora(lattes)}>Lattes</a>')
        bloco = f'<div class="vp-contato">{"".join(contatos)}</div>' if contatos else ""
        cartoes.append(f"""<div class="vp-membro">
{avatar(m)}
<div class="vp-membro-texto">
<span class="vp-papel">{e(m.get("papel"))}</span>
<h3>{nome_html}</h3>
<p class="vp-vinculo">{e(m.get("vinculo"))}</p>
{bloco}
</div>
</div>""")

    eixos = "".join(
        f'<div class="vp-card vp-card-teal"><h3>{e(x.get("titulo"))}</h3>'
        f'<p>{e(x.get("texto"))}</p></div>'
        for x in (nucleo.get("eixos") or [])
    )
    secao_eixos = ""
    if eixos:
        secao_eixos = f"""<div class="vp-wrap vp-secao" style="padding-top:0">
<span class="vp-kicker">Eixos de pesquisa</span>
<h2>As três dimensões que orientam a agenda</h2>
<div class="vp-grade-3" style="margin-top:24px">{eixos}</div>
</div>"""

    site_nucleo = ""
    if nucleo.get("site"):
        site_nucleo = (f'<p style="margin-top:18px"><a class="vp-btn vp-btn-claro" '
                       f'href="{e(nucleo["site"])}"{fora(nucleo["site"])}>'
                       f'Site do núcleo &rarr;</a></p>')

    endereco = "\n".join(str(l) for l in (perfil.get("endereco") or []))

    return cabecalho_pagina(
        "Grupo de pesquisa",
        f'{nucleo.get("nome", "NERD")} — {nucleo.get("nome_completo", "")}',
        nucleo.get("resumo", ""),
    ) + f"""
<div class="vp-wrap vp-secao">
<div class="vp-grade-2">
<div>
<span class="vp-kicker">O núcleo</span>
<h2>De onde vem e o que faz</h2>
<div style="margin-top:18px">{paragrafos(nucleo.get("texto"))}</div>
<figure style="margin:26px 0 0">
<img src="nerd_diagrama_venn.png" alt="Diagrama do NERD: a interseção entre governos, comportamento eleitoral e partidos políticos">
<figcaption class="vp-fraco" style="margin-top:8px">As três dimensões que o núcleo cruza.</figcaption>
</figure>
{site_nucleo}
</div>
<div class="vp-card vp-card-laranja">
<span class="vp-kicker vp-kicker-laranja">Objetivos</span>
<ul style="margin:14px 0 0; padding-left:20px; font-size:15.5px">{objetivos}</ul>
</div>
</div>
</div>

{secao_eixos}

<div class="vp-secao-sup">
<div class="vp-wrap vp-secao">
<span class="vp-kicker">Equipe</span>
<h2>{len(cartoes)} integrantes</h2>
<div class="vp-grade-3" style="margin-top:28px">{"".join(cartoes)}</div>
</div>
</div>

<div class="vp-wrap vp-secao">
<span class="vp-kicker">Onde</span>
<h2>Localização</h2>
<p class="vp-fraco" style="white-space:pre-line; margin-top:14px">{e(endereco)}</p>
</div>"""


# --------------------------------------------------------------------------- #
# montagem
# --------------------------------------------------------------------------- #

def main() -> None:
    perfil = ler("perfil.yml")
    pubs_raw = ler("publicacoes.yml").get("publicacoes") or []
    orientacoes_raw = ler("orientacoes.yml").get("orientacoes") or []
    projetos = ler("projetos.yml")
    equipe = ler("equipe.yml")

    pubs = sorted(publicaveis(pubs_raw),
                  key=lambda p: (-(p.get("ano") or 0), str(p.get("titulo") or "")))
    orientacoes = publicaveis(orientacoes_raw)

    SAIDA.mkdir(parents=True, exist_ok=True)

    escritos = {
        "index.html": pagina(perfil, "index.html", "Início",
                             perfil.get("resumo", ""),
                             pagina_inicio(perfil, pubs, projetos, equipe)),
        "publicacoes.html": pagina(perfil, "publicacoes.html", "Publicações",
                                   f"Publicações de {perfil.get('nome')}, com DOI e link.",
                                   pagina_publicacoes(perfil, pubs), SCRIPT_FILTRO),
        "orientacoes.html": pagina(perfil, "orientacoes.html", "Orientações",
                                   f"Orientações de {perfil.get('nome')}.",
                                   pagina_orientacoes(perfil, orientacoes)),
        "projetos.html": pagina(perfil, "projetos.html", "Projetos",
                                f"Projetos de pesquisa e software de {perfil.get('nome')}.",
                                pagina_projetos(perfil, projetos)),
        "nerd.html": pagina(perfil, "nerd.html", "O NERD",
                            equipe.get("nucleo", {}).get("resumo", ""),
                            pagina_nerd(perfil, equipe)),
    }

    for nome, conteudo in escritos.items():
        (SAIDA / nome).write_text(conteudo, encoding="utf-8")

    # Os .html e os ativos da raiz sao saida descartavel: saem de dados/ + ativos/.
    for ativo in sorted(ATIVOS.iterdir()):
        if ativo.is_file():
            shutil.copyfile(ativo, SAIDA / ativo.name)
        elif ativo.is_dir():  # ativos/fotos/ e afins
            shutil.copytree(ativo, SAIDA / ativo.name, dirs_exist_ok=True)
    (SAIDA / ".nojekyll").write_text("", encoding="utf-8")

    ocultos_pub = len(pubs_raw) - len(pubs)
    ocultos_ori = len(orientacoes_raw) - len(orientacoes)

    print(f"site gerado na raiz: {len(escritos)} paginas")
    print(f"  publicacoes  {len(pubs)} no ar" +
          (f", {ocultos_pub} com publicar: false" if ocultos_pub else ""))
    print(f"  orientacoes  {len(orientacoes)} no ar" +
          (f", {ocultos_ori} com publicar: false" if ocultos_ori else ""))
    print(f"  equipe       {len(equipe.get('membros') or [])} integrantes")


if __name__ == "__main__":
    main()
