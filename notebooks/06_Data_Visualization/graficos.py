"""graficos.py — gráficos bonitos numa só linha.

Um pequeno módulo feito para este notebook. Cada função desenha um tipo de
gráfico já com bom aspeto: título e subtítulo alinhados à esquerda, grelha
discreta, cores escolhidas com propósito e valores escritos onde fazem falta.

Como usar (no notebook, na mesma pasta que este ficheiro)::

    from graficos import aplicar_tema, barras, guardar

    aplicar_tema()
    fig, ax = barras({"Lisboa": 545, "Porto": 232, "Braga": 193},
                     titulo="Lisboa é a maior cidade",
                     subtitulo="População, em milhares de habitantes")
    guardar(fig, "cidades")

Todas as funções de gráfico devolvem ``(fig, ax)``: a figura e os eixos do
Matplotlib. Assim podes sempre afinar mais alguma coisa à mão, por exemplo
``ax.set_xlim(0, 100)``.

As cores vêm de uma paleta validada para daltonismo (``PALETA``). A ordem das
cores é fixa: a 1.ª categoria é sempre azul, a 2.ª laranja, a 3.ª verde-água...

Tipo de letra: Inter (licença SIL Open Font License, ver ``fonts/OFL.txt``).
Se a pasta ``fonts/`` não existir, o módulo usa o tipo de letra por omissão.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib import patheffects
from matplotlib.colors import LinearSegmentedColormap, to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.ticker import FuncFormatter
from matplotlib.transforms import offset_copy

__all__ = [
    "PALETA", "CORES", "aplicar_tema", "barras", "linha", "histograma",
    "dispersao", "caixa", "donut", "mapa_calor", "nuvem_palavras",
    "moldura", "guardar",
]

# ---------------------------------------------------------------------------
# Cores
# ---------------------------------------------------------------------------

#: Paleta categórica (modo claro), por esta ordem. Validada para daltonismo
#: (protanopia/deuteranopia) entre cores vizinhas; as 3 primeiras distinguem-se
#: todas entre si, por isso são as ideais para gráficos de dispersão.
PALETA: list[str] = [
    "#2a78d6",  # azul
    "#eb6834",  # laranja
    "#1baf7a",  # verde-água
    "#eda100",  # amarelo
    "#e87ba4",  # magenta
    "#008300",  # verde
    "#6250d6",  # violeta
    "#e34948",  # vermelho
]

#: As mesmas cores com nomes, para usares à mão: ``CORES["laranja"]``.
CORES: dict[str, str] = {
    "azul": PALETA[0], "laranja": PALETA[1], "verde_agua": PALETA[2],
    "amarelo": PALETA[3], "magenta": PALETA[4], "verde": PALETA[5],
    "violeta": PALETA[6], "vermelho": PALETA[7], "cinzento": "#d3d1c9",
}

_CLARO: dict[str, Any] = {
    "fundo": "#fcfcfb", "tinta": "#0b0b0b", "tinta2": "#52514e", "suave": "#898781",
    "grelha": "#e1e0d9", "eixo": "#c3c2b7", "neutro": "#d3d1c9",
    "paleta": PALETA,
    "sequencial": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
    "divergente": ["#104281", "#2a78d6", "#9ec5f4", "#f0efec", "#f3b0af", "#e34948", "#9c2423"],
}
_ESCURO: dict[str, Any] = {
    "fundo": "#1a1a19", "tinta": "#f0efec", "tinta2": "#c3c2b7", "suave": "#898781",
    "grelha": "#2c2c2a", "eixo": "#383835", "neutro": "#4a4a46",
    "paleta": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"],
    "sequencial": ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"],
    "divergente": ["#9ec5f4", "#3987e5", "#184f95", "#383835", "#9c2423", "#e66767", "#f3b0af"],
}
_TEMA: dict[str, Any] = dict(_CLARO)
# o Inter vem em várias famílias ("Inter", "Inter SemiBold"...): silencia avisos inofensivos de pesos
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
_TEMA_APLICADO = False

# ---------------------------------------------------------------------------
# Tipo de letra
# ---------------------------------------------------------------------------

_PASTA_FONTES = Path(__file__).resolve().parent / "fonts"
_FONTES = {"texto": ["DejaVu Sans"], "media": ["DejaVu Sans"], "titulo": ["DejaVu Sans"]}
_PESOS = {"texto": "normal", "media": "normal", "titulo": "bold"}


def _registar_fontes() -> bool:
    """Regista o Inter (se existir em ``fonts/``). Devolve True se correu bem."""
    ficheiros = {
        "texto": _PASTA_FONTES / "Inter-Regular.ttf",
        "media": _PASTA_FONTES / "Inter-Medium.ttf",
        "titulo": _PASTA_FONTES / "Inter-SemiBold.ttf",
        "negrito": _PASTA_FONTES / "Inter-Bold.ttf",
    }
    if not all(f.exists() for f in ficheiros.values()):
        return False
    try:
        for f in ficheiros.values():
            font_manager.fontManager.addfont(str(f))
    except Exception:  # ficheiro estragado, permissões...: usa o tipo de letra por omissão
        return False
    # Cada peso fica registado como uma família própria ("Inter Medium"...);
    # o "DejaVu Sans" no fim serve de reserva para símbolos que o Inter não tem.
    _FONTES["texto"] = ["Inter", "DejaVu Sans"]
    _FONTES["media"] = ["Inter Medium", "Inter", "DejaVu Sans"]
    _FONTES["titulo"] = ["Inter SemiBold", "Inter", "DejaVu Sans"]
    _PESOS.update(texto="normal", media="medium", titulo="semibold")
    return True


def _fonte(papel: str = "texto") -> dict[str, Any]:
    """Argumentos de tipo de letra para um papel: 'texto', 'media' ou 'titulo'."""
    return {"fontfamily": _FONTES[papel], "fontweight": _PESOS[papel]}


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------

def aplicar_tema(escuro: bool = False) -> None:
    """Aplica o estilo do módulo a **todos** os gráficos seguintes.

    Muda o tipo de letra, as cores, a grelha e as margens do Matplotlib (e,
    por arrasto, do Seaborn). As funções deste módulo chamam-na sozinhas se
    te esqueceres, mas chamá-la no início deixa também os teus gráficos
    "à mão" (``plt.plot``, ``sns.histplot``...) com o mesmo aspeto.

    Args:
        escuro: ``True`` para um fundo escuro (ótimo para slides com fundo
            preto). As cores são versões ajustadas da mesma paleta.

    Exemplo::

        aplicar_tema()             # fundo claro
        aplicar_tema(escuro=True)  # fundo escuro
    """
    global _TEMA_APLICADO
    _TEMA.clear()
    _TEMA.update(_ESCURO if escuro else _CLARO)
    tem_inter = _registar_fontes()
    t = _TEMA
    mpl.rcParams.update({
        "font.family": _FONTES["texto"],
        "font.size": 10.5,
        "text.color": t["tinta"],
        "figure.facecolor": t["fundo"],
        "figure.dpi": 110,
        "savefig.facecolor": t["fundo"],
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.35,
        "axes.facecolor": t["fundo"],
        "axes.edgecolor": t["eixo"],
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "axes.labelcolor": t["tinta2"],
        "axes.labelsize": 10,
        "axes.labelpad": 8,
        "axes.titlesize": 14,
        "axes.titleweight": "semibold" if tem_inter else "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 14,
        "axes.titlecolor": t["tinta"],
        "axes.prop_cycle": mpl.cycler(color=t["paleta"]),
        "grid.color": t["grelha"],
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": t["eixo"],
        "ytick.color": t["eixo"],
        "xtick.labelcolor": t["tinta2"],
        "ytick.labelcolor": t["tinta2"],
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "xtick.major.pad": 6,
        "ytick.major.pad": 6,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "legend.labelcolor": t["tinta2"],
        "lines.linewidth": 2,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "lines.markersize": 7,
        "patch.linewidth": 0,
        "image.cmap": "viridis",
        "boxplot.medianprops.color": t["tinta"],
    })
    _TEMA_APLICADO = True


def _garantir_tema() -> dict[str, Any]:
    if not _TEMA_APLICADO:
        aplicar_tema()
    return _TEMA


def _cmap_sequencial() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("graficos_seq", _TEMA["sequencial"])


def _cmap_divergente() -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list("graficos_div", _TEMA["divergente"])


# ---------------------------------------------------------------------------
# Pequenas ajudas internas
# ---------------------------------------------------------------------------

def _numero(valor: float, formato: str | None = None) -> str:
    """Formata um número à portuguesa: 1 234,5 (espaço nos milhares, vírgula nas décimas)."""
    if formato is None:
        if float(valor).is_integer():
            formato = "{:,.0f}"
        elif abs(valor) < 10:
            formato = "{:,.2f}"
        else:
            formato = "{:,.1f}"
    texto = formato.format(valor)
    return texto.translate(str.maketrans({",": " ", ".": ",", "-": "−"}))


def _formatar_eixo(ax, eixo: str = "y", percentagem: bool = False) -> None:
    """Escreve os números de um eixo à portuguesa (2,5 · 3 000 · 15%)."""
    def marca(v, _pos):
        texto = f"{v:,.6f}".rstrip("0").rstrip(".")
        texto = texto.translate(str.maketrans({",": " ", ".": ",", "-": "−"}))
        return texto + ("%" if percentagem else "")
    for e in ("x", "y") if eixo == "both" else (eixo,):
        getattr(ax, f"{e}axis").set_major_formatter(FuncFormatter(marca))


def _para_serie(dados: Any) -> pd.Series:
    """Aceita dict, Counter, pandas Series ou lista de pares (rótulo, valor)."""
    if isinstance(dados, pd.Series):
        return dados.copy()
    if isinstance(dados, Mapping):
        return pd.Series(dict(dados))
    pares = list(dados)
    return pd.Series([v for _, v in pares], index=[str(r) for r, _ in pares])


def _nova_figura(largura: float, altura: float):
    t = _garantir_tema()
    fig, ax = plt.subplots(figsize=(largura, altura))
    fig.set_facecolor(t["fundo"])
    ax.set_facecolor(t["fundo"])
    return fig, ax


def _pontos_por_unidade(ax) -> tuple[float, float]:
    """Quantos pontos tipográficos (1/72 pol.) mede uma unidade de dados em x e em y."""
    fig = ax.figure
    largura_pt = ax.bbox.width * 72 / fig.dpi
    altura_pt = ax.bbox.height * 72 / fig.dpi
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return largura_pt / abs(x1 - x0), altura_pt / abs(y1 - y0)


def _barra_arredondada(pos: float, valor: float, espessura: float, rx: float, ry: float,
                       horizontal: bool, **estilo) -> PathPatch:
    """Uma barra com os cantos do lado do valor arredondados e a base reta."""
    s = 1 if valor >= 0 else -1
    v = abs(valor)
    a = min(rx if horizontal else ry, v)            # raio ao longo do valor
    b = min(ry if horizontal else rx, espessura / 2)  # raio na espessura
    k = 0.5523  # constante para aproximar um quarto de círculo com uma curva de Bézier
    w0, w1 = pos - espessura / 2, pos + espessura / 2
    # pontos no referencial (u = ao longo do valor, w = espessura)
    pts = [
        (0, w0), (v - a, w0),
        (v - a + k * a, w0), (v, w0 + b - k * b), (v, w0 + b),
        (v, w1 - b),
        (v, w1 - b + k * b), (v - a + k * a, w1), (v - a, w1),
        (0, w1), (0, w0),
    ]
    codigos = [MplPath.MOVETO, MplPath.LINETO,
               MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
               MplPath.LINETO,
               MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
               MplPath.LINETO, MplPath.CLOSEPOLY]
    if horizontal:
        vertices = [(s * u, w) for u, w in pts]
    else:
        vertices = [(w, s * u) for u, w in pts]
    return PathPatch(MplPath(vertices, codigos), **estilo)


def _itens_legenda(itens: Sequence[tuple[str, str, str]]) -> list[Line2D]:
    """Cria marcas de legenda a partir de (rótulo, cor, tipo) — tipo: 'ponto', 'linha' ou 'barra'."""
    marcas = []
    for rotulo, cor, tipo in itens:
        if tipo == "linha":
            marcas.append(Line2D([], [], color=cor, lw=2.4, label=rotulo))
        elif tipo == "barra":
            marcas.append(Line2D([], [], color=cor, marker="s", markersize=9, lw=0, label=rotulo))
        else:
            marcas.append(Line2D([], [], color=cor, marker="o", markersize=8, lw=0,
                                 markeredgecolor=_TEMA["fundo"], markeredgewidth=1.2, label=rotulo))
    return marcas


def moldura(fig, ax, titulo: str, subtitulo: str | None = None, fonte: str | None = None,
            legenda: Sequence[tuple[str, str, str]] | None = None) -> None:
    """Acrescenta título, subtítulo, legenda e nota de fonte a um gráfico.

    É o "acabamento" que todas as funções deste módulo usam: o título fica
    alinhado à esquerda, por cima do subtítulo; a legenda (se houver) fica
    numa linha logo abaixo; a fonte dos dados vai para o canto inferior.
    Usa-a quando criares as tuas próprias funções de gráficos.

    Args:
        fig, ax: a figura e os eixos (de ``plt.subplots()``).
        titulo: a mensagem principal do gráfico (de preferência, a conclusão).
        subtitulo: o que está a ser medido e em que unidades.
        fonte: de onde vêm os dados, por exemplo ``"Palmer Penguins"``.
        legenda: lista de ``(rótulo, cor, tipo)`` com tipo ``"ponto"``,
            ``"linha"`` ou ``"barra"``.
    """
    t = _garantir_tema()
    fig.canvas.draw()  # calcula posições reais antes de medir
    r = fig.canvas.get_renderer()
    pt = 72 / fig.dpi
    caixa_eixos = ax.bbox
    caixa_total = ax.get_tightbbox(r)
    x0 = (caixa_total.x0 - caixa_eixos.x0) / caixa_eixos.width  # alinhamento à esquerda
    cursor = max(0.0, (caixa_total.y1 - caixa_eixos.y1) * pt) + 12

    if legenda:
        transf = offset_copy(ax.transAxes, fig=fig, x=0, y=cursor, units="points")
        leg = ax.legend(handles=_itens_legenda(legenda), loc="lower left", bbox_to_anchor=(x0, 1),
                        bbox_transform=transf, ncols=len(legenda), borderaxespad=0, borderpad=0,
                        handlelength=1.2, handletextpad=0.5, columnspacing=1.6,
                        prop={"family": _FONTES["texto"], "size": 9.5})
        cursor += leg.get_window_extent(r).height * pt + 8

    if subtitulo:
        sub = ax.annotate(subtitulo, xy=(x0, 1), xycoords="axes fraction", xytext=(0, cursor),
                          textcoords="offset points", ha="left", va="bottom", fontsize=10.5,
                          color=t["tinta2"], linespacing=1.35, annotation_clip=False, **_fonte("texto"))
        cursor += sub.get_window_extent(r).height * pt + 5

    ax.annotate(titulo, xy=(x0, 1), xycoords="axes fraction", xytext=(0, cursor),
                textcoords="offset points", ha="left", va="bottom", fontsize=15.5,
                color=t["tinta"], linespacing=1.2, annotation_clip=False, **_fonte("titulo"))

    if fonte:
        abaixo = max(0.0, (caixa_eixos.y0 - caixa_total.y0) * pt) + 14
        ax.annotate(f"Fonte: {fonte}", xy=(x0, 0), xycoords="axes fraction", xytext=(0, -abaixo),
                    textcoords="offset points", ha="left", va="top", fontsize=8.5,
                    color=t["suave"], annotation_clip=False, **_fonte("texto"))


def _halo() -> list:
    """Contorno da cor do fundo à volta de um texto, para se ler por cima dos pontos."""
    return [patheffects.withStroke(linewidth=3.2, foreground=_TEMA["fundo"])]


def _cores_por_grupo(grupos: Iterable[Any]) -> dict[Any, str]:
    """Atribui cores fixas aos grupos, por ordem alfabética (a cor segue o grupo, não a posição)."""
    unicos = sorted(pd.unique(pd.Series(list(grupos)).dropna()), key=str)
    paleta = _TEMA["paleta"]
    return {g: (paleta[i] if i < len(paleta) else _TEMA["neutro"]) for i, g in enumerate(unicos)}


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def barras(dados: Any, titulo: str, subtitulo: str | None = None, destaque: str | Sequence[str] | None = None,
           rotulo_valor: str | None = None, formato: str | None = None, maximo: int | None = None,
           ordenar: bool = True, fonte: str | None = None, largura: float = 8.5):
    """Barras horizontais, ordenadas, com o valor escrito na ponta de cada barra.

    Args:
        dados: um ``dict`` (``{"a": 3, "b": 5}``), um ``Counter``, uma pandas
            ``Series`` (o índice dá os nomes) ou uma lista de pares
            ``[("a", 3), ("b", 5)]``.
        titulo: a mensagem do gráfico, de preferência a conclusão.
        subtitulo: o que se mede e em que unidades.
        destaque: o nome (ou lista de nomes) da barra a destacar. As outras
            ficam cinzentas — assim o olhar vai direto ao que interessa.
        rotulo_valor: o nome do eixo dos valores (aparece por baixo).
        formato: como escrever os valores, por exemplo ``"{:.0%}"`` para
            percentagens ou ``"{:.1f}"`` para uma casa decimal.
        maximo: mostra só as ``maximo`` maiores barras.
        ordenar: ``False`` para manter a ordem original (útil para meses, idades...).
        fonte: de onde vêm os dados.
        largura: largura da figura, em polegadas.

    Returns:
        ``(fig, ax)``.

    Exemplo::

        fig, ax = barras({"Python": 52, "R": 18, "Julia": 6},
                         titulo="Python lidera", destaque="Python")
    """
    t = _garantir_tema()
    serie = _para_serie(dados).astype(float)
    if ordenar:
        serie = serie.sort_values(ascending=False, kind="stable")
    if maximo:
        serie = serie.head(maximo)
    rotulos = [str(r) for r in serie.index]
    valores = serie.to_numpy()
    n = len(valores)

    if destaque is None:
        destacados = set(rotulos)
    else:
        destacados = {destaque} if isinstance(destaque, str) else {str(d) for d in destaque}
        desconhecidos = destacados - set(rotulos)
        if desconhecidos:
            print(f"Aviso: {sorted(desconhecidos)} não existe(m) nos dados — nada a destacar.")
    cores = [t["paleta"][0] if r in destacados else t["neutro"] for r in rotulos]

    fig, ax = _nova_figura(largura, 0.42 * n + 1.1)
    posicoes = np.arange(n)[::-1]  # a primeira barra fica em cima
    ax.barh(posicoes, valores, height=0.62, color="none")  # só para o Matplotlib calcular os limites
    menor, maior = min(0.0, valores.min()), max(0.0, valores.max())
    folga = (maior - menor) * 0.14
    ax.set_xlim(menor - (folga if menor < 0 else 0), maior + folga)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_yticks(posicoes, rotulos)
    ax.tick_params(axis="y", labelsize=10.5, labelcolor=t["tinta"])
    ax.tick_params(axis="x", labelbottom=False)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    for lbl in ax.get_yticklabels():
        lbl.set_fontfamily(_FONTES["texto"])
    if rotulo_valor:  # cabeçalho por cima das barras: diz o que os números medem
        ax.annotate(rotulo_valor, xy=(0, n - 0.4), xytext=(0, 6), textcoords="offset points",
                    ha="left", va="bottom", fontsize=9.5, color=t["suave"], **_fonte("media"))
    fig.canvas.draw()

    # barras com ponta arredondada (raio de 3,5 pt), espessura no máximo 18 pt
    ppx, ppy = _pontos_por_unidade(ax)
    espessura = min(0.62, 18 / ppy)
    for barra in list(ax.patches):
        barra.remove()
    for pos, val, cor in zip(posicoes, valores, cores):
        ax.add_patch(_barra_arredondada(pos, val, espessura, 3.5 / ppx, 3.5 / ppy, True,
                                        facecolor=cor, edgecolor="none", zorder=2))
        destacada = destaque is not None and cor != t["neutro"]
        ax.annotate(_numero(val, formato), xy=(val, pos), xytext=(6 if val >= 0 else -6, 0),
                    textcoords="offset points", va="center", ha="left" if val >= 0 else "right",
                    fontsize=10, color=t["tinta"] if destacada else t["tinta2"],
                    **_fonte("titulo" if destacada else "texto"))
    ax.axvline(0, color=t["eixo"], lw=1, zorder=3)  # a linha de base
    if destaque is not None:
        for lbl in ax.get_yticklabels():
            if lbl.get_text() in destacados:
                lbl.set_fontfamily(_FONTES["titulo"])
                lbl.set_fontweight(_PESOS["titulo"])
            else:
                lbl.set_color(t["tinta2"])
    moldura(fig, ax, titulo, subtitulo, fonte)
    return fig, ax


def linha(dados: Any, titulo: str, subtitulo: str | None = None, rotulo_x: str | None = None,
          rotulo_y: str | None = None, media_movel: int | None = None, formato: str | None = None,
          destacar_maximo: bool = True, fonte: str | None = None, largura: float = 9, altura: float = 4.2):
    """Gráfico de linhas: como um valor muda ao longo de uma sequência (tempo, posição...).

    Args:
        dados: uma pandas ``Series`` ou ``dict`` (x = índice/chaves, y = valores),
            ou um ``DataFrame`` em que cada coluna é uma linha diferente (até 4).
        titulo, subtitulo: texto por cima do gráfico.
        rotulo_x, rotulo_y: nomes dos eixos.
        media_movel: se deres um número (ex.: ``50``), a série original fica
            em cinzento claro e desenha-se por cima a média dos últimos N
            valores, que mostra a tendência.
        formato: como escrever os valores (ex.: ``"{:.1f}"``).
        destacar_maximo: marca e escreve o valor máximo (só com uma linha).
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.

    Exemplo::

        fig, ax = linha({2020: 3, 2021: 5, 2022: 9}, titulo="As vendas triplicaram",
                        rotulo_x="Ano", rotulo_y="Vendas (milhares)")
    """
    t = _garantir_tema()
    fig, ax = _nova_figura(largura, altura)
    legenda = None

    if isinstance(dados, pd.DataFrame):
        colunas = list(dados.columns)[:4]
        legenda = []
        for i, col in enumerate(colunas):
            s = dados[col].dropna()
            cor = t["paleta"][i]
            ax.plot(s.index, s.to_numpy(), color=cor, lw=2, zorder=3)
            ax.scatter([s.index[-1]], [s.iloc[-1]], s=46, color=cor, edgecolor=t["fundo"], linewidth=2, zorder=4)
            ax.annotate(_numero(s.iloc[-1], formato), xy=(s.index[-1], s.iloc[-1]), xytext=(8, 0),
                        textcoords="offset points", va="center", fontsize=9.5, color=t["tinta2"])
            legenda.append((str(col), cor, "linha"))
    else:
        s = _para_serie(dados) if not isinstance(dados, pd.Series) else dados.copy()
        s = s.dropna()
        x, y = s.index, s.to_numpy(dtype=float)
        cor = t["paleta"][0]
        if media_movel:
            tendencia = s.rolling(media_movel, min_periods=max(1, media_movel // 2)).mean()
            ax.plot(x, y, color=t["neutro"], lw=0.8, zorder=2)
            ax.plot(x, tendencia.to_numpy(), color=cor, lw=2.4, zorder=3)
            legenda = [("cada valor", t["neutro"], "linha"), (f"média móvel ({media_movel})", cor, "linha")]
            ultimo = tendencia.dropna()
            ax.scatter([ultimo.index[-1]], [ultimo.iloc[-1]], s=46, color=cor,
                       edgecolor=t["fundo"], linewidth=2, zorder=4)
        else:
            ax.fill_between(x, y, min(0, y.min()), color=cor, alpha=0.10, lw=0, zorder=1)
            ax.plot(x, y, color=cor, lw=2, zorder=3)
            ax.scatter([x[-1]], [y[-1]], s=46, color=cor, edgecolor=t["fundo"], linewidth=2, zorder=4)
            ax.annotate(_numero(y[-1], formato), xy=(x[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=9.5, color=t["tinta2"])
            if destacar_maximo and len(y) > 2 and int(np.argmax(y)) != len(y) - 1:
                i = int(np.argmax(y))
                ax.scatter([x[i]], [y[i]], s=46, color=cor, edgecolor=t["fundo"], linewidth=2, zorder=4)
                ax.annotate(f"máximo: {_numero(y[i], formato)}", xy=(x[i], y[i]), xytext=(0, 10),
                            textcoords="offset points", ha="center", va="bottom", fontsize=9.5,
                            color=t["tinta"], path_effects=_halo(), **_fonte("media"))
            if y.min() >= 0:
                ax.set_ylim(bottom=0)
            ax.margins(y=0.15)

    ax.spines["bottom"].set_color(t["eixo"])
    _formatar_eixo(ax, "y")  # o eixo x fica como está (pode ter anos: 2024)
    if rotulo_x:
        ax.set_xlabel(rotulo_x)
    if rotulo_y:
        ax.set_ylabel(rotulo_y)
    moldura(fig, ax, titulo, subtitulo, fonte, legenda)
    return fig, ax


def histograma(dados: Any, coluna: str | None = None, titulo: str = "", subtitulo: str | None = None,
               cor_por: str | None = None, bins: int | str = "auto", rotulo_x: str | None = None,
               rotulo_y: str | None = None, percentagem: bool | None = None, mostrar_mediana: bool = True,
               fonte: str | None = None, largura: float = 9, altura: float = 4.2):
    """Histograma: como se distribuem os valores de uma coluna numérica.

    Args:
        dados: um ``DataFrame`` (indica a ``coluna``) ou simplesmente uma lista/Series de números.
        coluna: o nome da coluna a desenhar.
        titulo, subtitulo: texto por cima do gráfico.
        cor_por: nome de uma coluna de grupos (ex.: ``"especie"``). Cada grupo
            fica com a sua cor, desenhado por cima dos outros (até 3 grupos).
        bins: número de barras (ou ``"auto"``).
        rotulo_x, rotulo_y: nomes dos eixos.
        percentagem: ``True`` mostra % de cada grupo em vez de contagens —
            justo quando os grupos têm tamanhos diferentes. Por omissão é
            ``True`` com grupos e ``False`` sem grupos.
        mostrar_mediana: marca a mediana (sem grupos) ou escreve-a na legenda (com grupos).
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.

    Exemplo::

        fig, ax = histograma(pinguins, "massa_g", titulo="Quanto pesa um pinguim?",
                             rotulo_x="Massa (g)")
    """
    t = _garantir_tema()
    if isinstance(dados, pd.DataFrame):
        df = dados
        if coluna is None:
            raise ValueError("Indica a coluna a desenhar, por exemplo coluna='idade'.")
    else:
        coluna = coluna or "valor"
        df = pd.DataFrame({coluna: pd.Series(list(dados), dtype=float)})
    df = df.dropna(subset=[coluna])
    if percentagem is None:
        percentagem = cor_por is not None
    valores = df[coluna].to_numpy(dtype=float)
    limites = np.histogram_bin_edges(valores, bins=bins)

    fig, ax = _nova_figura(largura, altura)
    legenda = None
    if cor_por is None:
        contagens, _ = np.histogram(valores, bins=limites)
        if percentagem:
            contagens = contagens / contagens.sum() * 100
        ax.stairs(contagens, limites, fill=True, color=t["paleta"][0], zorder=2)
        # separadores finos da cor do fundo entre barras vizinhas
        ax.vlines(limites[1:-1], 0, np.maximum(contagens[:-1], contagens[1:]), color=t["fundo"], lw=1.4, zorder=3)
        if mostrar_mediana:
            mediana = float(np.median(valores))
            topo = contagens.max() * 1.08
            ax.vlines(mediana, 0, topo, color=t["tinta"], lw=1.2, zorder=4)
            ax.annotate(f"mediana: {_numero(mediana)}", xy=(mediana, topo), xytext=(5, 0),
                        textcoords="offset points", ha="left", va="center", fontsize=9.5,
                        color=t["tinta"], path_effects=_halo(), **_fonte("media"))
            ax.set_ylim(top=contagens.max() * 1.18)
    else:
        cores = _cores_por_grupo(df[cor_por])
        legenda = []
        for grupo, cor in cores.items():
            parte = df.loc[df[cor_por] == grupo, coluna].to_numpy(dtype=float)
            contagens, _ = np.histogram(parte, bins=limites)
            if percentagem:
                contagens = contagens / max(1, contagens.sum()) * 100
            ax.stairs(contagens, limites, fill=True, color=to_rgba(cor, 0.10), zorder=2)
            ax.stairs(contagens, limites, color=cor, lw=2, zorder=3)
            texto = str(grupo)
            if mostrar_mediana:
                texto += f" · mediana {_numero(float(np.median(parte)))}"
            legenda.append((texto, cor, "barra"))
        ax.set_ylim(bottom=0)
        ax.margins(y=0.08)

    ax.set_xlim(limites[0], limites[-1])
    ax.spines["bottom"].set_color(t["eixo"])
    _formatar_eixo(ax, "x")
    _formatar_eixo(ax, "y", percentagem=bool(percentagem))
    ax.set_xlabel(rotulo_x or coluna)
    ax.set_ylabel(rotulo_y or ("% do grupo" if (percentagem and cor_por) else
                               "% dos valores" if percentagem else "Contagem"))
    moldura(fig, ax, titulo, subtitulo, fonte, legenda)
    return fig, ax


def dispersao(df: pd.DataFrame, x: str, y: str, cor: str | None = None, titulo: str = "",
              subtitulo: str | None = None, rotulo_x: str | None = None, rotulo_y: str | None = None,
              tendencia: bool = False, rotular_grupos: bool = True, fonte: str | None = None,
              largura: float = 8.5, altura: float = 5.6):
    """Gráfico de dispersão: a relação entre duas colunas numéricas (um ponto por linha).

    Args:
        df: o DataFrame.
        x, y: os nomes das colunas para cada eixo.
        cor: nome de uma coluna de grupos (ex.: ``"especie"``). As cores
            estão validadas para até 3 grupos; os restantes juntam-se em "Outros".
        titulo, subtitulo: texto por cima do gráfico.
        rotulo_x, rotulo_y: nomes dos eixos (por omissão, os nomes das colunas).
        tendencia: desenha uma reta de tendência (uma por grupo, se houver grupos).
        rotular_grupos: escreve o nome de cada grupo no meio dos seus pontos.
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.

    Exemplo::

        fig, ax = dispersao(pinguins, "barbatana_mm", "massa_g", cor="especie",
                            titulo="Barbatanas maiores, pinguins mais pesados")
    """
    t = _garantir_tema()
    colunas = [x, y] + ([cor] if cor else [])
    d = df[colunas].dropna().copy()
    fig, ax = _nova_figura(largura, altura)
    ax.grid(True, axis="both")
    ax.spines["bottom"].set_visible(False)
    legenda = None

    def _reta(xs, ys, c):
        if len(xs) > 2:
            a, b = np.polyfit(xs, ys, 1)
            xx = np.array([xs.min(), xs.max()])
            ax.plot(xx, a * xx + b, color=c, lw=2.2, zorder=4, path_effects=[
                patheffects.withStroke(linewidth=4.5, foreground=t["fundo"])])

    if cor is None:
        ax.scatter(d[x], d[y], s=42, color=t["paleta"][0], alpha=0.85, edgecolor=t["fundo"], linewidth=0.9, zorder=3)
        if tendencia:
            _reta(d[x].to_numpy(float), d[y].to_numpy(float), t["tinta2"])
    else:
        grupos = d[cor].astype(str)
        mais_frequentes = grupos.value_counts().index[:3]
        grupos = grupos.where(grupos.isin(mais_frequentes), "Outros")
        d["_grupo"] = grupos
        cores = _cores_por_grupo([g for g in grupos.unique() if g != "Outros"])
        if "Outros" in set(grupos):
            cores["Outros"] = t["neutro"]
        legenda = []
        for g, c in cores.items():
            parte = d[d["_grupo"] == g]
            ax.scatter(parte[x], parte[y], s=42, color=c, alpha=0.85, edgecolor=t["fundo"],
                       linewidth=0.9, zorder=3 if g != "Outros" else 2)
            if tendencia:
                _reta(parte[x].to_numpy(float), parte[y].to_numpy(float), c)
            legenda.append((g, c, "ponto"))
        if rotular_grupos:
            nomes = []
            for g in cores:
                if g == "Outros":
                    continue
                parte = d[d["_grupo"] == g]
                nomes.append(ax.annotate(g, xy=(parte[x].median(), parte[y].quantile(0.93)), xytext=(0, 10),
                                         textcoords="offset points", ha="center", va="bottom",
                                         fontsize=11, color=t["tinta"], zorder=6, path_effects=[
                                             patheffects.withStroke(linewidth=4, foreground=t["fundo"])],
                                         **_fonte("titulo")))
            # se dois nomes se sobrepõem (grupos misturados), tiramo-los: a legenda chega
            fig.canvas.draw()
            caixas = [n.get_window_extent() for n in nomes]
            if any(a.overlaps(b) for i, a in enumerate(caixas) for b in caixas[i + 1:]):
                for n in nomes:
                    n.remove()
    ax.set_xlabel(rotulo_x or x)
    ax.set_ylabel(rotulo_y or y)
    ax.margins(0.05)
    _formatar_eixo(ax, "both")
    moldura(fig, ax, titulo, subtitulo, fonte, legenda)
    return fig, ax


def caixa(df: pd.DataFrame, coluna: str, por: str, titulo: str = "", subtitulo: str | None = None,
          tipo: str = "violino", rotulo: str | None = None, formato: str | None = None,
          pontos: bool = True, fonte: str | None = None, largura: float = 9):
    """Compara a distribuição de uma coluna numérica entre grupos (violino ou caixa de bigodes).

    Os grupos ficam ordenados pela mediana (o maior em cima) e a mediana de
    cada um fica escrita no gráfico.

    Args:
        df: o DataFrame.
        coluna: a coluna numérica (ex.: ``"massa_g"``).
        por: a coluna dos grupos (ex.: ``"especie"``).
        titulo, subtitulo: texto por cima do gráfico.
        tipo: ``"violino"`` (mostra a forma da distribuição) ou ``"caixa"``
            (a clássica caixa de bigodes, com quartis).
        rotulo: o nome do eixo dos valores.
        formato: como escrever as medianas (ex.: ``"{:.0f}"``).
        pontos: desenha também cada observação como um pontinho.
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.

    Exemplo::

        fig, ax = caixa(pinguins, "massa_g", por="especie", titulo="Os Gentoo são os mais pesados")
    """
    t = _garantir_tema()
    d = df[[coluna, por]].dropna()
    cores = _cores_por_grupo(d[por])
    medianas = d.groupby(por, observed=True)[coluna].median().sort_values()
    ordem = list(medianas.index)  # do menor (em baixo) para o maior (em cima)
    n = len(ordem)
    conjuntos = [d.loc[d[por] == g, coluna].to_numpy(float) for g in ordem]
    posicoes = np.arange(n)

    fig, ax = _nova_figura(largura, 1.15 * n + 1.3)
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.spines["bottom"].set_visible(False)
    rng = np.random.default_rng(42)

    if pontos:
        for pos, valores, g in zip(posicoes, conjuntos, ordem):
            ax.scatter(valores, pos + rng.uniform(-0.17, 0.17, len(valores)), s=8, color=cores[g],
                       alpha=0.45, lw=0, zorder=2)

    if tipo == "violino":
        partes = ax.violinplot(conjuntos, positions=posicoes, orientation="horizontal", widths=0.8,
                               showextrema=False)
        for corpo, g in zip(partes["bodies"], ordem):
            corpo.set_facecolor(to_rgba(cores[g], 0.20))
            corpo.set_edgecolor(cores[g])
            corpo.set_linewidth(1.5)
            corpo.set_zorder(1)
        for pos, valores, g in zip(posicoes, conjuntos, ordem):
            q1, q3 = np.percentile(valores, [25, 75])
            ax.hlines(pos, q1, q3, color=t["tinta"], lw=3.2, zorder=4, capstyle="round")
            ax.scatter([np.median(valores)], [pos], s=46, color=t["fundo"], edgecolor=t["tinta"],
                       linewidth=1.6, zorder=5)
    else:
        caixas = ax.boxplot(conjuntos, positions=posicoes, orientation="horizontal", widths=0.5,
                            patch_artist=True, showfliers=not pontos, showcaps=False,
                            medianprops={"color": t["tinta"], "lw": 2.2},
                            flierprops={"marker": "o", "markersize": 3.5, "markeredgewidth": 0})
        for i, g in enumerate(ordem):
            caixas["boxes"][i].set(facecolor=to_rgba(cores[g], 0.22), edgecolor=cores[g], linewidth=1.5, zorder=3)
            for bigode in caixas["whiskers"][2 * i: 2 * i + 2]:
                bigode.set(color=cores[g], linewidth=1.5)
            if not pontos:
                caixas["fliers"][i].set(markerfacecolor=cores[g])

    for pos, valores in zip(posicoes, conjuntos):
        ax.annotate(f"mediana {_numero(float(np.median(valores)), formato)}", xy=(np.median(valores), pos),
                    xytext=(0, 13), textcoords="offset points", ha="center", va="bottom",
                    fontsize=9, color=t["tinta"], zorder=6, path_effects=_halo(), **_fonte("media"))
    ax.set_yticks(posicoes, [str(g) for g in ordem])
    ax.tick_params(axis="y", labelsize=10.5, labelcolor=t["tinta"])
    ax.set_ylim(-0.6, n - 0.35)
    ax.set_xlabel(rotulo or coluna)
    _formatar_eixo(ax, "x")
    moldura(fig, ax, titulo, subtitulo, fonte)
    return fig, ax


def donut(dados: Any, titulo: str, subtitulo: str | None = None, destaque: str | None = None,
          centro: str | None = None, legenda_centro: str = "total", formato: str = "{:.0%}",
          fonte: str | None = None, tamanho: float = 6.2):
    """Gráfico circular com buraco ("donut"): as partes de um todo.

    Use-o só com poucas partes (até 6 — as restantes juntam-se em "Outros")
    e quando as diferenças forem claras; para comparar valores parecidos,
    as barras são melhores.

    Args:
        dados: ``dict``, ``Counter``, ``Series`` ou lista de pares (nome, valor).
        titulo, subtitulo: texto por cima do gráfico.
        destaque: o nome da fatia a destacar (as outras ficam cinzentas).
        centro: o texto grande no meio (por omissão, o total).
        legenda_centro: o texto pequeno por baixo do número central.
        formato: como escrever as percentagens.
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.
    """
    t = _garantir_tema()
    serie = _para_serie(dados).astype(float).sort_values(ascending=False, kind="stable")
    if len(serie) > 6:
        serie = pd.concat([serie.iloc[:5], pd.Series({"Outros": serie.iloc[5:].sum()})])
    total = serie.sum()
    if destaque is None:
        cores = [t["paleta"][i] if nome != "Outros" else t["neutro"] for i, nome in enumerate(serie.index)]
    else:
        cores = [t["paleta"][0] if str(nome) == str(destaque) else t["neutro"] for nome in serie.index]

    fig, ax = _nova_figura(tamanho, tamanho * 0.86)
    ax.grid(False)
    fatias, _ = ax.pie(serie.to_numpy(), colors=cores, startangle=90, counterclock=False,
                       wedgeprops={"width": 0.34, "edgecolor": t["fundo"], "linewidth": 2.5})
    for fatia, nome, valor in zip(fatias, serie.index, serie.to_numpy()):
        angulo = np.deg2rad((fatia.theta1 + fatia.theta2) / 2)
        cx, cy = np.cos(angulo), np.sin(angulo)
        lado = "left" if cx >= 0 else "right"
        destacada = destaque is not None and str(nome) == str(destaque)
        ax.annotate(f"{nome}", xy=(1.13 * cx, 1.13 * cy), ha=lado, va="bottom", fontsize=10.5,
                    color=t["tinta"], **_fonte("titulo" if destacada else "media"))
        ax.annotate(_numero(valor / total, formato), xy=(1.13 * cx, 1.13 * cy), ha=lado, va="top",
                    fontsize=10, color=t["tinta2"], **_fonte("texto"))
    ax.text(0, 0.06, centro if centro is not None else _numero(total), ha="center", va="center",
            fontsize=26, color=t["tinta"], **_fonte("titulo"))
    ax.text(0, -0.17, legenda_centro, ha="center", va="center", fontsize=10, color=t["tinta2"])
    ax.set(aspect="equal")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.3, 1.3)
    ax.axis("off")
    moldura(fig, ax, titulo, subtitulo, fonte)
    return fig, ax


def mapa_calor(df: pd.DataFrame, titulo: str, subtitulo: str | None = None, metade: bool = True,
               formato: str = "{:.2f}", nomes: Mapping[str, str] | None = None,
               fonte: str | None = None, tamanho: float = 6.8):
    """Mapa de calor das correlações entre as colunas numéricas de um DataFrame.

    Azul = correlação negativa, vermelho = positiva, cinzento = nenhuma.

    Args:
        df: um DataFrame com dados (as correlações são calculadas com
            ``df.corr()``) ou uma tabela de correlações já pronta.
        titulo, subtitulo: texto por cima do gráfico.
        metade: mostra só metade da tabela (a outra metade é igual, em espelho).
        formato: como escrever cada correlação.
        nomes: nomes mais bonitos para as colunas, ex.: ``{"massa_g": "Massa"}``.
        fonte: de onde vêm os dados.

    Returns:
        ``(fig, ax)``.
    """
    t = _garantir_tema()
    numerico = df.select_dtypes("number")
    pronta = numerico.shape[0] == numerico.shape[1] and list(numerico.index) == list(numerico.columns)
    corr = numerico if pronta else numerico.corr()
    if nomes:
        corr = corr.rename(index=nomes, columns=nomes)
    n = len(corr)
    matriz = corr.to_numpy(dtype=float)
    mascara = np.triu(np.ones_like(matriz, dtype=bool)) if metade else np.zeros_like(matriz, dtype=bool)
    if metade:  # sem a diagonal (é sempre 1) — tiramos a 1.ª linha e a última coluna, que ficam vazias
        matriz, mascara = matriz[1:, :-1], mascara[1:, :-1]
        linhas, colunas = list(corr.index[1:]), list(corr.columns[:-1])
    else:
        linhas, colunas = list(corr.index), list(corr.columns)

    fig, ax = _nova_figura(tamanho, tamanho * 0.82)
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    cmap = _cmap_divergente()
    dados = np.ma.masked_array(matriz, mascara)
    imagem = ax.imshow(dados, cmap=cmap, vmin=-1, vmax=1)
    # separadores: grelha da cor do fundo entre as células
    ax.set_xticks(np.arange(len(colunas) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(linhas) + 1) - 0.5, minor=True)
    ax.grid(which="minor", color=t["fundo"], linewidth=3)
    ax.tick_params(which="minor", length=0)
    for i in range(len(linhas)):
        for j in range(len(colunas)):
            if mascara[i, j]:
                continue
            v = matriz[i, j]
            r, g, b, _ = cmap((v + 1) / 2)
            claro = 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45
            ax.text(j, i, _numero(v, formato), ha="center", va="center", fontsize=10.5,
                    color="#0b0b0b" if claro else "#ffffff", **_fonte("media"))
    ax.set_xticks(range(len(colunas)), colunas, rotation=30, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(len(linhas)), linhas)
    ax.tick_params(axis="both", labelsize=10, labelcolor=t["tinta2"])
    barra = fig.colorbar(imagem, ax=ax, shrink=0.72, aspect=26, pad=0.03, ticks=[-1, -0.5, 0, 0.5, 1])
    barra.outline.set_visible(False)
    barra.ax.tick_params(labelsize=9, labelcolor=t["tinta2"], length=0)
    barra.ax.set_yticklabels(["−1", "−0,5", "0", "0,5", "1"])
    moldura(fig, ax, titulo, subtitulo, fonte)
    return fig, ax


def nuvem_palavras(dados: Any, titulo: str, subtitulo: str | None = None,
                   destaque: str | Sequence[str] | None = None, maximo: int = 80,
                   ignorar: Iterable[str] = (), fonte: str | None = None, largura: float = 10):
    """Nuvem de palavras: o tamanho de cada palavra mostra quantas vezes aparece.

    As palavras mais frequentes ficam maiores e num azul mais escuro; as
    palavras em ``destaque`` ficam a laranja.

    Args:
        dados: um texto (``str``) ou as contagens já feitas (``dict``,
            ``Counter`` ou ``Series``).
        titulo, subtitulo: texto por cima da nuvem.
        destaque: palavra (ou lista de palavras) a pintar de laranja.
        maximo: número máximo de palavras na nuvem.
        ignorar: palavras a deixar de fora (ex.: as tuas stop words).
        fonte: de onde vem o texto.

    Returns:
        ``(fig, ax)``.
    """
    from wordcloud import WordCloud  # só é preciso aqui

    t = _garantir_tema()
    ignorar = {p.lower() for p in ignorar}
    if isinstance(dados, str):
        contagem = Counter(p for p in dados.lower().split() if p not in ignorar)
    else:
        contagem = Counter({str(k): float(v) for k, v in _para_serie(dados).items() if str(k).lower() not in ignorar})
    contagem = dict(Counter(contagem).most_common(maximo))
    destacadas = {destaque} if isinstance(destaque, str) else set(destaque or [])
    maior = max(contagem.values())
    rampa = _TEMA["sequencial"][2:]  # do tom mais discreto ao mais forte (claro: azul → azul-escuro)

    def colorir(palavra, **_):
        if palavra in destacadas:
            return _TEMA["paleta"][1]
        peso = (contagem.get(palavra, 0) / maior) ** 0.5  # 0 (rara) → 1 (frequente)
        return rampa[min(len(rampa) - 1, int(peso * len(rampa)))]

    letra = _PASTA_FONTES / "Inter-SemiBold.ttf"
    nuvem = WordCloud(width=int(largura * 160), height=int(largura * 80), background_color=t["fundo"],
                      font_path=str(letra) if letra.exists() else None, prefer_horizontal=1.0,
                      relative_scaling=0.4, margin=12, random_state=7, color_func=colorir,
                      max_words=maximo).generate_from_frequencies(contagem)
    fig, ax = _nova_figura(largura, largura / 2)
    ax.imshow(nuvem, interpolation="bilinear")
    ax.axis("off")
    moldura(fig, ax, titulo, subtitulo, fonte)
    return fig, ax


def guardar(fig, nome: str, pasta: str | Path = "output", dpi: int = 200) -> None:
    """Guarda a figura como imagem PNG de alta resolução.

    Args:
        fig: a figura (o 1.º valor devolvido pelas funções de gráficos).
        nome: o nome do ficheiro, com ou sem ``.png``.
        pasta: a pasta onde guardar (é criada se não existir).
        dpi: pontos por polegada — 200 dá uma imagem nítida para slides e relatórios.

    Exemplo::

        fig, ax = barras(...)
        guardar(fig, "top_palavras")   # → output/top_palavras.png
    """
    caminho = Path(pasta) / nome
    if caminho.suffix.lower() != ".png":
        caminho = caminho.with_suffix(".png")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=dpi, bbox_inches="tight", pad_inches=0.35, facecolor=fig.get_facecolor())
    print(f"Gráfico guardado em {caminho.as_posix()}")
