# Changelog

## v1.2.0 — 2026-11-09

- Implementa VipCommerce anônimo para a rede Villefort (Tier B experimental).
- Adiciona resolução de organização por domínio, login anônimo de loja, busca,
  paginação e parsing de preço/disponibilidade.
- Adiciona `VIPCOMMERCE_LOJA_KEY` via ambiente; nenhuma chave é versionada.
- Adiciona fixtures e testes offline do VipCommerce.

## v1.1.0 — 2026-11-09

- Adiciona Grupo Mateus (Mateus Mais) como fonte Tier B experimental, com
  resolução de loja por praça e busca anônima via Meilisearch.
- Adiciona `platform` ao `ChainConfig` e factory de adapters por plataforma.
- Documenta a limitação do Assaí: não há catálogo público de produtos; compra
  online somente via app/Rappi/Uber.
- Adiciona testes do adapter Mateus, fixtures e documentação de API.

## v1.0.0 — 2026-11-09

- Busca comparativa em cinco redes Tier A via API pública VTEX.
- Preço unitário por kg, litro e unidade, com suporte a multipacks e kits.
- Matching cross-chain por EAN e fallback fuzzy, sem cruzar tamanhos.
- Backfill de tamanho por EAN entre redes.
- Painel de leitura de mercado com cobertura, economia e qualidade dos dados.
- Exportação CSV compatível com Excel BR.
- Tier B desligado por padrão.
- 133 testes offline, lint e formatação no CI.
