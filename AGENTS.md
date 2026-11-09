# AGENTS.md — Radar de Preço NE

App **Streamlit** que funciona como **comparador de preços de supermercado**: o usuário digita um produto, o app consulta várias redes do Nordeste e mostra **onde está mais barato**, com **preço por unidade** (R$/kg, R$/L, R$/un) para comparar embalagens diferentes.

Leia inteiro antes de alterar qualquer arquivo.

---

## 1. Produto

**Entrada:** termo livre (`leite integral 1l`, `arroz 5kg`, `detergente`).
**Saída:** tabela comparativa + destaque do menor preço + economia vs. maior preço.

O valor do app não é "listar produtos": é **responder 'onde comprar mais barato' de forma justa**. Isso exige normalização de unidade e matching entre redes.

### Escopo v1

- Busca em 5 redes com API pública (Tier A).
- Tabela ordenada por preço, com preço unitário e link.
- Matching cross-chain por EAN + fallback fuzzy.
- Destaque do mais barato por grupo e do mais barato geral.
- Export CSV.

### Fora do escopo v1

- Checkout, login, carrinho.
- Histórico de preços e alertas (v1.1).
- Preço de clube/fidelidade.
- Comparação de cesta completa (v1.1).
- Redes sem catálogo acessível.

---

## 2. Fontes e estratégia de coleta

### Tier A — API pública (produção)

| Rede | Base URL | Praça | Status |
|---|---|---|---|
| GBarbosa | `https://www.gbarbosa.com.br` | BA, SE, AL, PE, CE | ✅ homologado |
| Mercantil Atacado | `https://www.mercantilatacado.com.br` | BA | ✅ homologado |
| Hiperideal | `https://www.hiperideal.com.br` | BA | ✅ homologado |
| Atacadão | `https://www.atacadao.com.br` | Nacional/NE | ✅ homologado |
| Atacadão Treichel | `https://delivery.atacadotreichel.com.br` | CE | ✅ homologado |

### Tier B — API reversa (atrás de feature flag)

| Rede | Praça | O que já se sabe | Status |
|---|---|---|---|
| Pinheiro (Bom Vizinho) | CE | Plataforma VipCommerce | 🔬 pesquisar |
| Nordestão | RN | Plataforma VipCommerce | 🔬 pesquisar |
| Diniz | CE | Plataforma VipCommerce | 🔬 pesquisar |
| Grupo Mateus | MA, PI, CE, PE, BA | Mateus Mais; busca anônima via Meilisearch | ✅ experimental |
| Villefort | CE | VipCommerce; busca anônima de loja | ✅ experimental |

### Tier C — não homologado

| Rede | Motivo |
|---|---|
| GPA (Pão de Açúcar/Bompreço) | API privada Next.js, preço por CEP |
| Assaí | Site sem catálogo público de produtos; compra online via app/Rappi/Uber |
| Extra | Home 200 com `curl-cffi`; stack Next.js/Casas Bahia, fora do escopo de supermercado |
| Carrefour | Home 200; API de catálogo 403/503 |
| Novo Atacarejo / Recibom | app-first, sem catálogo web estável |

**Regra:** Tier A é o produto. Tier B é experimento controlado. Tier C não entra sem aprovação explícita.

---

## 3. Stack

- Python 3.11+
- Streamlit 1.50+
- **curl_cffi** (HTTP com impersonation de TLS/JA3)
- pandas (tabela)
- rapidfuzz (matching)
- altair (gráfico do painel)
- pytest (testes offline)
- ruff + black

Sem banco no v1. Feature flags por variável de ambiente.

---

## 4. Estrutura

```
radar-preco-ne/
├── AGENTS.md
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── .streamlit/config.toml      # tema editorial do painel
├── .env.example
├── app.py                      # UI apenas — nunca faz HTTP
├── docs/
│   ├── api/
│   │   ├── README.md           # registro de APIs descobertas
│   │   ├── mateus.md           # request/response do Mateus Mais
│   │   ├── assai.md            # limitação de catálogo
│   │   └── vipcommerce.md      # request/response (sem segredos)
│   └── assets/                 # screenshot e vídeo do painel
├── src/
│   ├── config.py               # CHAINS, flags, timeouts
│   ├── models.py               # Product, ChainResult
│   ├── http.py                 # cliente curl_cffi + retry + rate limit
│   ├── adapters/
│   │   ├── base.py
│   │   ├── vtex.py             # Tier A
│   │   ├── mateus.py           # Tier B (Mateus Mais)
│   │   └── vipcommerce.py      # Tier B (flag)
│   ├── units.py                # parsing de tamanho e preço unitário
│   ├── matching.py             # EAN + fuzzy + agrupamento
│   ├── insights.py             # cobertura, comparação e leitura de mercado
│   └── aggregator.py           # orquestra redes em paralelo
└── tests/
    ├── fixtures/
    └── test_*.py
```

