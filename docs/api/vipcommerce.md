# VipCommerce — Tier B (experimental)

Redes alvo: **Villefort** (implementado), **Pinheiro (Bom Vizinho)**,
**Nordestão** e **Diniz**.

## Arquitetura

White-label "Supermercados Online". O front-end expõe:

```text
GET  /organizacoes/filiais/dominio/{host}  -> organização/filial
POST /org/{orgId}/auth/loja/login          -> token anônimo da loja
GET  /org/{orgId}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}
```

Base: `https://services.vipcommerce.com.br/api-admin/v1`.

## Fluxo implementado — Villefort

1. **Domínio:** `villefortentrega.com.br` resolve para organização `120`.
2. **Login anônimo:** usuário `loja` + chave pública de cliente do bundle.
3. **Busca:** `GET /org/120/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/leite?page=1`.
4. Headers de tenant:
   - `OrganizationId`
   - `DomainKey`
   - `Authorization: Bearer ...`
   - `sessao-id`

### Configuração

A chave é pública no bundle, mas **não é versionada**:

```env
ENABLE_REVERSE_API=true
VIPCOMMERCE_LOJA_KEY=<chave-publica-de-loja>
```

Sem a chave, o adapter falha com mensagem clara.

### Campos usados

| Campo | Uso |
|---|---|
| `descricao` | nome |
| `preco` | preço efetivo |
| `preco_original` | preço de lista, se maior |
| `codigo_barras` | EAN |
| `produto_id` + `link` | URL do produto |
| `imagem` | imagem (CDN VipCommerce) |
| `disponivel` | estoque/disponibilidade |
| `unidade_sigla` | apoio; o tamanho vem do nome |
| `paginator.total_pages` | paginação |

## Status

- **Villefort:** ✅ experimental, validado ao vivo com busca por `leite`.
- **Pinheiro, Nordestão, Diniz:** 🔬 fluxo conhecido; ainda não configurados.
  É necessário revisar ToS, confirmar domínio/organização e criar fixture.

## Riscos

- Plataforma não documentada; endpoints podem mudar.
- A chave é pública, mas deve ficar fora do repositório.
- Preço e sortimento variam por filial/centro de distribuição.
- Revisar ToS antes de uso público.
- Não usar login de cliente, token de usuário ou contornar challenge.
