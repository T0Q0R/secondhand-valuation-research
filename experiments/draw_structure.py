"""Portable vector previews matching the editable TikZ diagram sources.

No empirical effect is depicted. Native vector text/boxes avoid dependence on
first-run TeX bundle downloads; the method source remains editable separately.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "paper/figures"
plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9,
                     "pdf.fonttype": 42, "svg.fonttype": "none"})
BLUE, ORANGE, GRAY = "#0072B2", "#B46B00", "#666666"


def canvas(height, xlim, ylim):
    fig, ax = plt.subplots(figsize=(7.1, height))
    fig.subplots_adjust(left=.015, right=.985, top=.985, bottom=.015)
    ax.set(xlim=xlim, ylim=ylim); ax.axis("off")
    return fig, ax


def box(ax, center, width, height, title, body, color=GRAY, fill="#F6F6F6"):
    x, y = center
    font = 8.5 if ax.figure.get_figheight() > 3 else 9
    usable = width / (ax.get_xlim()[1] - ax.get_xlim()[0]) * ax.figure.get_figwidth() * .97 * 72 - 12
    def wrap(text, bold=False):
        prop = FontProperties(family="DejaVu Serif", size=font, weight="bold" if bold else "normal")
        lines = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split():
                candidate = (line + " " + word).strip()
                if line and TextPath((0,0), candidate, prop=prop).get_extents().width > usable:
                    lines.append(line); line = word
                else:
                    line = candidate
            lines.append(line)
        return "\n".join(lines)
    title, body = wrap(title, True), wrap(body)
    world_per_point = (ax.get_ylim()[1] - ax.get_ylim()[0]) / (ax.figure.get_figheight() * .97 * 72)
    body_height = len(body.split("\n")) * font * 1.25
    title_height = len(title.split("\n")) * font * 1.2
    height = max(height, (body_height + title_height + 16) * world_per_point)
    ax.add_patch(FancyBboxPatch((x - width/2, y - height/2), width, height,
        boxstyle="round,pad=0.03,rounding_size=0.06", linewidth=.9, edgecolor=color, facecolor=fill))
    ax.text(x, y + (body_height + 4)/2 * world_per_point, title, ha="center", va="center",
            fontsize=font, fontweight="bold", linespacing=1.2)
    ax.text(x, y - (title_height + 4)/2 * world_per_point, body, ha="center", va="center", fontsize=font, linespacing=1.25)


def arrow(ax, start, end):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                               linewidth=.8, color="#333333"))


def save(fig, name):
    for ext in ["pdf", "svg", "png"]:
        fig.savefig(DEST / f"{name}.{ext}", dpi=180)
    plt.close(fig)


def main():
    DEST.mkdir(exist_ok=True)
    fig, ax = canvas(2.9, (-2.1, 15.6), (-3.3, 3.4))
    box(ax, (0, 1.45), 3.6, 1.65, "A: withheld", "140,000 km\nrecorded and hidden", ORANGE, "#FFF7E8")
    box(ax, (0, -1.45), 3.6, 1.65, "B: unavailable", "No mileage\nvalue recorded")
    box(ax, (4.6, 0), 3.3, 2.0, "Same public report", "Mileage: missing\nSame other\nvisible fields", BLUE, "#F1F7FC")
    box(ax, (8.8, 0), 3.3, 2.0, "Same query decision", "Public inputs only\nOne capacity slot\nper attempt")
    box(ax, (13.4, 1.45), 3.7, 1.65, "A: replay succeeds", "140,000 km\nrecovered", BLUE, "#F1F7FC")
    box(ax, (13.4, -1.45), 3.7, 1.65, "B: replay fails", "Still missing\nSlot still spent")
    for start, end in [((1.83,1.45),(2.92,.7)), ((1.83,-1.45),(2.92,-.7)),
                       ((6.28,0),(7.1,0)), ((10.48,.7),(11.5,1.45)), ((10.48,-.7),(11.5,-1.45))]:
        arrow(ax, start, end)
    for x, title in [(0,"Private source state"),(6.7,"Pre-query platform information"),(13.4,"Environment response")]:
        ax.text(x, 2.78, title, ha="center", va="center", fontsize=9, fontweight="bold")
    ax.plot([2.35,2.35],[-2.4,3.1],"--",color="#777777",lw=.7)
    ax.text(6.7,-2.65,"Conceptual example; illustrative mileage.\nReplay does not simulate physical inspection.",ha="center",va="center",fontsize=9)
    save(fig,"missingness_example")

    fig, ax = canvas(4.8,(-2.75,13.95),(-3.6,7.7))
    style = dict(color=BLUE,fill="#F1F7FC")
    box(ax,(0,6),4.8,2.75,"Nested target generation","Three outer folds\nInner estimator / guidance\nsplit within outer training",**style)
    box(ax,(5.6,6),4.8,2.75,"Policy-aware feedback","Mask-aware backbone + residual\nGuidance action head\nSeller-response replay",**style)
    box(ax,(11.2,6),4.8,2.75,"Suppression targets","Quotes on outer-held-out rows\nOutcomes used only after\nthe corresponding fitted loop",**style)
    box(ax,(0,2.6),4.8,2.75,"Mask-aware valuation","Fit deployment estimator\nInner estimator / guidance split\nHonest-price anchor and gap loss",**style)
    box(ax,(5.6,2.6),4.8,2.75,"Deployment action head","Learn collected outer targets\nInputs: report, current quote,\ncandidate field",**style)
    ax.text(11.2,2.6,"Offline construction\nSource values form targets.\nTeacher and deployment fitting\nsample sizes differ.",ha="center",va="center",fontsize=9,linespacing=1.35)
    for start,end in [((2.45,6),(3.13,6)),((8.05,6),(8.73,6)),
                      ((2.45,2.6),(3.13,2.6)),((0,1.20),(0,.205)),((5.6,1.20),(5.6,.205))]:
        arrow(ax,start,end)
    ax.plot([11.2,11.2,5.6],[4.60,4.15,4.15],color="#333333",lw=.8)
    arrow(ax,(5.6,4.15),(5.6,4.005))
    ax.plot([-2.6,13.8],[.75,.75],"--",color="#777777",lw=.7)
    box(ax,(0,-1.2),4.8,2.75,"Reported listing","Visible fields and missingness\nBefore-query price estimate")
    box(ax,(5.6,-1.2),4.8,2.75,"Budget allocation","Best positive field per listing\nHighest scores in the batch\nAt most one query per listing")
    box(ax,(11.2,-1.2),4.8,2.75,"Query and final quote","Replay a value if recorded\nFailed attempt spends a slot\nRe-estimate the reported listing")
    arrow(ax,(2.45,-1.2),(3.13,-1.2));arrow(ax,(8.05,-1.2),(8.73,-1.2))
    ax.text(5.6,-3.1,"Deployment excludes hidden values, simulator masks,\noutcomes, and honest-reference quotes.",ha="center",va="center",fontsize=9)
    save(fig,"sav_val_overview")
    print(f"Exported two native vector PDF/SVG diagrams and PNG previews under {DEST}")


if __name__ == "__main__":
    main()