Regras:
- `app.py` não faz HTTP.
- Um adapter por plataforma, não por rede. VTEX cobre 5; VipCommerce cobre Villefort (Pinheiro, Nordestão e Diniz em pesquisa); Mateus Mais tem adapter próprio.
- `ChainConfig.platform` decide o adapter no `build_adapters()`.
- Todo adapter devolve `list[Product]`.

---

## 5. Modelo de dados

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Product:
    chain: str
    chain_slug: str
    name: str
    brand: str | None
    ean: str | None
    price: float                 # BRL
    list_price: float | None
    package_size: float | None   # em unidade base
    package_unit: str | None     # "kg" | "l" | "un"
    unit_price: float | None     # R$ por kg/l/un
    url: str
    image_url: str | None
    collected_at: datetime
    access: str                  # "public" | "reverse"

@dataclass
class ChainResult:
    chain: str
    products: list[Product]
    error: str | None = None
    elapsed_ms: int = 0
```

`unit_price` é **obrigatório para o ranking justo**. Se não der para inferir tamanho, `None` e o produto fica fora do ranking por unidade (mas aparece na tabela).

---

## 6. Núcleo do comparador

### 6.1 Parse de tamanho

Extrair de nome/descrição:

```
(\d+(?:[.,]\d+)?)\s*(kg|g|mg|l|ml|un|unid|pacote|pct|caps)
```

Normalizar para base:

| Entrada | Base | Fator |
|---|---|---|
| g | kg | 0.001 |
| mg | kg | 0.000001 |
| ml | l | 0.001 |
| un / unid | un | 1 |
| kg / l | kg / l | 1 |

`package_size` = valor × fator. `unit_price = price / package_size`.

Casos que o teste deve cobrir: `1kg` vs `500g`, `900ml` vs `1l`, `pacote 500g`, `30un`, `1,5l`.

Multipacks contam o **conteúdo total**, não o volume de uma unidade:

| Nome | Conteúdo |
|---|---|
| `6x350ml` / `6 x 350ml` | 2,1 L |
| `2x2L` | 4 L |
| `Pack c/ 6 Unid de 350ml` | 2,1 L |
| `350ml com 6 Unidades` | 2,1 L |
| `Leve 12 Pague 11` | 12 unidades (usa o "leve") |
| `Kit 2L + Fanta 2L` | 4 L |

`multipack`/`pack`/`fardo` **sem quantidade explícita** não têm tamanho confiável: ficam com `package_size = None` em vez de chutar. Se o mesmo EAN aparece em outra rede com tamanho conhecido, o aggregator preenche por EAN.

O parser também normaliza nomes colados/abreviados: `Vidro250ml`, `360mlEmbalagem`, `1 ,15Kg`, `900mll`, `LV 24 PG 22` e `L500P350ml`. `Stand Pack` é formato de embalagem e não conta como multipack.

### 6.2 Matching entre redes

1. Normalizar nome: minúsculas, sem acento (`unicodedata.normalize("NFKD")`), espaços colapsados.
2. **EAN exato** → mesmo produto (score 100).
3. Senão, comparar `nome_sem_tamanho` + `package_size` + `package_unit`.
4. `rapidfuzz.token_set_ratio` ≥ 85 → agrupar; 60–84 → exibir com aviso "similar"; < 60 → descartar.
5. Nunca agrupar produtos de tamanhos diferentes.
6. **Backfill por EAN:** se uma rede não identificou o tamanho, mas o mesmo EAN aparece em outra rede com tamanho conhecido, o aggregator reaproveita esse tamanho e recalcula o preço unitário. Nunca sobrescreve tamanho já identificado.

### 6.3 Ranking

- `best_by_chain`: menor `unit_price` (ou `price` se unidade ausente) por rede.
- `best_overall`: menor `unit_price` entre redes.
- `savings_pct = 1 - best_overall / worst_overall`.
- `comparable_savings_pct`: mesma conta, mas só dentro do grupo do `best_overall`
  (mesmo produto/tamanho). É o valor exibido na UI, porque comparar leite com
  barra de proteína gera "economia" de 99% sem significado. Sem par no grupo,
  a UI mostra `—`.
- Empate: desempata por `price`.

### 6.4 Cesta (v1.1)

Lista de itens → total por rede. Só comparar redes que tenham **todos** os itens; senão, marcar "incompleto". Não implementar no v1.

---

## 7. Tier A — VTEX (API pública)

```
GET {base_url}/api/catalog_system/pub/products/search?ft={termo}&_from=0&_to=49
```

- `206 Partial Content` = sucesso paginado.
- 1–2 páginas por rede (50–100 itens).
- **Espaços no `ft` devem ser `%20`, nunca `+`.** VTEX responde
  `400 Bad Request! Scripts are not allowed!` com `+` (validado em 09/11/2026).
- Cliente: `curl_cffi` com `impersonate="chrome"` (ver 8.6).
- Headers: `User-Agent` identificado, `Accept: application/json`, `Accept-Language: pt-BR`.
- Preço: `items[].sellers[].commertialOffer.Price` (menor entre sellers com `AvailableQuantity > 0`).
- `ean` em `items[].ean`; URL = `{base_url}/{linkText}/p`.
- Timeout 10s; retry 2× em 429/5xx com backoff 0.5s/1.5s.
- Máx. 2 req/s por rede; 1 página simultânea por rede.

Não fazer parsing de string de moeda: `Price` já é float.

---

## 8. Tier B — engenharia reversa de API

### 8.1 Quando usar

Só quando a rede tem catálogo público **na prática** (o site anônimo mostra produto e preço), mas o endpoint não é documentado. O objetivo é **reproduzir a chamada que o próprio site faz**, não contornar proteção.

### 8.2 Playbook

1. **Capturar:** DevTools → Network → Fetch/XHR → busca no site → "Copy as cURL".
2. **Identificar:** host, path, método, query, headers, paginação, ordenação.
3. **Achar a origem no bundle:** baixar `main-*.js` e chunks; buscar `https://`, `apiUrl`, `baseUrl`, `gateway`, `graphql`, `/api/`.
4. **Replay mínimo:** reproduzir em `curl_cffi` com `impersonate="chrome"`; remover headers supérfluos; validar 200 + JSON.
5. **Documentar:** `docs/api/{rede}.md` com request/response de exemplo, **sem tokens, cookies ou chaves**.
6. **Fixture:** salvar JSON real em `tests/fixtures/`, sanitizado.
7. **Adapter:** implementar atrás de `ENABLE_REVERSE_API`.
8. **Kill switch:** erro repetido → desabilita a rede e loga.

