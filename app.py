"""UI Streamlit — apresentação e leitura de mercado. Nenhum HTTP aqui."""

from __future__ import annotations

import html
import logging
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from src import config
from src.aggregator import rank, search, sort_products
from src.insights import (
    MarketSummary,
    build_market_summary,
    chain_comparison,
    format_brl,
    format_pct,
    market_insights,
    reference_group,
)
from src.matching import best_in_group, group_products
from src.models import ChainResult, Product
from src.units import format_size

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(
    page_title="Radar de Preço NE",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_CSS = """
<style>
:root {
  --cn-ink: #111827;
  --cn-muted: #6B7280;
  --cn-line: #E5E1D8;
  --cn-paper: #F6F5F1;
  --cn-card: #FFFFFF;
  --cn-accent: #0F766E;
  --cn-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.stApp { background: var(--cn-paper); }
.block-container { max-width: 1240px; padding-top: 2.2rem; padding-bottom: 3rem; }
h1, h2, h3 { color: var(--cn-ink); letter-spacing: -0.02em; }
h1 { font-size: clamp(2.1rem, 4vw, 3.1rem); font-weight: 650; margin-bottom: .1rem; }
.cn-kicker {
  color: var(--cn-accent); font-size: .72rem; font-weight: 750;
  letter-spacing: .18em; text-transform: uppercase; margin-bottom: .25rem;
}
.cn-subtitle {
  color: var(--cn-muted); font-size: 1rem; line-height: 1.55;
  max-width: 760px; margin: 0 0 1.35rem 0;
}
.cn-label {
  color: var(--cn-muted); font-size: .7rem; font-weight: 700;
  letter-spacing: .14em; text-transform: uppercase; margin: .85rem 0 .35rem;
}
.cn-section-title {
  color: var(--cn-muted); font-size: .72rem; font-weight: 750;
  letter-spacing: .14em; text-transform: uppercase; margin-bottom: .55rem;
}
.cn-kpi {
  background: var(--cn-card); border: 1px solid var(--cn-line);
  border-radius: 14px; min-height: 112px; padding: .9rem 1rem .8rem;
}
.cn-kpi__label {
  color: var(--cn-muted); font-size: .68rem; font-weight: 700;
  letter-spacing: .13em; text-transform: uppercase;
}
.cn-kpi__value {
  color: var(--cn-ink); font-family: var(--cn-mono); font-size: 1.55rem;
  font-weight: 650; letter-spacing: -.04em; line-height: 1.25; margin-top: .25rem;
}
.cn-kpi--accent .cn-kpi__value { color: var(--cn-accent); }
.cn-kpi__detail {
  color: var(--cn-muted); font-size: .76rem; line-height: 1.35;
  margin-top: .45rem;
}
.cn-ref-price {
  color: var(--cn-accent); font-family: var(--cn-mono); font-size: 1.45rem;
  font-weight: 650; letter-spacing: -.03em; text-align: right;
}
.cn-gap { height: 1.15rem; }
.cn-footer {
  border-top: 1px solid var(--cn-line); color: var(--cn-muted);
  font-size: .76rem; line-height: 1.5; margin-top: 1.6rem; padding-top: .9rem;
}
[data-testid="stForm"] {
  background: var(--cn-card); border: 1px solid var(--cn-line);
  border-radius: 16px; padding: 1rem 1.1rem 1.15rem;
}
[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--cn-card); border-color: var(--cn-line) !important;
  border-radius: 16px;
}
[data-testid="stDataFrame"] {
  border: 1px solid var(--cn-line); border-radius: 12px; overflow: hidden;
}
[data-testid="stExpander"] {
  background: var(--cn-card); border: 1px solid var(--cn-line);
  border-radius: 12px;
}
[data-testid="stCaptionContainer"] { color: var(--cn-muted); }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { display: none; }
@media (max-width: 700px) {
  .block-container { padding-top: 1.2rem; }
  .cn-kpi { min-height: auto; }
  .cn-ref-price { text-align: left; }
}
</style>
"""


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def buscar(
    termo: str, redes: tuple[str, ...], incluir_reverse: bool
) -> list[ChainResult]:
    """Cache de 5 min. A chamada HTTP fica no aggregator, nunca na UI."""

    return search(termo, chain_slugs=redes, include_reverse=incluir_reverse)


def _inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _render_header() -> None:
    st.markdown(
        '<div class="cn-kicker">Inteligência de preços · Nordeste</div>',
        unsafe_allow_html=True,
    )
    st.title("Radar de Preço NE")
    st.markdown(
        '<p class="cn-subtitle">Compare embalagens equivalentes entre cinco '
        "redes VTEX e fontes experimentais. O ranking usa o conteúdo total da "
        "embalagem — inclusive multipacks — para uma comparação justa.</p>",
        unsafe_allow_html=True,
    )


def _render_search() -> None:
    with st.form("busca_form"):
        query_col, button_col = st.columns([5, 1], vertical_alignment="bottom")
        with query_col:
            termo = st.text_input(
                "Produto",
                placeholder="Ex.: leite integral 1l, arroz 5kg, detergente",
                key="termo",
                label_visibility="collapsed",
            )
        with button_col:
            submitted = st.form_submit_button(
                "Buscar",
                type="primary",
                width="stretch",
                key="buscar",
            )

        st.markdown(
            '<div class="cn-label">Redes consultadas</div>',
            unsafe_allow_html=True,
        )
        reverse_slugs = {chain.slug for chain in config.TIER_B}
        available_chains = tuple(config.TIER_A) + tuple(
            chain for chain in config.TIER_B if chain.implemented
        )
        selected: list[str] = []
        for start in range(0, len(available_chains), 4):
            row = available_chains[start : start + 4]
            columns = st.columns(len(row))
            for column, chain in zip(columns, row, strict=True):
                is_reverse = chain.slug in reverse_slugs
                reverse_disabled = is_reverse and not config.ENABLE_REVERSE_API
                default_on = not reverse_disabled and (
                    not is_reverse
                    or chain.slug != "villefort"
                    or bool(config.VIPCOMMERCE_LOJA_KEY)
                )
                help_text = None
                if reverse_disabled:
                    help_text = "Ative ENABLE_REVERSE_API para usar esta fonte."
                elif chain.slug == "villefort" and not config.VIPCOMMERCE_LOJA_KEY:
                    help_text = "Configure VIPCOMMERCE_LOJA_KEY para usar esta fonte."
                elif is_reverse:
                    help_text = "Fonte experimental (Tier B)."
                with column:
                    if st.checkbox(
                        chain.name,
                        value=default_on,
                        key=f"rede_{chain.slug}",
                        disabled=reverse_disabled,
                        help=help_text,
                    ):
                        selected.append(chain.slug)

        if not config.ENABLE_REVERSE_API:
            st.caption("Tier B desativado por ENABLE_REVERSE_API=false.")
        incluir_reverse = any(slug in reverse_slugs for slug in selected)

    if submitted:
        if not termo.strip():
            st.warning("Digite um produto para buscar.")
        elif not selected:
            st.warning("Selecione pelo menos uma rede.")
        else:
            st.session_state["query"] = {
                "termo": termo.strip(),
                "redes": tuple(selected),
                "reverse": bool(incluir_reverse),
            }


def _render_initial() -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="cn-section-title">Como começar</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            "`leite integral 1l` · `arroz 5kg` · `detergente` · "
            "`café 500g` · `coca cola 2l`"
        )
        st.caption(
            "A busca consulta cinco redes VTEX e, quando habilitadas, as fontes "
            "experimentais Grupo Mateus e Villefort. Cache de cinco minutos. "
            "Itens sem tamanho identificado ficam fora do ranking por unidade."
        )


