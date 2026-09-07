# moraespeixoto.github.io

Site pessoal de **Vitor de Moraes Peixoto** — publicações, orientações, projetos
e o NERD. No ar em <https://moraespeixoto.github.io>.

Site estático em `docs/`, servido pelo GitHub Pages. Todo o conteúdo vem dos
arquivos YAML em `dados/`; `docs/` é saída descartável e pode ser apagada e
regerada a qualquer momento.

A identidade visual (paleta teal/laranja, Source Sans 3, JetBrains Mono,
vocabulário de seção) é a mesma do site do
[ocupacoesBR](https://moraespeixoto.github.io/ocupacoesBR/).

```
dados/         o conteúdo — é aqui que você edita
  perfil.yml       nome, bio, vínculo, identificadores, linhas de pesquisa
  publicacoes.yml  artigos, livros, capítulos, dados — com DOI e link
  orientacoes.yml  teses, dissertações, pós-docs, iniciações
  projetos.yml     projetos financiados + software e replicação
  equipe.yml       o NERD: texto, objetivos e integrantes
ativos/        CSS e imagens copiados para docs/ na geração
ferramentas/   os scripts (Python 3)
docs/          o site gerado — não edite à mão
```

## Ligar o GitHub Pages (uma vez só)

Em **Settings → Pages**, deixe assim:

- **Source:** Deploy from a branch
- **Branch:** `main` — pasta **`/docs`**

A pasta é o único ponto de atenção: o padrão do GitHub é `/ (root)`, e o site
mora em `/docs`. Feito isso, o endereço é <https://moraespeixoto.github.io>.

## Publicar uma mudança

```bash
python3 -m pip install pyyaml     # uma vez
python3 ferramentas/gera_site.py  # regenera docs/
git add -A && git commit -m "atualiza publicações" && git push
```

O workflow `.github/workflows/site.yml` também regenera `docs/` sozinho quando
você edita um arquivo de `dados/` direto pelo GitHub — então dá para atualizar o
site pelo navegador, sem rodar nada localmente.

## Trazer as publicações do Lattes

O Lattes não tem API aberta e a página do currículo é protegida por captcha. O
caminho oficial é o XML:

1. Entre em [lattes.cnpq.br](http://lattes.cnpq.br/), abra seu currículo e vá em
   **Atualizar currículo → Exportar → XML**. Baixa um `.zip` com `curriculo.xml`.
2. Rode:

```bash
python3 ferramentas/importa_lattes.py ~/Downloads/curriculo.zip
python3 ferramentas/gera_site.py
```

Isso preenche `publicacoes.yml`, `orientacoes.yml` e `projetos.yml` de uma vez —
inclusive o nome de cada orientando e o ID Lattes dele, que a busca pública não
entrega.

## Completar DOIs e links (ORCID, Crossref, Zenodo, OSF, DataCite)

```bash
python3 ferramentas/coleta_publicacoes.py
python3 ferramentas/gera_site.py
```

Consulta, nesta ordem: ORCID (obras registradas), Crossref (filtrado pelo seu
ORCID), DataCite, Zenodo, OSF e — por último — Crossref por nome. As cinco
primeiras entram com `publicar: true`; a busca por nome é ruidosa e entra com
`publicar: false`, para você triar antes de ir ao ar.

Opções: `--seco` mostra o que faria sem gravar; `--so orcid,crossref` roda só
algumas fontes.

**Precisa de rede aberta.** No container do Claude Code na web o egresso é
restrito a poucos hosts e todas essas chamadas falham — o script diz qual host
caiu e não grava nada. Rode na sua máquina.

## Como a mesclagem se comporta

As duas ferramentas de coleta seguem a mesma regra, em `ferramentas/comum.py`:

- registro novo entra;
- registro que já existe só tem preenchidos os campos **vazios** — o que você
  escreveu à mão nunca é sobrescrito;
- nenhum registro é apagado.

Publicações casam por DOI normalizado e, na falta dele, por título sem acento e
sem pontuação. Orientações casam pelo nome do orientando e, quando o registro
daqui ainda não tem nome, pelo título do trabalho.

Os arquivos são reescritos pelo `yaml.safe_dump`, que **não preserva
comentários**: só o cabeçalho de cada arquivo é reemitido. Anotações que precisam
durar vão aqui no README, não no meio dos dados.

## O campo `publicar`

`publicar: false` esconde um registro do site sem apagá-lo do arquivo. É o que
segura o que ainda não foi conferido. Hoje está assim:

- **Três publicações** que a busca atribuiu a você mas cuja autoria não consegui
  confirmar na página do periódico (Revista Cronos, Em Construção, Agenda
  Política). Confira e vire para `true`.
- **Toda a lista de orientações.** As três dos anos 2010 vieram sem o nome do
  orientando; as demais foram derivadas da equipe do NERD e não estão
  confirmadas como orientações suas. A importação do Lattes resolve tudo de uma
  vez.

## Dois pontos a conferir em `dados/`

- **ORCID** (`perfil.yml`): `0000-0001-6618-3311` foi levantado por busca na web,
  não pela API do ORCID. Confirme antes de publicar — é dele que a coleta parte.
- **Lattes de Matheus Virginio Harduim Machado** (`equipe.yml`): no site antigo
  do NERD o ID repetia o de Rafael Soares Salles, provável erro de cópia. Está
  vazio até confirmar.

## Relação com o NERD

Este repositório é só o site pessoal. O site do núcleo continua em
[NERD_SITE](https://github.com/moraespeixoto/NERD_SITE), intocado. A página
**O NERD** daqui apresenta o grupo e a equipe — o conteúdo veio de lá
(`dados/equipe.yml` e `dados/projetos.yml`) e os dois podem seguir caminhos
próprios a partir de agora.