### 8.3 Exemplo já mapeado — VipCommerce

Villefort, Pinheiro, Nordestão e Diniz usam o white-label **VipCommerce**. O bundle expõe a arquitetura:

```
POST {api}/auth/loja/login          # token anônimo da loja
GET  {api}/filiais/dominio/{host}   # resolve orgId e domainKey
GET  {api}/org/{orgId}/...          # catálogo, busca, produto
```

- `api` = `https://services.vipcommerce.com.br/api-admin/v1` (modo horizontalizado).
- Headers de tenant: `DomainKey` e `OrganizationId`, além de `sessao-id`.
- O token é obtido pelo próprio app anônimo.

**Status:** Villefort **implementado como experimental**. O fluxo é: resolver domínio, login anônimo da loja com chave pública (`VIPCOMMERCE_LOJA_KEY`, não versionada) e busca por termo. Pinheiro, Nordestão e Diniz continuam com `implemented=False` até revisão de ToS e configuração de domínio/organização.

### 8.4 Grupo Mateus — implementado como Tier B

- SPA Angular (Mateus Mais) com API anônima em `https://app.mateusmais.com.br`.
- Praça resolvida via `GET /api/products/market-category-group/?latitude=...&longitude=...&city_code=...`.
- Busca via `POST /api/products/internal/v1/service/priority` com `service="meilisearch"`, `market_priority` e filtros `market_id` + `for_sale`.
- Campos usados: `hits[].name`, `price`, `sale_price`, `barcode`, `measure`, `measure_type`, `objectID`, `image`, `amount_in_stock`.
- Loja padrão: São Luís/MA; configurável por `MATEUS_CITY_CODE`, `MATEUS_LATITUDE`, `MATEUS_LONGITUDE` e `MATEUS_MARKET_ID`.
- **Status:** ✅ experimental, atrás de `ENABLE_REVERSE_API`. Revisar ToS antes de uso público.

