# VipCommerce — Tier B (não homologado)

Redes alvo: **Pinheiro (Bom Vizinho)**, **Nordestão** e **Diniz**.

## Arquitetura identificada

White-label "Supermercados Online". O bundle do site expõe o fluxo:

```
POST {api}/auth/loja/login          -> token anônimo da loja
GET  {api}/filiais/dominio/{host}   -> orgId, filialId, domainKey
GET  {api}/org/{orgId}/...          -> catálogo, busca, produto
```

- `api` = `https://services.vipcommerce.com.br/api-admin/v1` (modo horizontalizado).
- Headers de tenant: `DomainKey`, `OrganizationId`, `sessao-id`.
- O token é obtido pelo próprio front-end anônimo.

## Status no projeto

**🔬 Não homologado.** O adapter (`src/adapters/vipcommerce.py`) existe apenas
como placeholder e levanta `AdapterError` com mensagem clara. Ele só é
construído quando `ENABLE_REVERSE_API=true`.

Motivos para não ligar ainda:

1. Revisar os ToS de cada rede antes de qualquer chamada.
2. Confirmar que a chamada é anônima (sem login de cliente).
3. Capturar request/response reais e mapear os campos de catálogo/preço.
4. Salvar fixture sanitizada em `tests/fixtures/` e escrever testes offline.
5. Nunca versionar token, cookie ou chave.

## Próximo passo

Com ToS aprovado: capturar a busca no DevTools, reproduzir em `curl_cffi` com
headers mínimos, documentar os campos observados aqui e só então implementar o
parser. Sem contrato observado, **não inventar campo**.