def _kpi(label: str, value: str, detail: str, tone: str = "") -> None:
    classes = f"cn-kpi {tone}".strip()
    st.markdown(
        f'<div class="{classes}">'
        f'<div class="cn-kpi__label">{html.escape(label)}</div>'
        f'<div class="cn-kpi__value">{html.escape(value)}</div>'
        f'<div class="cn-kpi__detail">{html.escape(detail)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _gap() -> None:
    st.markdown('<div class="cn-gap"></div>', unsafe_allow_html=True)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _render_kpis(ranking, summary: MarketSummary) -> None:
    best = ranking.best_overall
    columns = st.columns(4)
    with columns[0]:
        if best is None:
            _kpi("Menor preço", "—", "Sem item com tamanho identificado")
        else:
            _kpi(
                "Menor preço",
                format_brl(best.price),
                f"{_truncate(best.chain, 28)} · "
                f"{format_size(best.package_size, best.package_unit)}",
                "cn-kpi--accent",
            )
    with columns[1]:
        _kpi(
            "Economia",
            format_pct(ranking.comparable_savings_pct),
            (
                "mesmo produto/tamanho"
                if ranking.comparable_savings_pct is not None
                else "sem par comparável"
            ),
        )
    with columns[2]:
        detail = "redes com resultado"
        if summary.errors:
            failure = "falha" if summary.errors == 1 else "falhas"
            detail += f" · {summary.errors} {failure}"
        _kpi(
            "Cobertura",
            f"{summary.chains_with_results}/{summary.chains_total}",
            detail,
        )
    with columns[3]:
        _kpi(
            "Comparáveis",
            str(summary.comparable_products),
            f"{summary.total_products} coletados · "
            f"{summary.missing_size} sem tamanho",
        )


def _render_chart(comparison) -> None:
    labels = []
    for index, offer in enumerate(comparison):
        labels.append(
            {
                "Rede": offer.chain,
                "Preço": offer.product.price,
                "Texto": format_brl(offer.product.price).removeprefix("R$ "),
                "Destaque": "Menor" if index == 0 else "Demais",
            }
        )
    data = pd.DataFrame(labels)
    order = [offer.chain for offer in comparison]
    max_value = max(offer.product.price for offer in comparison)

    base = alt.Chart(data).encode(
        y=alt.Y(
            "Rede:N",
            sort=order,
            title=None,
            axis=alt.Axis(
                labelFontSize=12,
                labelLimit=180,
                ticks=False,
                domain=False,
                labelPadding=8,
            ),
        ),
        x=alt.X(
            "Preço:Q",
            title="Preço (R$)",
            scale=alt.Scale(domain=[0, max_value * 1.22]),
            axis=alt.Axis(
                format=".2f",
                grid=True,
                gridColor="#E5E1D8",
                domain=False,
                tickCount=4,
                labelFontSize=11,
            ),
        ),
    )
    bars = base.mark_bar(size=18).encode(
        color=alt.Color(
            "Destaque:N",
            scale=alt.Scale(
                domain=["Menor", "Demais"],
                range=["#0F766E", "#CBD5E1"],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("Rede:N", title="Rede"),
            alt.Tooltip("Preço:Q", format=".2f", title="Preço"),
        ],
    )
    text = base.mark_text(
        align="left",
        dx=6,
        fontSize=11,
        color="#111827",
    ).encode(text=alt.Text("Texto:N"))

    chart = (
        (bars + text)
        .properties(height=max(140, 38 * len(data)))
        .configure_view(stroke=None)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_reference(
    best: Product | None,
    groups,
) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="cn-section-title">Produto de referência</div>',
            unsafe_allow_html=True,
        )
        if best is None:
            st.write("Nenhum item com tamanho identificado para comparar por unidade.")
            return

        title_col, price_col = st.columns([3, 1])
        with title_col:
            st.markdown(f"#### {best.name}")
            ean = best.ean or "EAN não informado"
            st.caption(
                f"{best.chain} · {format_size(best.package_size, best.package_unit)}"
                f" · {ean}"
            )
        with price_col:
            st.markdown(
                f'<div class="cn-ref-price">'
                f"{html.escape(format_brl(best.price))}"
                "</div>",
                unsafe_allow_html=True,
            )
            st.caption("preço")

        group = reference_group(groups, best)
        comparison = chain_comparison(group)
        if len(comparison) >= 2:
            _render_chart(comparison)
        else:
            st.caption(
                "O mesmo produto/tamanho não aparece em outra rede nesta busca; "
                "não há comparação direta."
            )


def _render_market_read(
    ranking,
    summary: MarketSummary,
    comparison,
) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="cn-section-title">Leitura do mercado</div>',
            unsafe_allow_html=True,
        )
        for insight in market_insights(ranking, summary, comparison):
            st.markdown(f"- {insight}")


def _product_key(product: Product) -> tuple[str, str, float, str]:
    return (product.chain_slug, product.url, product.price, product.name)


def _build_table(
    products: list[Product],
    best_overall: Product | None,
    group_bests: set[tuple[str, str, float, str]],
) -> pd.DataFrame:
    overall_key = _product_key(best_overall) if best_overall else None
    rows: list[dict[str, object]] = []

    for product in sort_products(products):
        key = _product_key(product)
        if key == overall_key:
            highlight = "Menor geral"
        elif key in group_bests:
            highlight = "Menor do grupo"
        else:
            highlight = ""

        discount = ""
        if product.list_price and product.list_price > product.price:
            discount = f"{(1 - product.price / product.list_price) * 100:.0f}%"

        rows.append(
            {
                "Produto": product.name,
                "Rede": product.chain,
                "Preço": product.price,
                "Tamanho": format_size(product.package_size, product.package_unit),
                "Desconto": discount,
                "Link": product.url,
                "Destaque": highlight,
            }
        )

    return pd.DataFrame(rows)


def _render_table(
    products: list[Product],
    best_overall: Product | None,
    results: list[ChainResult],
    termo: str,
) -> None:
    groups = group_products(products)
    group_bests: set[tuple[str, str, float, str]] = set()
    for group in groups:
        if len({product.chain for product in group.products}) < 2:
            continue
        best = best_in_group(group)
        if best is not None and best.unit_price is not None:
            group_bests.add(_product_key(best))

    table = _build_table(products, best_overall, group_bests)

    title_col, action_col = st.columns([4, 1], vertical_alignment="bottom")
    with title_col:
        st.markdown(
            '<div class="cn-section-title">Resultados</div>',
            unsafe_allow_html=True,
        )
    with action_col:
        _render_download(table, termo)

    st.caption(
        "Ordenado pelo melhor preço por conteúdo da embalagem. "
        "Itens sem tamanho identificado aparecem no fim."
    )
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=460,
        column_config={
            "Produto": st.column_config.TextColumn("Produto", width="large"),
            "Rede": st.column_config.TextColumn("Rede", width="medium"),
            "Preço": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
            "Tamanho": st.column_config.TextColumn("Tamanho"),
            "Desconto": st.column_config.TextColumn("Desconto", width="small"),
            "Link": st.column_config.LinkColumn("Link", display_text="Abrir"),
            "Destaque": st.column_config.TextColumn("Destaque", width="medium"),
        },
    )

    similar = sum(1 for group in groups if group.similar and len(group.products) > 1)
    if similar:
        st.caption(
            f"{similar} grupo(s) usam correspondência aproximada de nome. "
            "Confira o produto antes de comprar."
        )