### 8.5 Assaí

- `/busca` é busca de conteúdo do site, não catálogo de produtos.
- `/ofertas` é encarte, sem preço por produto.
- Compra online disponível via app Meu Assaí/Rappi/Uber, sem catálogo web público anônimo.
- **Status:** ⛔ não suportado sem API de parceiro/login.

### 8.6 Cliente HTTP: curl-cffi

`curl_cffi` reproduz o handshake TLS/JA3 de um navegador real. É o **cliente padrão do projeto**, inclusive no Tier A.

```python
from curl_cffi import requests

session = requests.Session(impersonate="chrome")
r = session.get(url, timeout=10, headers=HEADERS)
```

- `IMPERSONATE=chrome` (default); fallback `chrome110` / `safari17_0` se um host rejeitar.
- Uma `Session` por rede (reaproveita conexão e cookies). Nunca compartilhar sessão entre redes.
- `allow_redirects=True`; nunca `verify=False`.
- Rate limit continua 2 req/s por rede — impersonation não é licença para martelar.

**Validado neste ambiente:**

| Host | Antes | Com `curl-cffi` |
|---|---|---|
| `assai.com.br` | 403 | 200 |
| `extra.com.br` | 403 | 200 |
| `carrefour.com.br` | 200 | 200 (API de catálogo segue 403) |
| `mercado.carrefour.com.br` | — | 503 na API |

Ou seja: fingerprint deixou de ser o bloqueio. **Captcha, challenge JS e login continuam fora de escopo.**

### 8.7 Limites (inegociável)

- ✅ Reproduzir chamada anônima que o site já faz.
- ✅ Usar `impersonate` para passar por checagem de TLS/fingerprint.
- ✅ Usar chave pública de cliente **somente** se ela serve acesso anônimo no próprio site.
- ❌ Resolver captcha, executar challenge JS, forjar login, reutilizar sessão de terceiro.
- ❌ Coletar dado pessoal.
- ❌ Commitar token, cookie ou chave.
- ❌ Aumentar taxa para "vencer" rate limit.

Se a API exigir login que o visitante não tem, **pare e pergunte**.

---

## 9. Orquestração

- `ThreadPoolExecutor(max_workers=len(redes))`.
- Uma falha não derruba a busca: `ChainResult.error`.
- Mensagens curtas: "tempo esgotado", "bloqueio temporário", "instabilidade", "resposta inesperada".
- Log INFO: rede, termo, status, itens, ms. Nunca payload completo.
- `ENABLE_REVERSE_API=true` por padrão; se `false`, ficam fora as redes Tier B com `implemented=True` (hoje, Grupo Mateus e Villefort).
- Timeout global da busca: 20s.

---

## 10. UI do comparador

Direção visual: **painel editorial de inteligência de mercado**, não landing page.

```
INTELIGÊNCIA DE PREÇOS · NORDESTE
Radar de Preço NE
Compare o preço real por quilo, litro ou unidade...

[ coca cola ........................ ] [ Buscar ]
Redes consultadas: [x] GBarbosa [x] Mercantil [x] Hiperideal [x] Atacadão [x] Treichel [x] Grupo Mateus [x] Villefort

Cards: Menor preço R$ 10,99 · Economia 12% · Cobertura 5/5 · Comparáveis 68

Produto de referência
[ gráfico de barras: preço por rede, menor em destaque ]

Leitura do mercado
- rede líder, diferença para o segundo, cobertura, qualidade dos dados

Resultados
Produto | Rede | Preço | Tamanho | Desconto | Link | Destaque
```

Regras:
- Tema claro, off-white, tinta escura e um único acento teal; sem gradiente, glassmorphism, neon ou emoji decorativo.
- Tipografia hierárquica e números em monoespaçada.
- Ordenar por `unit_price` asc; `None` vai para o fim.
- A UI não exibe valores `R$/kg`, `R$/L` ou `R$/un`; o preço unitário continua apenas interno no ranking e na economia. A tabela não tem `Preço/un`.
- Destacar `best_overall` e o menor de grupos com pelo menos duas redes.
- Cards de KPI e leitura de mercado usam apenas dados reais; nada de métrica inventada.
- `st.column_config.NumberColumn(format="R$ %.2f")` para preço; `LinkColumn` para URL.
- Aviso fixo: **"Preço de catálogo público; pode variar por loja/CEP. Não inclui preço de clube. Coletado em {data}."**
- Estado vazio: sugerir termo mais genérico.
- CSV: `;` + `utf-8-sig`.
- `app.py` não faz HTTP; a leitura de mercado fica em `src/insights.py`.

