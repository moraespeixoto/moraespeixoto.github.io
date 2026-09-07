# moraespeixoto.github.io

Site pessoal de **Vitor de Moraes Peixoto** — publicações, orientações, projetos
e o NERD. No ar em <https://moraespeixoto.github.io>.

Site estático servido pelo GitHub Pages a partir da raiz do repositório. Todo o
conteúdo vem dos arquivos YAML em `dados/`; os `.html` da raiz são saída
descartável e podem ser apagados e regerados a qualquer momento.

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
ativos/        CSS e imagens copiados para a raiz na geração
  fotos/           retratos dos integrantes do NERD
lattes/        o currículo Lattes em XML — a fonte das publicações
ferramentas/   os scripts (Python 3)
*.html         o site gerado — não edite à mão
```

Fonte e saída convivem na raiz porque este é o repositório `<usuário>.github.io`:
o Pages publica a raiz do branch, e é a única pasta que ele oferece por padrão.

## GitHub Pages

Em **Settings → Pages**: Source `Deploy from a branch`, branch `main`, pasta
`/ (root)` — que é o padrão. Nada a mudar.

O arquivo `.nojekyll` na raiz é o que impede o GitHub de rodar o Jekyll e
transformar o `README.md` em página inicial no lugar do `index.html`. Não apague.

## Publicar uma mudança

```bash
python3 -m pip install pyyaml     # uma vez
python3 ferramentas/gera_site.py  # regenera o site
git add -A && git commit -m "atualiza publicações" && git push
```

O workflow `.github/workflows/site.yml` também regenera o site sozinho quando
você edita um arquivo de `dados/` direto pelo GitHub — então dá para atualizar o
site pelo navegador, sem rodar nada localmente.

## Atualizar as publicações e orientações

Publicações, orientações e projetos vêm todos do currículo Lattes, que está
versionado aqui em `lattes/Vitor_Peixoto.xml`. Para atualizar:

1. Em [lattes.cnpq.br](http://lattes.cnpq.br/), abra seu currículo e vá em
   **Atualizar currículo → Exportar → XML**. Substitua `lattes/Vitor_Peixoto.xml`
   pelo arquivo novo (o importador também aceita o `.zip` direto).
2. Rode:

```bash
python3 ferramentas/importa_lattes.py lattes/Vitor_Peixoto.xml
python3 ferramentas/gera_site.py
```

Isso preenche `publicacoes.yml`, `orientacoes.yml` e `projetos.yml` de uma vez —
inclusive o nome de cada orientando e o ID Lattes dele.

### O que o importador conserta no caminho

O XML do Lattes não sai pronto para publicação, e o importador reproduz os mesmos
tratamentos que o script R do site do NERD faz:

- **Títulos em CAIXA ALTA** viram caixa de sentença, trecho a trecho (o que vem
  antes e depois de `:` é tratado separadamente), preservando siglas e nomes
  próprios. As duas listas ficam no topo de `ferramentas/importa_lattes.py` —
  complete-as se um título novo trouxer uma sigla que ainda não esteja lá.
- **Links** vêm no formato `[url][doi:10.x/y]`; fica só a URL, e o DOI entra em
  seu próprio campo.
- **Autores** saem no nome de citação (`PEIXOTO, VITOR`), como no site do NERD.
- **Nomes de orientandos** em caixa alta viram caixa de título, com as
  preposições em minúscula.

Erros de digitação que estão no próprio Lattes o importador não inventa de
corrigir — ele os reproduz fielmente. Um exemplo hoje visível: a tese de Ralph
André Crespo começa com "Aas ações de impugnação". Isso se corrige no Lattes e
some na próxima exportação.

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

`publicar: false` esconde um registro do site sem apagá-lo do arquivo. Hoje o
único uso é em `projetos.yml`: os projetos que vieram do Lattes entram
desligados, porque a lista curada de projetos é a do site do NERD. Ligue os que
fizerem sentido.

Publicações e orientações estão todas no ar — vieram do Lattes, que é a fonte
autorizada.

## Um ponto a conferir em `dados/perfil.yml`

O **ORCID** `0000-0001-6618-3311` foi levantado por busca na web, não pela API do
ORCID. Confirme antes de contar com ele: é dele que a coleta de DOIs parte.

## Relação com o site do NERD

O site do núcleo vive em outro lugar e em outra ferramenta:
**<https://gitlab.com/vpeixoto1981/nerd_site>** (R Markdown, publicado pelo
GitLab Pages). É de lá que vieram o texto do núcleo, os objetivos, os eixos de
pesquisa, a lista de projetos, a equipe com as fotos, o diagrama de Venn e o
próprio XML do Lattes.

São **dois repositórios independentes, sem sincronização automática**. Ao mexer
em algo do núcleo no GitLab — entrou um integrante novo, um projeto novo, o
currículo foi reexportado — traga a mudança para cá também:

| No GitLab (site do NERD) | Aqui (site pessoal) |
| --- | --- |
| `Lattes/Vitor_Peixoto.xml` | `lattes/Vitor_Peixoto.xml`, depois rode o importador |
| `Lattes/Fotos/*.jpg` | `ativos/fotos/` |
| `membros.Rmd` | `dados/equipe.yml` (bloco `membros`) |
| `projetos.Rmd` | `dados/projetos.yml` (bloco `pesquisa`) |
| `index.Rmd`, `objetivos.Rmd` | `dados/equipe.yml` (bloco `nucleo`) |

O repositório [NERD_SITE](https://github.com/moraespeixoto/NERD_SITE) no GitHub é
a versão antiga do site do núcleo e está desatualizado — a equipe de lá não
corresponde mais à atual.