def _render_download(table: pd.DataFrame, termo: str) -> None:
    csv = table.to_csv(sep=";", index=False, decimal=",", na_rep="")
    safe_term = "".join(
        char if char.isalnum() else "-" for char in termo.lower()
    ).strip("-")
    filename = f"radar-preco-{safe_term or 'busca'}-{datetime.now():%Y%m%d}.csv"
    st.download_button(
        "Exportar CSV",
        data=csv.encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        width="stretch",
    )


def _render_errors(results: list[ChainResult]) -> None:
    errors = [result for result in results if result.error]
    if not errors:
        return
    with st.expander(f"Falhas em {len(errors)} rede(s)"):
        for result in errors:
            st.write(f"**{result.chain}:** {result.error}")


def _render_sources(results: list[ChainResult], summary: MarketSummary) -> None:
    with st.expander("Fontes e qualidade dos dados"):
        rows = [
            {
                "Rede": result.chain,
                "Itens": len(result.products),
                "Tempo (ms)": result.elapsed_ms,
                "Status": result.error or "OK",
            }
            for result in results
        ]
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            column_config={
                "Rede": st.column_config.TextColumn("Rede"),
                "Itens": st.column_config.NumberColumn("Itens", format="%d"),
                "Tempo (ms)": st.column_config.NumberColumn("Tempo (ms)", format="%d"),
                "Status": st.column_config.TextColumn("Status"),
            },
        )
        notes = [
            (
                "Tier B desligado"
                if not config.ENABLE_REVERSE_API
                else "Tier B habilitado"
            ),
            f"{summary.comparable_products} itens comparáveis",
        ]
        if summary.missing_size:
            notes.append(f"{summary.missing_size} sem tamanho")
        if summary.similar_groups:
            notes.append(f"{summary.similar_groups} grupos aproximados")
        st.caption(" · ".join(notes))


