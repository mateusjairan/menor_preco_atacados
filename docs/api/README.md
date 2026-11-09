# Registro de APIs — Comparador NE

Status de cada fonte. Atualize ao descobrir/validar um endpoint.
**Nunca** registre token, cookie ou chave neste arquivo.

## Legenda

| Símbolo | Significado |
|---|---|
| ✅ | Validado, em produção |
| 🔬 | Fluxo identificado, não homologado |
| ⛔ | Bloqueado ou fora de escopo |

---

## Tier A — públicas

### VTEX (5 redes)

- **Redes:** GBarbosa, Mercantil Atacado, Hiperideal, Atacadão, Atacadão Treichel
- **Endpoint:**
  ```
  GET {base_url}/api/catalog_system/pub/products/search?ft={termo}&_from=0&_to=49
  ```
- **Auth:** nenhuma
- **Status:** ✅ (validado ao vivo em 09/11/2026 nas 5 redes)
- **Observações:**
  - `206 Partial Content` é resposta normal.
  - Preço em `items[].sellers[].commertialOffer.Price`.
  - `AvailableQuantity == 0` → ignorar SKU.
  - Preço é do canal padrão; pode variar por CEP/loja.
  - **Espaços no `ft` precisam ser `%20`, não `+`.** Com `+` a VTEX devolve
    `400 Bad Request! Scripts are not allowed!` (GBarbosa, Mercantil,
    Hiperideal e Treichel). O `HttpClient` usa `quote_via=quote` para garantir
    `%20`.

---

## Tier B — reversas

### VipCommerce (Pinheiro, Nordestão, Diniz)

Detalhes do fluxo e do bloqueio de homologação em [`vipcommerce.md`](vipcommerce.md).

- **Plataforma:** VipCommerce white-label ("Supermercados Online")
- **Base:** `https://services.vipcommerce.com.br/api-admin/v1`
- **Fluxo identificado:**
  ```
  POST /auth/loja/login          -> token anônimo da loja
  GET  /filiais/dominio/{host}   -> orgId, filialId, domainKey
  GET  /org/{orgId}/...          -> catálogo/busca/produto
  ```
- **Headers de tenant:** `DomainKey`, `OrganizationId`, `sessao-id`
- **Auth:** token anônimo obtido pelo próprio front-end
- **Status:** 🔬
- **Bloqueios:**
  - Revisar ToS antes de ligar.
  - Confirmar que a chamada é anônima (sem login de cliente).
  - Não versionar token.
  - Feature flag `ENABLE_REVERSE_API`.

### Grupo Mateus (Mateus, Mix, Camiño)

- **Arquitetura:** SPA Angular + gateway próprio
- **Hosts identificados no bundle:**
  - `gateway.mateusmais.com.br`
  - `app.mateusmais.com.br`
  - `cart-v2.mateusmais.com.br`
  - `plataforma.mateusmais.com.br`
- **Busca:** serviço próprio (`searchService: "meilisearch"`)
- **Status:** 🔬 (requer RE adicional)
- **Próximo passo:** capturar a chamada de busca no DevTools e reproduzir com headers mínimos.

---

## Tier C — bloqueadas

| Rede | Motivo | Status |
|---|---|---|
| Assaí | Home 200 com `curl-cffi` (era 403); catálogo sem endpoint mapeado | ⛔ v1 |
| Extra | Home 200 com `curl-cffi`; stack Next.js/Casas Bahia, fora do escopo | ⛔ v1 |
| Carrefour | Home 200; API de catálogo 403/503 | ⛔ v1 |
| GPA (Pão de Açúcar/Bompreço) | API privada Next.js, preço por CEP; Bompreço indisponível | ⛔ v1 |
| Novo Atacarejo | app-first | ⛔ |
| Recibom | app-first | ⛔ |

### Nota sobre `curl-cffi`

Cliente padrão do projeto: `curl_cffi.requests.Session(impersonate="chrome")`.
Resolveu o 403 de Assaí e Extra. Não resolve captcha, challenge JS nem API com WAF próprio (Carrefour).

---

## Template para nova fonte

```md
### {Rede}

- **Base:**
- **Endpoint:**
- **Método:**
- **Headers:**
- **Paginação:**
- **Campos de preço:**
- **Auth:**
- **Status:** 🔬
- **Riscos:**
```
