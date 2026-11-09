# Contribuindo

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Antes de abrir um PR

```bash
pytest -q
ruff check .
black --check .
```

## Regras do projeto

- `app.py` não faz HTTP; toda coleta fica em `src/`.
- Um adapter por plataforma, não por rede.
- Não versionar `.env`, tokens, cookies ou chaves.
- Testes são offline: use fixtures e monkeypatch, nunca rede real no CI.
- Mudança de comportamento exige atualização de `AGENTS.md`, `docs/api/` e testes.
- Respeite os termos de uso das redes. Se uma fonte bloquear de forma
  consistente, remova a fonte em vez de contornar a proteção.

## Escopo de issues

Bom para issue:

- bug reproduzível com termo e rede;
- melhoria de parsing de tamanho/unidade;
- nova fonte pública homologada;
- melhoria de acessibilidade ou performance.

Fora do escopo:

- burlar captcha, login ou challenge JS;
- rotacionar proxies para ignorar bloqueio;
- coletar dados pessoais.
