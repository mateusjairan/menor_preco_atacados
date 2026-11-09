# Assaí — sem catálogo público de produtos

Rede: **Assaí Atacadista**
Site: `https://www.assai.com.br`
Status: **não suportado** no v1.

## O que foi verificado

- `GET /busca?s=leite` retorna **busca de conteúdo do site** (lojas, blog,
  páginas institucionais), não produtos com preço.
- `GET /ofertas` retorna o encarte/ofertas em formato de página, sem catálogo
  estruturado por produto.
- `/api/catalog_system/pub/products/search`, `/graphql` e `/api/rest/...`
  retornam `404`.
- O app **Meu Assaí** e a compra online usam app/delivery parceiros
  (Rappi/Uber), sem catálogo web anônimo equivalente ao das redes de atacado.

## Por que não implementar

Não há endpoint público anônimo com produto, preço, estoque e URL. Implementar
exigiria API de parceiro, login ou engenharia reversa do app — fora do escopo e
dos limites de compliance do projeto.

## Próximo passo possível

Se houver contrato/parceria com o Assaí ou acesso a um feed oficial de
catálogo, criar um adapter novo com:

- autenticação fornecida pelo parceiro;
- fixture sanitizada;
- testes offline;
- feature flag;
- documentação de ToS.

Sem isso, a rede fica fora do painel em vez de entregar um checkbox que sempre
falha.