def _render_footer(summary: MarketSummary | None) -> None:
    collected = "—"
    if summary is not None and summary.collected_at is not None:
        collected = summary.collected_at.astimezone().strftime("%d/%m/%Y %H:%M")
    st.markdown(
        '<div class="cn-footer">Preço de catálogo público; pode variar por '
        "loja/CEP. Não inclui preço de clube ou fidelidade. "
        f"Coletado em {collected}. Projeto não afiliado às redes.</div>",
        unsafe_allow_html=True,
    )


def _render_empty(results: list[ChainResult]) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="cn-section-title">Nenhum resultado</div>',
            unsafe_allow_html=True,
        )
        st.markdown("Tente um termo mais genérico ou marque mais redes.")
        st.markdown("`leite` · `arroz` · `detergente` · `café`")
    _render_errors(results)
    _render_footer(None)


def _render_results(results: list[ChainResult], termo: str) -> None:
    products = [product for result in results for product in result.products]
    if not products:
        _render_empty(results)
        return

    groups = group_products(products)
    summary = build_market_summary(results, products, groups)
    ranking = rank(results)

    _render_kpis(ranking, summary)
    _gap()

    best_group = reference_group(groups, ranking.best_overall)
    comparison = chain_comparison(best_group)
    _render_reference(ranking.best_overall, groups)
    _gap()
    _render_market_read(ranking, summary, comparison)
    _render_table(products, ranking.best_overall, results, termo)
    _render_sources(results, summary)
    _render_footer(summary)


def main() -> None:
    _inject_styles()
    _render_header()
    _render_search()

    query = st.session_state.get("query")
    if not query:
        _render_initial()
        return

    with st.spinner("Consultando redes públicas..."):
        results = buscar(query["termo"], query["redes"], query["reverse"])

    _render_results(results, query["termo"])


if __name__ == "__main__":
    main()