### Cache

```python
@st.cache_data(ttl=300, show_spinner=False)
def buscar(termo: str, redes: tuple[str, ...], incluir_reverse: bool) -> list[Product]:
    ...
```

---

## 11. Performance

| Cenário | Meta |
|---|---|
| 5 redes Tier A, 1 página, cache frio | < 8s |
| Cache quente | < 300ms |
| Com Tier B habilitado | < 15s |

Se estourar: reduzir páginas antes de aumentar concorrência.

---

## 12. Testes

- 100% offline (fixtures + monkeypatch no método `fetch` do adapter).
- `units.py`: `1kg` vs `500g`, `900ml` vs `1l`, `30un`, `1,5l`, tamanho ausente.
- `matching.py`: mesmo EAN em redes diferentes; fuzzy 85 agrupa; 50 não agrupa; tamanhos diferentes nunca agrupam.
- `vtex.py`: 206, múltiplos sellers, esgotado, EAN vazio.
- `vipcommerce.py`: resolução de domínio, login anônimo, busca, paginação, disponibilidade e chave via ambiente; só com fixture no CI.
- `mateus.py`: resolução de loja, busca, preço promocional, estoque, medida e fallback de tamanho.
- `aggregator.py`: uma rede com erro não impede as outras.
- `insights.py`: cobertura, comparação por grupo e leitura de mercado.
- `app.py`: smoke test com `streamlit.testing.v1.AppTest`; a tabela não deve ter `Preço/un`.
- `http.py`: retry em 429/5xx, timeout e fallback de `impersonate` sem rede real.

---

## 13. Compliance

- Endpoints públicos, uso anônimo, cache de 5 min.
- `User-Agent` com contato.
- `curl_cffi` com `impersonate` para compatibilidade de TLS, **não** para derrotar desafio de bot.
- Exibir fonte e horário.
- Se uma rede bloquear de forma consistente, **remover** em vez de contornar.
- Revisar ToS antes de habilitar qualquer Tier B.
- Nenhum segredo no repositório; `.env` no `.gitignore`.

---

## 14. Comandos

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

streamlit run app.py
pytest -q
ruff check .
black .
```

`requirements.txt` (runtime):

```
streamlit>=1.50
curl_cffi>=0.7
pandas>=2.2
rapidfuzz>=3.9
altair>=4.2
```

`requirements-dev.txt` acrescenta pytest, ruff e black.

`.env.example`:

```
ENABLE_REVERSE_API=true
HTTP_TIMEOUT=10
MAX_PAGES=2
IMPERSONATE=chrome
CONTACT_EMAIL=contato@seudominio.com.br

# Grupo Mateus (Tier B)
MATEUS_CITY_CODE=2111300
MATEUS_LATITUDE=-2.5157923
MATEUS_LONGITUDE=-44.2452414
MATEUS_MARKET_ID=

# VipCommerce (Villefort)
VIPCOMMERCE_LOJA_KEY=
```

---

## 15. Critérios de aceite

- [ ] "leite integral 1l" retorna ≥ 3 redes.
- [ ] Preço unitário correto para `1kg` vs `500g` e `900ml` vs `1l`.
- [ ] Tabela ordenada por preço unitário, com link e BRL.
- [ ] Menor preço geral destacado.
- [ ] Falha de rede não quebra a página.
- [ ] CSV abre no Excel BR.
- [ ] `pytest -q` e `ruff check .` verdes.
- [ ] Nenhum request HTTP em `app.py`.
- [ ] Nenhum segredo versionado.
- [ ] Tier B controlado por `ENABLE_REVERSE_API`; padrão habilitado para exibir todas as redes implementadas.
- [ ] `IMPERSONATE` configurável e fallback testado.

---

## 16. Como o agente deve trabalhar

1. Leia este arquivo e `docs/api/README.md` antes de codar.
2. Valide endpoint com `curl` antes de implementar parser.
3. Prefira API pública; só faça RE quando o site anônimo já expõe o dado.
4. Um adapter por plataforma; sem `if chain == ...` espalhado.
5. Não invente campo: se não viu no JSON, não existe.
6. Mudou comportamento → atualize este MD, `docs/api/` e testes.
7. Rode `pytest -q` e `ruff check .` antes de concluir.
8. Requisito ambíguo → pergunte.
```
