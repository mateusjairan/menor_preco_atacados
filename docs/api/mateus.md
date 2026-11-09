# Grupo Mateus — Mateus Mais (Tier B)

Rede: **Grupo Mateus** (Supermercado Mateus, Mix Mateus, Mateus Mais).
Site: `https://www.mateusmais.com.br`
API: `https://app.mateusmais.com.br`
Status: **experimental**, atrás de `ENABLE_REVERSE_API`.

O endpoint é o mesmo usado pelo SPA público. Não há token, cookie ou chave
neste documento ou no adapter.

## 1. Resolver a loja

```http
GET /api/products/market-category-group/?latitude=-2.5157923&longitude=-44.2452414&city_code=2111300
Host: app.mateusmais.com.br
```

Resposta: lista de grupos (`Mercado`, `Eletro`, `Farma`, ...). O adapter usa o
primeiro mercado com `online_sell=true` do grupo `Mercado`.

```json
[
  {
    "name": "Mercado",
    "markets": [
      {
        "id": "2857c51e-ffc9-4365-b39a-0156cfc032b9",
        "name": "Supermercado Mateus Cohama",
        "online_sell": true
      }
    ]
  }
]
```

A praça padrão é São Luís/MA. Pode ser alterada por:

- `MATEUS_CITY_CODE`
- `MATEUS_LATITUDE`
- `MATEUS_LONGITUDE`
- `MATEUS_MARKET_ID` (força uma loja específica)

## 2. Buscar produtos

```http
POST /api/products/internal/v1/service/priority
Host: app.mateusmais.com.br
Content-Type: application/json
```

Corpo (campos relevantes):

```json
{
  "facets": ["specification.*", "brand", "nodes"],
  "params": "page=0&hitsPerPage=50&query=leite&facetFilters=[[\"market_id:2857c51e-ffc9-4365-b39a-0156cfc032b9\"],[\"for_sale:true\"]]",
  "index": "SHOWCASE_catalog_product_api_index_PROD_total_quantity_sold_desc",
  "service": "meilisearch",
  "market_priority": {
    "market_ids": ["2857c51e-ffc9-4365-b39a-0156cfc032b9"]
  }
}
```

Resposta: `hits`, `nbHits`, `nbPages`, `page`, `hitsPerPage`.

Campos usados pelo adapter:

| Campo | Uso |
|---|---|
| `name` | nome do produto |
| `price` | preço de etiqueta |
| `sale_price` | preço efetivo |
| `barcode` | EAN |
| `measure` + `measure_type` | tamanho (`G`, `KG`, `ML`, `L`, `UN`) |
| `objectID` | id do produto na URL |
| `image` | imagem |
| `amount_in_stock` | estoque; `0` é ignorado |
| `for_sale` | disponibilidade |
| `is_active` | produto ativo |
| `market_id` | loja consultada |

## 3. Riscos

- API não documentada; pode mudar sem aviso.
- Preço varia por loja/praça.
- O endpoint é anônimo hoje, mas isso pode mudar.
- Revisar ToS antes de uso público.
- Não usar login, token de cliente ou contornar challenge.
