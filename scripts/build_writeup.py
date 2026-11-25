"""Build the Word write-up of the agricultural results, to send to Alper when ready:
outputs/writeup/agriculture_results.docx.

A living document: the text is written here, every number and figure is read from the
results tables in outputs/, so re-running this script after an update refreshes it.
Sections are marked draft / awaiting Alper / to come. The methodology change log
(docs/methodology_change_log.md, local) is the detailed working list behind section 2.6.

Run:  python scripts/build_writeup.py
"""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TAB, FIG = ROOT / "outputs/tables", ROOT / "outputs/figures"
PROC = ROOT / "data/processed"
OUT = ROOT / "outputs/writeup/agriculture_results.docx"
INK, MUTED, ACCENT = RGBColor(0x0B, 0x0B, 0x0B), RGBColor(0x52, 0x51, 0x4E), RGBColor(0x18, 0x4F, 0x95)
FONT = "Calibri"


# ---------------------------------------------------------------- formatting helpers
def setup(doc):
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)  # A4
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.3))
    st = doc.styles
    st["Normal"].font.name, st["Normal"].font.size = FONT, Pt(10.5)
    st["Normal"].paragraph_format.space_after = Pt(6)
    st["Normal"].paragraph_format.line_spacing = 1.1
    for name, size, before in (("Title", 20, 0), ("Heading 1", 15, 16), ("Heading 2", 12, 12)):
        s = st[name]
        s.font.name, s.font.size, s.font.bold, s.font.color.rgb = FONT, Pt(size), True, INK
        rpr = s.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(a), FONT)
        s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(before), Pt(6)
        s.paragraph_format.keep_with_next = True
    footer = sec.footer.paragraphs[0]
    footer.text = "Working draft. Results are provisional; the recommended specification differs from methodology v5."
    footer.runs[0].font.size, footer.runs[0].font.color.rgb = Pt(8), MUTED


def para(doc, text, italic=False, size=None, color=None, bold_prefix=None):
    p = doc.add_paragraph()
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
    r = p.add_run(text)
    r.italic = italic
    if size:
        r.font.size = Pt(size)
    if color is not None:
        r.font.color.rgb = color
    return p


def bullets(doc, items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        if isinstance(it, tuple):
            p.add_run(it[0]).bold = True
            p.add_run(it[1])
        else:
            p.add_run(it)


def status(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(f"Status: {text}")
    r.italic, r.font.size, r.font.color.rgb = True, Pt(9), ACCENT


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def keep_with_next(paragraph):
    paragraph.paragraph_format.keep_with_next = True


def table(doc, df, widths_cm, note=None, fmt=None):
    """Caption (note) above the table, kept with it; rows kept on one page where they fit;
    header row repeated if the table breaks."""
    fmt = fmt or {}
    if note:
        p = doc.add_paragraph()
        r = p.add_run(note)
        r.italic, r.font.size, r.font.color.rgb = True, Pt(8.5), MUTED
        p.paragraph_format.space_after = Pt(3)
        keep_with_next(p)
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    tblPr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    for i, c in enumerate(df.columns):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(str(c))
        r.bold, r.font.size = True, Pt(9)
        shade(cell, "E6EEF8")
    for row in df.itertuples(index=False):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            col = df.columns[i]
            if isinstance(v, float):
                s_ = "" if pd.isna(v) else fmt.get(col, "{:.1f}").format(v)
            else:
                s_ = str(v)
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(s_)
            r.font.size = Pt(9)
            if i > 0 and isinstance(v, float):
                cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for i, w in enumerate(widths_cm):
        t.columns[i].width = Cm(w)
    for k, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        trPr.append(cant)
        if k == 0:
            hdr = OxmlElement("w:tblHeader")
            trPr.append(hdr)
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)
            if k < len(t.rows) - 1:
                for p in row.cells[i].paragraphs:
                    keep_with_next(p)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figure(doc, path, width_cm, caption):
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    r = p.add_run(caption)
    r.italic, r.font.size, r.font.color.rgb = True, Pt(8.5), MUTED


# ---------------------------------------------------------------- numbers from outputs
def spec_tests():
    s = pd.read_csv(TAB / "direct_v5_rice_spec_comparison_no_dmi.csv")
    s = s[s.model == "ppml"].copy()
    s["effect"] = s.get("B_RP").fillna(s.get("B_R"))
    s["t_eff"] = s.get("t_RP").fillna(s.get("t_R"))
    labels = {"base": "v5 Eq. 4 (RONI only)", "split": "El Niño and La Niña separate",
              "season": "effect differs by harvest season", "trend_rq": "trends by region and quarter",
              "trend_spline": "smooth regional trends (spline)", "lags_0_4": "lags 0–4 (current quarter)",
              "lags_1_6": "lags 1–6", "pool_island": "effects pooled by island group",
              "pool_national": "one national effect"}
    w = s.pivot_table(index="spec", columns="ecosystem", values=["ic_minus_base", "effect", "t_eff"])
    out = pd.DataFrame({"Change to the v5 specification": [labels[k] for k in labels],
                        "Fit gain, irrigated": [-w.loc[k, ("ic_minus_base", "irrigated")] for k in labels],
                        "El Niño effect, irrigated": [w.loc[k, ("effect", "irrigated")] for k in labels],
                        "Fit gain, rainfed": [-w.loc[k, ("ic_minus_base", "rainfed")] for k in labels],
                        "El Niño effect, rainfed": [w.loc[k, ("effect", "rainfed")] for k in labels]})
    for c in ("Fit gain, irrigated", "Fit gain, rainfed"):
        out[c] = out[c].map(lambda v: f"{v:,.0f}").astype(object)
        out.loc[0, c] = "reference"
    return out


def validation():
    a = pd.read_csv(TAB / "direct_v5_rice_validation_no_dmi.csv")
    b = pd.read_csv(TAB / "direct_v5_rice_validation_candidate_no_dmi.csv")
    v = pd.concat([a[a.spec == "base"], b[b.spec.isin(["candidate", "candidate_break2000"])]])
    names = {"base": "v5 (RONI only)", "candidate": "split + spline + season",
             "candidate_break2000": "recommended (+ change from 2000)"}
    rows = []
    for eco in ("irrigated", "rainfed"):
        for sp in names:
            x = v[(v.ecosystem == eco) & (v.spec == sp)].set_index("episode")
            r = {"Palay": eco, "Specification": names[sp]}
            for ep in ("1997-98", "2015-16", "2023-24"):
                r[f"{ep} obs / pred"] = f"{x.loc[ep, 'observed_loss_pct']:.0f} / {x.loc[ep, 'predicted_loss_pct']:.0f}"
            r["Mean abs. error (pts)"] = (x.predicted_loss_pct - x.observed_loss_pct).abs().mean()
            rows.append(r)
    return pd.DataFrame(rows)


def effects():
    n = pd.read_csv(TAB / "direct_rice_national_effects.csv")
    n = n[(n.model == "ppml") & n["index"].str.startswith("El")]
    rows = []
    for eco in ("irrigated", "rainfed"):
        for season in ("dry (Q1-Q2)", "wet (Q3-Q4)"):
            x = n[(n.ecosystem == eco) & (n.harvest_season == season)].set_index("period")
            rows.append({"Palay": eco, "Harvest season": season.replace("-", "–"),
                         "Before 2000": x.loc["before 2000", "pct_effect_of_+1"],
                         "t (before)": x.loc["before 2000", "t"],
                         "From 2000": x.loc["from 2000", "pct_effect_of_+1"],
                         "t (from 2000)": x.loc["from 2000", "t"]})
    return pd.DataFrame(rows)


def episode_totals(crop="rice", main="palay", parts=("irrigated", "rainfed")):
    t = pd.read_csv(TAB / f"shocks_{crop}_episode_totals.csv")
    t["path"] = t.path.str.replace("unit RONI +1 (4 quarters from Q3)", "unit path: RONI +1 for 4 quarters", regex=False)
    w = t.pivot_table(index="path", columns="crop", values="total_loss_pct_of_annual")
    r = t[t.crop == main].set_index("path")
    name = {"palay": "Palay", "corn": "Corn"}[main]
    out = pd.DataFrame({"Path (replayed under today's conditions)": w.index,
                        name: w[main].values,
                        "90% range": [f"{r.loc[k, 'p05']:.1f} to {r.loc[k, 'p95']:.1f}" for k in w.index]})
    for c in parts:
        out[c.replace("corn_", "").capitalize()] = w[c].values
    out[f"Draws with a loss ({main}, %)"] = [r.loc[k, "share_of_draws_with_loss_pct"] for k in w.index]
    return out


def corn_specs():
    s = pd.read_csv(TAB / "direct_v5_corn_spec_comparison_summary_no_dmi.csv")
    s = s[s.model == "ppml"].set_index("spec")
    v = pd.read_csv(TAB / "direct_v5_corn_validation_summary_no_dmi.csv")
    mae = v.groupby("spec").error_pts.apply(lambda x: x.abs().mean())
    names = {"base": "v5 (RONI only)", "candidate": "split + spline + season (recommended)",
             "step_2000": "+ step in 2000", "gradual_linear": "+ gradual change"}
    rows = []
    for k, lab in names.items():
        eff = s.loc[k, "B_RP"] if "B_RP" in s and pd.notna(s.loc[k].get("B_RP")) else s.loc[k, "B_R"]
        rows.append({"Specification": lab,
                     "Fit gain vs v5": "reference" if k == "base" else f"{-s.loc[k, 'ic_minus_base']:,.0f}",
                     "El Niño effect (log points)": eff,
                     "Validation error (pts)": mae[k]})
    return pd.DataFrame(rows)


def corn_effects():
    n = pd.read_csv(TAB / "direct_corn_national_effects.csv")
    n = n[(n.model == "ppml") & n["index"].str.startswith("El")]
    rows = []
    for e, lab in (("corn", "total"), ("corn_white", "white"), ("corn_yellow", "yellow")):
        x = n[n.ecosystem == e].set_index("harvest_season")
        rows.append({"Corn": lab, "Dry-season harvest (Q1–Q2), %": x.loc["dry (Q1-Q2)", "pct_effect_of_+1"],
                     "t (dry)": x.loc["dry (Q1-Q2)", "t"],
                     "Wet-season harvest (Q3–Q4), %": x.loc["wet (Q3-Q4)", "pct_effect_of_+1"],
                     "t (wet)": x.loc["wet (Q3-Q4)", "t"]})
    return pd.DataFrame(rows)


def corn_checks():
    out = {}
    for sfx, lab in (("", "main"), ("_check_kanlaon", "kanlaon"), ("_check_no_vi_corn_2023q3", "no_vi")):
        n = pd.read_csv(TAB / f"direct_corn_national_effects{sfx}.csv")
        out[lab] = n[(n.model == "ppml") & n["index"].str.startswith("El")].set_index(["ecosystem", "harvest_season"]).est
    return max((out["kanlaon"] - out["main"]).abs().max(), (out["no_vi"] - out["main"]).abs().max())


def quarterly_palay():
    s = pd.read_csv(TAB / "shocks_rice.csv")
    s = s[(s.crop == "palay") & ~s.path.str.startswith("unit")]
    s = s.assign(S=s.S * 100, lo=s.S_p05 * 100, hi=s.S_p95 * 100, SD=s.S_D * 100)
    return pd.DataFrame({"Path": s.path, "Quarter": s.scenario_q,
                         "Shock (% of quarter)": s.S, "90% range": [f"{a:.1f} to {b:.1f}" for a, b in zip(s.lo, s.hi)],
                         "Scaled for DEFINE-PH (%)": s.SD})


EPS = ("1997-98", "2015-16", "2023-24")
VARIANT_LABEL = {"recommended (nested break)": "recommended",
                 "recommended, no DMI (nested break)": "recommended, no DMI",
                 "v5 as written": "v5 as written", "v5 as written, no DMI": "v5 as written, no DMI"}


def strict(crop):
    """Stricter validation: errors by episode, mean, mean leaving one episode out, breaks."""
    t = pd.read_csv(TAB / f"validation_strict_{crop}.csv")
    rows = []
    for (series, variant), g in t.groupby(["series", "variant"], sort=False):
        g = g.set_index("episode")
        err = g.error_pts.reindex(EPS)
        loo = [err.drop(ep).abs().mean() for ep in EPS]
        r = {"Series": series.replace("corn", "total corn") if series == "corn" else series,
             "Variant": VARIANT_LABEL[variant]}
        for ep in EPS:
            r[f"{ep}"] = err[ep]
        r["Mean abs. error"] = err.abs().mean()
        r["Leaving one out"] = f"{min(loo):.1f}–{max(loo):.1f}"
        r["Break chosen"] = "/".join(g.chosen_break.reindex(EPS)) if variant.startswith("recommended") else "none"
        rows.append(r)
    return pd.DataFrame(rows)


def strict_mae(crop, series, variant):
    t = pd.read_csv(TAB / f"validation_strict_{crop}.csv")
    return t[(t.series == series) & (t.variant == variant)].error_pts.abs().mean()


def dmi_table():
    """El Nino effect and validation errors with and without the DMI."""
    rows = []
    names = {"corn": "total corn", "vr": "VR index", "pf": "PF index"}
    for crop, series_list in (("rice", ("irrigated", "rainfed")), ("corn", ("corn",)), ("vr", ("vr",)),
                              ("pf", ("pf",))):
        s = pd.read_csv(TAB / f"direct_v5_{crop}_spec_comparison_dmi.csv")
        v = pd.read_csv(TAB / f"direct_v5_{crop}_validation_dmi.csv")
        st = pd.read_csv(TAB / f"validation_strict_{crop}.csv")
        sfx = "" if crop in ("vr", "pf") else " (nested break)"
        eff = "B_R" if crop in ("vr", "pf") else "B_RP"  # VR / PF: one RONI effect
        for e in series_list:
            x = s[(s.ecosystem == e)].set_index(["model", "spec"])
            with_s, without_s = [k for k in x.loc["ppml"].index if not k.endswith("no_dmi")][0], \
                [k for k in x.loc["ppml"].index if k.endswith("no_dmi")][0]
            mae = v[v.ecosystem == e].groupby("spec").error_pts.apply(lambda z: z.abs().mean())
            smae = st[st.series == e].groupby("variant").error_pts.apply(lambda z: z.abs().mean())
            rows.append({"Series": names.get(e, f"{e} palay"),
                         "El Niño effect, with / without": f"{x.loc[('ppml', with_s), eff]:.2f} / {x.loc[('ppml', without_s), eff]:.2f}",
                         "Validation error, with / without": f"{mae[with_s]:.1f} / {mae[without_s]:.1f}",
                         "Stricter validation, with / without": f"{smae['recommended' + sfx]:.1f} / {smae['recommended, no DMI' + sfx]:.1f}",
                         "Fit gain without DMI, Poisson / log-LS": f"{-x.loc[('ppml', without_s), 'ic_minus_base']:,.0f} / {-x.loc[('ols', without_s), 'ic_minus_base']:,.0f}"})
    return pd.DataFrame(rows)


def decomposition():
    """Table 8a: total loss over each episode path, with and without the DMI part."""
    d = pd.read_csv(TAB / "shocks_decomposition.csv")
    names = {"palay": "palay", "corn": "corn", "vr": "VR index", "pf": "PF index"}
    d = d[d.crop.isin(names)]
    w = d.pivot_table(index=["crop", "path"], columns="part", values="total_loss_pct_of_annual")
    rows = []
    for c in names:
        for pth in ("1997-98", "2015-16", "2023-24"):
            x = w.loc[(c, pth)]
            rows.append({"Series": names[c], "Path": pth, "Shock (RONI and DMI)": x["RONI and DMI"],
                         "RONI part (DMI = 0)": x["RONI only (DMI = 0)"],
                         "DMI part (RONI = 0)": x["DMI only (RONI = 0)"]})
    return pd.DataFrame(rows)


def decomp(crop, path, part):
    d = pd.read_csv(TAB / "shocks_decomposition.csv")
    return d[(d.crop == crop) & (d.path == path) & (d.part == part)].total_loss_pct_of_annual.iloc[0]


def dmi_blocked():
    """Table 8b: blocked nested cross-validation with and without the DMI."""
    t = pd.read_csv(TAB / "dmi_blocked_cv_summary.csv")
    names = {"irrigated": "irrigated palay", "rainfed": "rainfed palay", "corn": "total corn",
             "vr": "VR index", "pf": "PF index"}
    return pd.DataFrame({"Series": t.series.map(names),
                         "Blocks": t.blocks,
                         "Error change with the DMI, %": t.mse_reduction_with_dmi_pct,
                         "90% range": [f"{a:.1f} to {b:.1f}" for a, b in zip(t.p05, t.p95)],
                         "Deviance change with the DMI, %": t.deviance_reduction_with_dmi_pct,
                         "Blocks better with the DMI": [f"{k} of {n}" for k, n in zip(t.blocks_better_with_dmi, t.blocks)]})


def dmi_controls(series, controls):
    t = pd.read_csv(TAB / "dmi_controls.csv")
    return t[(t.series == series) & (t.controls == controls)].dmi_effect.iloc[0]


def no_dmi_totals():
    """Table 8c: episode shocks of the recommended specifications with and without the DMI."""
    rows = []
    for crop, main, lab in (("rice", "palay", "palay"), ("corn", "corn", "corn"), ("vr", "vr", "VR index"),
                            ("pf", "pf", "PF index")):
        a = pd.read_csv(TAB / f"shocks_{crop}_episode_totals.csv").set_index(["path", "crop"])
        b = pd.read_csv(TAB / f"shocks_{crop}_episode_totals_with_dmi.csv").set_index(["path", "crop"])
        for pth in ("1997-98", "2015-16", "2023-24"):
            x, y = a.loc[(pth, main)], b.loc[(pth, main)]
            rows.append({"Series": lab, "Path": pth,
                         "RONI only (main)": f"{x.total_loss_pct_of_annual:.1f} ({x.p05:.1f} to {x.p95:.1f})",
                         "With the DMI (variant)": f"{y.total_loss_pct_of_annual:.1f} ({y.p05:.1f} to {y.p95:.1f})"})
    return pd.DataFrame(rows)


def roni_dmi_corr():
    from climate.indices import quarterly
    x = pd.DataFrame({"roni": quarterly("roni"), "dmi": quarterly("dmi")}).dropna()
    x = x[x.index.year.isin(range(1987, 2026))]
    q = x.groupby(x.index.quarter).apply(lambda g: g.roni.corr(g.dmi))
    return q[3], q[4]


def rice_checks():
    a = pd.read_csv(TAB / "direct_rice_national_effects.csv")
    b = pd.read_csv(TAB / "direct_rice_national_effects_check_kanlaon.csv")
    k = ["ecosystem", "model", "index", "harvest_season", "period"]
    m = a.merge(b, on=k, suffixes=("", "_k"))
    m = m[(m.model == "ppml") & m["index"].str.startswith("El")]
    kan = (m.est - m.est_k).abs().max()
    c = pd.read_csv(TAB / "rice_direct_control_compare.csv")
    c = c[(c.model == "ppml") & (c.term == "El Nino") & (c.season == "dry")]
    w = c.pivot_table(index="ecosystem", columns="controls", values="est")
    ctl = (w["category"] - w["none"]).abs().max()
    return kan, ctl


def quarterly_corn():
    s = pd.read_csv(TAB / "shocks_corn.csv")
    s = s[(s.crop == "corn") & ~s.path.str.startswith("unit")]
    s = s.assign(S=s.S * 100, lo=s.S_p05 * 100, hi=s.S_p95 * 100, SD=s.S_D * 100)
    return pd.DataFrame({"Path": s.path, "Quarter": s.scenario_q,
                         "Shock (% of quarter)": s.S, "90% range": [f"{a:.1f} to {b:.1f}" for a, b in zip(s.lo, s.hi)],
                         "Scaled for DEFINE-PH (%)": s.SD})


VRPF_SPECS = {"base": "v5 Eq. 4 (RONI only)", "spline_region": "smooth regional trends",
              "spline_national": "smooth trends + one national effect (recommended)",
              "spline_national_split": "  + El Niño and La Niña separate",
              "spline_national_season": "  + effect differs by harvest season",
              "spline_national_lags_1_6": "  + lags 1–6",
              "spline_island": "smooth trends + effects by island group"}
VRPF_INDEX = {"vr": "VR", "vr_noroot": "VR without root crops", "pf": "PF",
              "pf_nocavendish": "PF without Cavendish", "pf_nobanana": "PF without banana"}


def vrpf_specs():
    """Table 9: VR and PF specification tests (Poisson): fit gain against v5 as written,
    El Nino effect (%), leave-one-episode-out error."""
    out = pd.DataFrame({"Specification": list(VRPF_SPECS.values())})
    for crop in ("vr", "pf"):
        s = pd.read_csv(TAB / f"direct_v5_{crop}_spec_comparison_vrpf_national_no_dmi.csv")
        s = s[s.model == "ppml"].set_index("spec")
        v = pd.read_csv(TAB / f"direct_v5_{crop}_validation_vrpf_national_no_dmi.csv")
        mae = v.groupby("spec").error_pts.apply(lambda x: x.abs().mean())
        eff = s.B_RP.fillna(s.B_R) if "B_RP" in s else s.B_R
        lab = crop.upper()
        out[f"Fit gain, {lab}"] = ["reference" if k == "base" else f"{-s.loc[k, 'ic_minus_base']:,.0f}"
                                   for k in VRPF_SPECS]
        out[f"El Niño effect, {lab} (%)"] = [(np.exp(eff[k]) - 1) * 100 for k in VRPF_SPECS]
        out[f"Validation error, {lab}"] = [mae[k] for k in VRPF_SPECS]
    return out


def vrpf_effects():
    """Table 10: El Nino effect of the recommended VR / PF specification (RONI only), by index,
    with the El Nino and DMI effects of the variant with the DMI."""
    rows = []
    for crop, series in (("vr", ("vr", "vr_noroot")), ("pf", ("pf", "pf_nocavendish", "pf_nobanana"))):
        n = pd.read_csv(TAB / f"direct_{crop}_national_effects.csv")
        n = n[n.model == "ppml"].set_index(["ecosystem", "index"])
        v = pd.read_csv(TAB / f"direct_{crop}_national_effects_with_dmi.csv")
        v = v[v.model == "ppml"].set_index(["ecosystem", "index"])
        for e in series:
            rows.append({"Index": VRPF_INDEX[e],
                         "El Niño (RONI +1), %": n.loc[(e, "RONI"), "pct_effect_of_+1"],
                         "t (RONI)": n.loc[(e, "RONI"), "t"],
                         "With the DMI: El Niño, %": v.loc[(e, "RONI"), "pct_effect_of_+1"],
                         "DMI +1, %": v.loc[(e, "DMI"), "pct_effect_of_+1"],
                         "t (DMI)": v.loc[(e, "DMI"), "t"]})
    return pd.DataFrame(rows)


def vrpf_effect(crop, series, idx="RONI", col="pct_effect_of_+1"):
    n = pd.read_csv(TAB / f"direct_{crop}_national_effects.csv")
    return n[(n.model == "ppml") & (n.ecosystem == series) & (n["index"] == idx)][col].iloc[0]


def vrpf_strict():
    """Table 11: stricter validation for VR and PF (two episodes)."""
    rows = []
    for crop in ("vr", "pf"):
        t = pd.read_csv(TAB / f"validation_strict_{crop}.csv")
        for variant, g in t.groupby("variant", sort=False):
            g = g.set_index("episode")
            r = {"Index": crop.upper(), "Variant": variant}
            for ep in ("2015-16", "2023-24"):
                r[f"{ep} obs / pred"] = f"{g.loc[ep, 'observed_loss_pct']:.1f} / {g.loc[ep, 'predicted_loss_pct']:.1f}"
            r["Mean abs. error"] = g.error_pts.abs().mean()
            rows.append(r)
    return pd.DataFrame(rows)


def vrpf_totals():
    """Table 12: total loss over each path, VR and PF indices with their checks."""
    rows = []
    for crop, series in (("vr", ("vr", "vr_noroot")), ("pf", ("pf", "pf_nocavendish", "pf_nobanana"))):
        t = pd.read_csv(TAB / f"shocks_{crop}_episode_totals.csv")
        t["path"] = t.path.str.replace("unit RONI +1 (4 quarters from Q3)", "unit path: RONI +1 for 4 quarters",
                                       regex=False)
        for e in series:
            x = t[t.crop == e].set_index("path")
            r = {"Index": VRPF_INDEX[e]}
            for pth in x.index:
                r[pth] = f"{x.loc[pth, 'total_loss_pct_of_annual']:.1f} ({x.loc[pth, 'p05']:.1f} to {x.loc[pth, 'p95']:.1f})"
            rows.append(r)
    return pd.DataFrame(rows)


def luzon_shocks():
    """Table 4a: rice shocks, main and without the Luzon quarters of 2015Q4-2016Q2."""
    a = pd.read_csv(TAB / "shocks_rice_episode_totals.csv").set_index(["path", "crop"])
    b = pd.read_csv(TAB / "shocks_rice_episode_totals_no_luzon2015.csv").set_index(["path", "crop"])
    rows = []
    for pth in ("1997-98", "2015-16", "2023-24", "unit RONI +1 (4 quarters from Q3)"):
        for crop in ("palay", "irrigated", "rainfed"):
            x, y = a.loc[(pth, crop)], b.loc[(pth, crop)]
            rows.append({"Path": pth.replace("unit RONI +1 (4 quarters from Q3)", "unit path"),
                         "Series": crop,
                         "Main": f"{x.total_loss_pct_of_annual:.1f} ({x.p05:.1f} to {x.p95:.1f})",
                         "Without Luzon 2015Q4–2016Q2": f"{y.total_loss_pct_of_annual:.1f} ({y.p05:.1f} to {y.p95:.1f})"})
    return pd.DataFrame(rows)


def luzon(series, sample, col):
    t = pd.read_csv(TAB / "check_luzon_2015.csv")
    return t[(t.series == series) & (t["sample"] == sample)][col].iloc[0]


def faostat(series, col):
    t = pd.read_csv(TAB / "faostat_check_vrpf.csv")
    return t[t.series == series][col].iloc[0]


def faostat_table():
    """Table 11a: 1998 in FAOSTAT against the model's 1998 loss from the 1997-98 path."""
    t = pd.read_csv(TAB / "faostat_check_vrpf.csv").set_index("series")
    rows = []
    for k, lab in (("vr", "VR"), ("vr_noroot", "VR without root crops"), ("pf", "PF"),
                   ("pf_nobanana", "PF without banana")):
        x = t.loc[k]
        rows.append({"Index": lab,
                     "1998 vs trend, %": x.obs_dev_1998_pct,
                     "1998 vs 1996–97, %": x.obs_1998_vs_1996_97_pct,
                     "Trend residual SD, %": x.trend_resid_sd_pct,
                     "Model loss in 1998, %": (f"{x.model_loss_1998_pct:.1f} ({x.model_1998_p05:.1f} to "
                                               f"{x.model_1998_p95:.1f})" if pd.notna(x.model_loss_1998_pct) else "")})
    return pd.DataFrame(rows)


def vrpf_total(crop, series, path, col="total_loss_pct_of_annual"):
    t = pd.read_csv(TAB / f"shocks_{crop}_episode_totals.csv")
    return t[(t.crop == series) & (t.path == path)][col].iloc[0]


DELIVERY = ROOT / "outputs/delivery"
CATEGORY = {"rice": "Rice", "corn": "Corn", "veg_fruit": "Vegetables and fruits (VR + PF)",
            "other_food": "Other food (no El Niño shock, v5)",
            "nonrice_fallback": "Fallback: all food except rice (corn + VR + PF)",
            "rice_sensitivity_no_luzon2015": "Rice, without the Luzon typhoon quarters (upper bound)"}


def delivery_totals():
    """Table 13: total loss by food category and episode (delivery file)."""
    t = pd.read_csv(DELIVERY / "food_shocks_episode_totals.csv")
    rows = []
    for cat, lab in CATEGORY.items():
        x = t[t.category == cat].set_index("path")
        r = {"Category": lab}
        for pth in ("1997-98", "2015-16", "2023-24"):
            r[pth] = f"{x.loc[pth, 'total_loss_pct_of_annual']:.1f} ({x.loc[pth, 'p05']:.1f} to {x.loc[pth, 'p95']:.1f})"
        rows.append(r)
    return pd.DataFrame(rows)


def delivery_kcal():
    """Calorie totals of the estimated items, 2021-2023 (billion kcal a year), from the README."""
    import re
    txt = (DELIVERY / "README_food_shocks.md").read_text()
    m = re.search(r"corn ([\d,]+), VR ([\d,]+),\s*PF ([\d,]+)", txt)
    return [int(v.replace(",", "")) for v in m.groups()]


def quarterly_vrpf(crop):
    s = pd.read_csv(TAB / f"shocks_{crop}.csv")
    s = s[(s.crop == crop) & ~s.path.str.startswith("unit")]
    s = s.assign(S=s.S * 100, lo=s.S_p05 * 100, hi=s.S_p95 * 100, SD=s.S_D * 100)
    return pd.DataFrame({"Path": s.path, "Quarter": s.scenario_q,
                         "Shock (% of quarter)": s.S, "90% range": [f"{a:.1f} to {b:.1f}" for a, b in zip(s.lo, s.hi)],
                         "Scaled for DEFINE-PH (%)": s.SD})


# ---------------------------------------------------------------- document
def decline():
    """Step (2000) versus gradual linear change of the El Nino effect, Poisson."""
    s = pd.read_csv(TAB / "direct_v5_rice_spec_comparison_decline_no_dmi.csv")
    s = s[s.model == "ppml"].set_index(["ecosystem", "spec"])
    v = pd.read_csv(TAB / "direct_v5_rice_validation_decline_no_dmi.csv")
    mae = v.groupby(["ecosystem", "spec"]).error_pts.apply(lambda x: x.abs().mean())
    return {(e, sp): {"ic": s.loc[(e, sp), "ic_minus_base"], "today": s.loc[(e, sp), "B_RP_today"],
                      "y1995": s.loc[(e, sp), "B_RP_1995"], "mae": mae[(e, sp)]}
            for e in ("irrigated", "rainfed") for sp in ("step_2000", "gradual_linear")}


def decline_table():
    """Table 3a: step versus gradual change of the El Nino effect."""
    dc = decline()
    rows = []
    for e in ("irrigated", "rainfed"):
        for sp, lab in (("step_2000", "step in 2000 (recommended)"),
                        ("gradual_linear", "gradual (linear) decline")):
            d = dc[(e, sp)]
            rows.append({"Palay": e, "Change of the effect": lab,
                         "Fit vs step": "reference" if sp == "step_2000" else f"{-d['ic']:,.0f}",
                         "Validation error (pts)": d["mae"],
                         "Effect in 1995 (%)": (np.exp(d["y1995"]) - 1) * 100,
                         "Effect today (%)": (np.exp(d["today"]) - 1) * 100})
    return pd.DataFrame(rows)


def rice_calendar_table():
    """National growing window of total palay by harvest quarter (RiceAtlas, PSA weights)."""
    s = pd.read_csv(PROC / "rice_season_by_quarter.csv")
    w = pd.read_csv(PROC / "rice_growing_window.csv")
    s, w = s[s.ecosystem == "total"], w[w.ecosystem == "total"]
    prod = s.groupby(["region_code", "quarter"]).production_t.sum().rename("p").reset_index()
    w = w.merge(prod, on=["region_code", "quarter"])
    nat = (w.assign(x=w.weight * w.p).groupby(["quarter", "lag", "calendar_month"]).x.sum()
           / w.groupby(["quarter", "lag", "calendar_month"]).p.sum()).rename("weight").reset_index()
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    q_tot = s.groupby("quarter").production_t.sum()
    near = s[s.matched_by == "nearest"].groupby("quarter").production_t.sum() / q_tot
    rows = []
    for q in range(1, 5):
        m = nat[(nat.quarter == q) & (nat.weight >= 0.5)].sort_values("lag", ascending=False)
        rows.append({"Harvest quarter": f"Q{q}",
                     "Share of annual production (%)": 100 * q_tot[q] / q_tot.sum(),
                     "Months in the field (weight ≥ 0.5)": f"{names[m.calendar_month.iloc[0] - 1]}–"
                                                          f"{names[m.calendar_month.iloc[-1] - 1]}",
                     "Not covered by the calendar (%)": 100 * near.get(q, 0.0)})
    return pd.DataFrame(rows)


def corn_calendar_table():
    """National corn growing window by harvest quarter (GGCMI rainfed, cropland and PSA weights)."""
    w = pd.read_csv(PROC / "corn_growing_window.csv")
    w = w[w.calendar == "rainfed"]
    cov = pd.read_csv(TAB / "corn_calendar_coverage.csv")
    cov = cov[cov.calendar == "rainfed"].set_index("quarter")
    d = read_csv_prod_corn()
    w = w.merge(d, on=["region_code", "quarter"])
    nat = (w.assign(x=w.weight * w.p).groupby(["quarter", "lag", "calendar_month"]).x.sum()
           / w.groupby(["quarter", "lag", "calendar_month"]).p.sum()).rename("weight").reset_index()
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    rows = []
    for q in range(1, 5):
        m = nat[(nat.quarter == q) & (nat.weight >= 0.5)].sort_values("lag", ascending=False)
        rows.append({"Harvest quarter": f"Q{q}",
                     "Share of annual production (%)": 100 * cov.loc[q, "share_of_annual_production"],
                     "Months in the field (weight ≥ 0.5)": f"{names[m.calendar_month.iloc[0] - 1]}–"
                                                          f"{names[m.calendar_month.iloc[-1] - 1]}",
                     "Window from GGCMI (%)": 100 * cov.loc[q, "share_from_ggcmi"]})
    return pd.DataFrame(rows)


def read_csv_prod_corn():
    """PSA corn production by region and quarter of the year (2016-2025 total), from the crop panel."""
    c = pd.read_csv(PROC / "crop_region_quarter.csv")
    c = c[(c.series == "corn") & (c.variable == "production_t") & c.period.str[:4].astype(int).between(2016, 2025)]
    c = c.assign(quarter=c.period.str[-1].astype(int))
    return c.groupby(["region_code", "quarter"]).value.sum().rename("p").reset_index()


def stage1_scen_checks():
    """Van's scenario simulations: checks passed, by check."""
    c = pd.read_csv(TAB / "stage1_scenarios_check.csv")
    c["Check"] = c.check.str.replace(r" \(.*\)$", "", regex=True)
    g = c.groupby("Check", sort=False).agg(passed=("ok", "sum"), n=("ok", "size")).reset_index()
    return g.assign(**{"Passed": g.passed.astype(str) + " of " + g.n.astype(str)})[["Check", "Passed"]]


def stage1_scen_effects():
    """Largest national effect of each scenario (RONI model, palay weights), P, SM_RZ, T."""
    e = pd.read_csv(TAB / "stage1_scenarios_effects.csv")
    e = e[(e.model == "roni") & e["var"].isin(["P", "SM_RZ", "T"])]
    e = e.loc[e.assign(a=e["mean"].abs()).groupby(["scenario", "var"]).a.idxmax()]
    names = {"P": "Rainfall (mm/month)", "SM_RZ": "Root-zone soil moisture (m³/m³)", "T": "Temperature (°C)"}
    rows = []
    for sc in ["1997-98", "2015-16", "2023-24", "unit"]:
        r = {"Path": sc}
        for v, lab in names.items():
            x = e[(e.scenario == sc) & (e["var"] == v)].iloc[0]
            fmt = "{:+.3f}" if v == "SM_RZ" else ("{:+.2f}" if v == "T" else "{:+.0f}")
            mon = pd.Timestamp(x.date).strftime("%b %Y")
            rng = "" if abs(x.q90 - x.q10) < 1e-3 else f" ({fmt.format(x.q10)} to {fmt.format(x.q90)})"
            r[lab] = f"{fmt.format(x['mean'])}{rng}, {mon}"
        rows.append(r)
    return pd.DataFrame(rows)


def stage1_scen_range():
    """Share of simulated region-months outside the 1987-2025 observed range (RONI model)."""
    r = pd.read_csv(TAB / "stage1_scenarios_range.csv")
    r = r[(r.model == "roni") & r["var"].isin(["T", "SM_RZ", "SM_DEEP", "P"]) & r.scenario.isin(["1997-98", "unit"])]
    rows = []
    for v in ["T", "P", "SM_RZ", "SM_DEEP"]:
        x = r[r["var"] == v].set_index(["scenario", "path"])
        row = {"Variable": v}
        for sc in ["1997-98", "unit"]:
            for pth, lab in (("neutral", "neutral"), ("scenario", "El Niño")):
                y = x.loc[(sc, pth)]
                row[f"{sc}, {lab}"] = f"{y.share_below_pct + y.share_above_pct:.0f} ({y.share_below_pct:.0f} below)"
        rows.append(row)
    return pd.DataFrame(rows)


STAGE2_MODELS = {"linear": "Linear, 4 monthly means", "hinge": "Hinge, 4 monthly means (Eq. 11)",
                 "hinge_sm_t": "Hinge, T and SM_RZ", "hinge_extremes": "Hinge on monthly extremes",
                 "hinge_sm_tmax": "Hinge, TMAX and SM_RZ", "hinge_sm_edd30": "Hinge, EDD30 and SM_RZ",
                 "hinge_ldry_tmax": "Hinge, dry spell and TMAX",
                 "hinge_sm_t_post2000": "Hinge, T and SM_RZ, changing from 2000",
                 "gbm4": "Boosting, 4 monthly means", "gbm_all": "Boosting, 16 monthly features",
                 "gbm_daily": "Boosting, 30 monthly and daily features",
                 "gbm_daily_post2000": "Boosting, 30 features, changing from 2000"}
STAGE2_SHOWN = ("hinge_sm_t", "hinge_sm_t_post2000", "gbm_all", "gbm_daily_post2000")


def stage2_skill():
    s = pd.read_csv(TAB / "stage2_cv_skill.csv")
    d = s.groupby(["series", "fold_type", "model"]).deviance.sum()
    rows = []
    for mdl, lab in STAGE2_MODELS.items():
        r = {"Model": lab}
        for ser in ["irrigated", "rainfed", "corn"]:
            for ft, fl in (("block", "5-yr"), ("episode", "episodes")):
                r[f"{ser}, {fl}"] = 100 * (1 - d[(ser, ft, mdl)] / d[(ser, ft, "base")])
        rows.append(r)
    return pd.DataFrame(rows)


def stage2_folds_won():
    """Folds (of 11 per series) in which each model has the lowest held-out deviance."""
    s = pd.read_csv(TAB / "stage2_cv_skill.csv")
    s = s[s.model != "base"]
    best = s.loc[s.groupby(["series", "fold"]).deviance.idxmin()]
    return best.groupby("model").size()


def stage2_episodes():
    e = pd.read_csv(TAB / "stage2_cv_episodes.csv")
    g = e.groupby(["series", "episode"]).sum(numeric_only=True)
    rows = []
    for (ser, ep), x in g.iterrows():
        rows.append({"Series": ser, "Episode": ep, "Observed": 100 * (x.actual / x.base - 1),
                     **{STAGE2_MODELS[m]: 100 * (x[m] / x.base - 1) for m in STAGE2_SHOWN}})
    order = {"irrigated": 0, "rainfed": 1, "corn": 2}
    return pd.DataFrame(rows).sort_values(["Series", "Episode"], key=lambda c: c.map(order) if c.name == "Series" else c)


def stage2_hinge():
    """Hinge terms of the regression whose response changes from 2000: extra loss beyond the
    threshold before 2000 and today (before + shift)."""
    c = pd.read_csv(TAB / "stage2_coefficients.csv")
    c = c[c.model == "hinge_sm_t_post2000"].set_index(["series", "term"])
    lab = {"H_T": "Heat: window T above threshold (per °C)",
           "H_SM_RZ": "Dry soil: SM_RZ below threshold (per 0.01 m³/m³)"}
    rows = []
    for ser in ["irrigated", "rainfed", "corn"]:
        for term in ("H_T", "H_SM_RZ"):
            x, sh = c.loc[(ser, term)], c.loc[(ser, f"P_{term}")]
            k = 0.01 if term == "H_SM_RZ" else 1.0
            rows.append({"Series": ser, "Term": lab[term],
                         "Threshold": f"{x.threshold:.3g} {'°C' if term == 'H_T' else 'm³/m³'}"
                                      + (" (edge)" if x.on_grid_edge else ""),
                         "Before 2000 (%)": -100 * (np.exp(x.est * k) - 1),
                         "Today (%)": -100 * (np.exp((x.est + sh.est) * k) - 1),
                         "t of the change": sh.est / sh.se})
    return pd.DataFrame(rows)


def stage2_break():
    b = pd.read_csv(TAB / "stage2_break2000.csv").set_index("series")
    return {s_: (b.loc[s_, "wald"], int(b.loc[s_, "df"]), b.loc[s_, "p_value"]) for s_ in b.index}


def key_numbers():
    e = effects().set_index(["Palay", "Harvest season"])
    dry = "dry (Q1–Q2)"
    tot = episode_totals().set_index("Path (replayed under today's conditions)")
    val = validation().set_index(["Palay", "Specification"])["Mean abs. error (pts)"]
    q = pd.read_csv(TAB / "shocks_rice.csv")
    peak = q[(q.crop == "palay") & ~q.path.str.startswith("unit")].groupby("path").S.max() * 100
    return {
        "irr_now": -e.loc[("irrigated", dry), "From 2000"], "rf_now": -e.loc[("rainfed", dry), "From 2000"],
        "irr_before": -e.loc[("irrigated", dry), "Before 2000"], "rf_before": -e.loc[("rainfed", dry), "Before 2000"],
        "s97": tot.loc["1997-98", "Palay"], "s15": tot.loc["2015-16", "Palay"], "s23": tot.loc["2023-24", "Palay"],
        "mae_base_irr": val[("irrigated", "v5 (RONI only)")],
        "corn_dry": -corn_effects().set_index("Corn").loc["total", "Dry-season harvest (Q1–Q2), %"],
        "c97": episode_totals("corn", "corn", ()).set_index("Path (replayed under today's conditions)").loc["1997-98", "Corn"],
        "c15": episode_totals("corn", "corn", ()).set_index("Path (replayed under today's conditions)").loc["2015-16", "Corn"],
        "c23": episode_totals("corn", "corn", ()).set_index("Path (replayed under today's conditions)").loc["2023-24", "Corn"],
        "mae_rec_irr": val[("irrigated", "recommended (+ change from 2000)")],
        "peak_lo": peak[["1997-98", "2015-16"]].min(), "peak_hi": peak[["1997-98", "2015-16"]].max(),
    }


def main():
    k = key_numbers()
    doc = Document()
    setup(doc)
    doc.add_paragraph("El Niño shocks to agricultural production in the Philippines", style="Title")
    para(doc, "Results of the agricultural channel: working draft for discussion", size=12, color=MUTED)
    para(doc, f"Ginevra Ferraioli · updated {date.today():%d %B %Y}", size=9.5, color=MUTED)

    doc.add_heading("Summary", level=1)
    status(doc, "draft, updated as each part is completed")
    para(doc, "This note reports the results of the direct approach for the agricultural shocks. "
              "Rice, corn, vegetables and root crops (VR) and perennial fruits (PF) are complete up to "
              "the shocks, which are also given for the food categories of DEFINE-PH (section 6); "
              "the two-stage approach is under way (section 7). All results are provisional.")
    bullets(doc, [
        ("Methodology v5 as written does not reproduce the past El Niño episodes for rice. ",
         "Estimated without each strong episode in turn, it predicts a small loss in 1997–98, "
         "when production fell sharply, and a loss in 2015–16, when there was almost none."),
        ("Three changes, supported by the data, fix most of this: ",
         "separate effects for El Niño and La Niña, smooth regional trends, and an El Niño effect "
         "that is smaller from 2000 on. The specification with these changes is the one I "
         "recommend; it differs from methodology v5 and the changes are proposed for "
         "discussion (section 2.7). A stricter validation, which also chooses the year of the "
         "change inside each fold, confirms this for every episode separately (section 2.2)."),
        ("El Niño effect today: ", f"a sustained +1 °C RONI lowers dry-season rice harvests by about "
         f"{k['irr_now']:.0f}% (irrigated) and {k['rf_now']:.0f}% (rainfed); before 2000 the effects were "
         f"about {k['irr_before']:.0f}% and {k['rf_before']:.0f}%."),
        ("Shocks: ", f"replayed under today's conditions, the 1997–98 and 2015–16 episodes cost about "
         f"{k['s97']:.1f}% and {k['s15']:.1f}% of a year's palay production and 2023–24 about "
         f"{k['s23']:.1f}%, with wide ranges, mainly because the effect on irrigated rice is uncertain. "
         "These are probably too low: without the typhoon rain over Luzon in late 2015 they are about "
         "twice as large (Table 4a, an upper bound); stage 2 will settle it."),
        ("Corn: ", f"separate El Niño and La Niña effects and smooth trends matter even more than for "
         f"rice, but the effect has not changed over time. A sustained +1 °C El Niño lowers "
         f"dry-season corn harvests by about {k['corn_dry']:.0f}%; replayed today, the 1997–98, "
         f"2015–16 and 2023–24 episodes cost about {k['c97']:.1f}%, {k['c15']:.1f}% and "
         f"{k['c23']:.1f}% of a year's corn production, with wide ranges (section 3)."),
        ("Vegetables and fruits: ", f"a small loss for fruits and none for vegetables and root crops. "
         f"A sustained +1 °C El Niño lowers PF by about {-vrpf_effect('pf', 'pf'):.1f}%, entirely through "
         "bananas; for VR no loss can be detected. The data (from 2010) support a simpler model than "
         "for rice and corn: v5's single RONI effect with smooth trends and one national effect "
         "(section 5)."),
        ("RONI alone as the main driver: ", "adding the Indian Ocean Dipole index improves the "
         "out-of-sample predictions neither of production (direct approach, all crops) nor of the "
         "weather (stage 1, Van's test); its estimated effect on production has a sign the weather "
         "does not support, and it offsets a large part of the corn shocks. The results in this note "
         "therefore use RONI alone, as stage 1 now does; the DMI is kept as a variant and for stress "
         "scenarios. This changes the agreed scope and awaits Alper's agreement (section 4)."),
        ("Two-stage approach, stage 2 (weather → production): ", "estimated and tested out of sample "
         "on the monthly and daily weather (section 7.3). The response of production to the same weather "
         "has changed since 2000, as in the direct approach, and the models that allow for it predict "
         "best: they reproduce the 1997–98 losses of irrigated and rainfed rice when that episode is "
         "left out. The chain will use a hinge regression on temperature and soil moisture for irrigated "
         "rice and gradient boosting on all features for rainfed rice and corn. Van's scenario simulations pass the checks needed for "
         "the chain (section 7.2)."),
    ])
    doc.add_heading("How reliable are the results?", level=2)
    bullets(doc, [
        ("Solid: ", "the data reconcile with the PSA national totals; the effects are clear and make "
         "agronomic sense (dry-season harvests hit hardest, rainfed rice more than irrigated, corn "
         "most); they do not depend on the typhoon and flood controls, the Negros corn break or the "
         "Kanlaon eruption; and the recommended specification predicts each past episode better than "
         "methodology v5 as written, also under the stricter validation."),
        ("Weaker: ", "severe droughts are probably understated (the 1997–98 losses of rainfed rice and "
         "corn are not predicted when that episode is left out, and FAOSTAT shows larger 1998 losses "
         "of vegetables, root crops and bananas than the model gives); part of the smaller rice effect "
         "after 2000 comes from typhoon rain over Luzon in late 2015, so today's rice effect is "
         "probably understated (section 2.6); for stress scenarios the direct "
         "shocks are best read as a lower bound until the two-stage approach is in place; the "
         "ranges are wide, and include no loss for irrigated rice and, in 1997–98 and 2015–16, for "
         "palay and total corn; there are only "
         "three strong episodes (two for VR and PF); and the specification was chosen on the same "
         "data, which the validation guards against only partly."),
    ])

    doc.add_heading("1. Data", level=1)
    status(doc, "complete")
    para(doc, "All series are rebuilt from PSA provincial data on the 16 regions of methodology v5 "
              "(the structure before the Negros Island Region): palay by ecosystem and corn by type "
              "from 1987, and the 13 VR and PF crops from 2010 (PSA OpenSTAT; the provincial tables "
              "are needed to put the NIR provinces back into Regions VI and VII). Boundary rules:")
    bullets(doc, [
        "Negros Occidental in Region VI and Negros Oriental and Siquijor in Region VII for all years;",
        "Sulu and Cotabato City in BARMM for all years;",
        "the Eight Cluster Areas, included in PSA's BARMM total from 2023 but in no province row, are "
        "added to Region XII, so that both regions keep their pre-2023 boundaries.",
    ])
    para(doc, "The 16 regions add up to the PSA national totals in every quarter, and the VR and PF "
              "calorie indices reproduce Alper Aras's workbook (v35) exactly for every region whose "
              "boundaries are unchanged. Negros Occidental corn falls sharply from 2023Q3, mostly in "
              "area harvested, in a way not seen elsewhere; the published data are kept and the "
              "issue is treated in the estimation (section 3).")
    para(doc, "Controls (by region and quarter): typhoon exposure by PAGASA category (IBTrACS), flood "
              "occurrence (EM-DAT), earthquakes (USGS, M ≥ 6.5) and eruptions (GVP, VEI ≥ 3, Pinatubo "
              "1991 separately). Typhoon and flood exposure is weighted by each crop's production across "
              "the provinces of a region (rice by ecosystem, corn by type, VR and PF by calorie "
              "output). The controls measure "
              "exposure, not damage, and are set to “no event” in the shocks, so that the El Niño shock "
              "can be combined with the CAT damage ratios.")

    doc.add_heading("2. Rice (palay)", level=1)
    status(doc, "draft; the recommended specification awaits agreement")
    doc.add_heading("2.1 Methodology v5 and the choices left open", level=2)
    para(doc, "The direct approach of methodology v5 (Eqs. 4–6) relates log production to RONI and "
              "DMI lagged 1–4 quarters, with a single-peaked (binomial) lag profile whose timing is "
              "chosen by profile estimation, regional total effects, region-specific seasonal "
              "effects and one linear trend per region. Methodology v5 lists several choices as "
              "still to be tested on the palay data. Table 1 tests them one at a time, for irrigated "
              "and rainfed palay separately (Poisson pseudo-maximum likelihood, 16 regions, "
              "1987–2025).")
    table(doc, spec_tests(), [5.6, 2.4, 2.6, 2.4, 2.6],
          note="Table 1. Fit gain = fall in the information criterion against v5 Eq. 4 with RONI only "
               "(as written but without the DMI, section 4; with the DMI the tests point to the same "
               "choices) (deviance + k ln n; positive = better after charging for extra parameters). El Niño "
               "effect = production-weighted national total effect of a sustained +1 °C RONI, log "
               "points (El Niño part when El Niño and La Niña are separate; dry-season harvest when "
               "effects differ by season).",
          fmt={"Fit gain, irrigated": "{:,.0f}", "Fit gain, rainfed": "{:,.0f}",
               "El Niño effect, irrigated": "{:.3f}", "El Niño effect, rainfed": "{:.3f}"})
    para(doc, "Two choices matter. Smooth regional trends give by far the largest improvement in fit, "
              "without changing the El Niño effect much. Separate El Niño and La Niña effects "
              "double or triple the El Niño effect: in these data La Niña does not raise rice "
              "production, so a single linear RONI term understates the El Niño loss. The lags of "
              "v5 (1–4) are confirmed: adding the current quarter worsens the fit and two more lags "
              "add nothing.")

    doc.add_heading("2.2 Validation on past episodes", level=2)
    para(doc, "As methodology v5 asks, each strong El Niño episode is left out in turn, the model is "
              "re-estimated without it (timing included), and the predicted loss is compared with the "
              "observed one. Losses are measured against the model's own neutral path (RONI = DMI = 0) "
              "over the episode's quarters, for all regions.")
    table(doc, validation(), [1.7, 4.6, 2.4, 2.4, 2.4, 2.3],
          note="Table 2. Loss in % of neutral production over the episode: observed / predicted by "
               "the model estimated without the episode. Observed losses differ slightly between "
               "specifications because each is measured against that model's neutral path.",
          fmt={"Mean abs. error (pts)": "{:.1f}"})
    para(doc, "No v5 variant reproduces 1997–98 and 2015–16 together: both were strong El Niños, but "
              "the first caused large losses and the second almost none. Allowing the El Niño effect "
              "to change over time resolves most of this. A change in 2000 fits best (2005 is close, "
              f"2010 weak) and brings the mean prediction error for irrigated palay from "
              f"{k['mae_base_irr']:.1f} to {k['mae_rec_irr']:.1f} percentage points. Likely reasons are the expansion of irrigation, new varieties and "
              "drought response. For rainfed palay the 1997–98 loss is still understated, consistent "
              "with losses that rise faster than linearly in severe droughts, the case that methodology "
              "v5 makes for the two-stage approach.")
    st = strict("rice")
    para(doc, "Stricter validation. The validation above re-estimates the timing in each fold, but the "
              "year of the change (2000) and the other choices were made on the full sample, and the "
              "quarters right after each episode, whose lags contain the episode, stayed in the "
              "estimation. A stricter version therefore (i) also leaves out the four quarters after each "
              "episode, (ii) chooses the year of the change inside each fold among 2000, 2005, 2010 and "
              "no change, using only the estimation data, and (iii) sets the trends on those years only "
              "(restricted cubic splines). Table 2a gives the error for each episode separately.")
    table(doc, st, [1.9, 3.0, 1.5, 1.5, 1.5, 1.6, 1.8, 3.0],
          note="Table 2a. Stricter validation, palay (Poisson): predicted − observed loss, percentage "
               "points, for each left-out episode; mean absolute error over the three, and its range when "
               "one episode is left out of the mean; year of the change chosen in each fold "
               "(1997–98 / 2015–16 / 2023–24).",
          fmt={"1997-98": "{:.1f}", "2015-16": "{:.1f}", "2023-24": "{:.1f}", "Mean abs. error": "{:.1f}"})
    para(doc, "The recommended specification predicts every episode better than methodology v5 as "
              "written, for irrigated and rainfed palay, and the result does not hinge on any single "
              "episode (the mean error stays far lower whichever episode is left out of it). For "
              f"irrigated palay the error falls from {strict_mae('rice', 'irrigated', 'v5 as written, no DMI'):.1f} "
              f"to {strict_mae('rice', 'irrigated', 'recommended, no DMI (nested break)'):.1f} points (RONI "
              "only; with the DMI the errors are similar, Table 2a) and every fold "
              "chooses 2000 by a wide margin. For rainfed palay the fold without 1997–98 chooses 2005, "
              "so the change lies around 2000–2005; 1997–98 remains the large miss.")

    doc.add_heading("2.3 Recommended specification", level=2)
    para(doc, "Methodology v5 (Eqs. 4–6) with: separate El Niño and La Niña effects; smooth regional "
              "trends (natural cubic spline); an El Niño and La Niña effect that shifts from 2000 on, "
              "by a common amount in all regions; and a shift in wet-season harvest quarters. The lag "
              "profile, the timing by profile estimation, regional effects, the controls and the "
              "Driscoll–Kraay standard errors are as in v5. The shocks use the effect from 2000, which "
              "reflects today's farming conditions, in the same way as v5 evaluates the trend at "
              "today's climate.")
    dc = decline()
    para(doc, "Step or gradual change? The step in 2000 was compared with an effect that declines "
              "linearly over time (same number of parameters). The step fits better (information "
              f"criterion lower by {dc[('irrigated', 'gradual_linear')]['ic']:.0f} for irrigated and "
              f"{dc[('rainfed', 'gradual_linear')]['ic']:.0f} for rainfed palay) and predicts the "
              f"episodes better (mean error {dc[('irrigated', 'step_2000')]['mae']:.1f} against "
              f"{dc[('irrigated', 'gradual_linear')]['mae']:.1f} points for irrigated, "
              f"{dc[('rainfed', 'step_2000')]['mae']:.1f} against {dc[('rainfed', 'gradual_linear')]['mae']:.1f} "
              "for rainfed). Both agree on a large effect in the 1990s; they differ on today's: the "
              "data show a fall around 2000 and a roughly constant effect since, whereas a straight "
              "line keeps falling and puts today's effect closer to zero, that is a smaller loss (irrigated "
              f"{dc[('irrigated', 'gradual_linear')]['today']:+.2f} against "
              f"{dc[('irrigated', 'step_2000')]['today']:+.2f} log points; rainfed "
              f"{dc[('rainfed', 'gradual_linear')]['today']:+.2f} against "
              f"{dc[('rainfed', 'step_2000')]['today']:+.2f}). The step is kept; the gradual decline is "
              "a sensitivity that gives a lower bound for the loss.")
    table(doc, decline_table(), [1.8, 4.6, 2.2, 2.6, 2.4, 2.4],
          note="Table 3a. Step versus gradual change of the El Niño effect (Poisson, recommended "
               "specification otherwise). Fit vs step = fall in the information criterion against the "
               "step (negative = worse). Validation error = mean absolute error of the leave-one-episode-"
               "out predictions. Effects: sustained +1 °C El Niño, dry-season harvest, production-weighted "
               "national effect, %.",
          fmt={"Validation error (pts)": "{:.1f}", "Effect in 1995 (%)": "{:.1f}", "Effect today (%)": "{:.1f}"})
    table(doc, effects(), [2.0, 3.0, 2.4, 2.1, 2.4, 2.4],
          note="Table 3. Effect of a sustained +1 °C El Niño (RONI) on palay production, % (Poisson; "
               "production-weighted national effect).",
          fmt={"Before 2000": "{:.1f}", "From 2000": "{:.1f}", "t (before)": "{:.1f}",
               "t (from 2000)": "{:.1f}"})
    figure(doc, FIG / "direct_rice_effects.png", 16.4,
           "Figure 1. El Niño effect by region (dry-season harvest, before 2000) with 95% intervals; "
           "lines: national effect before and from 2000.")

    doc.add_heading("2.4 Shocks", level=2)
    para(doc, "Following methodology v5 (Eqs. 12–13b), the shock is the share of production lost "
              "compared with the neutral path (RONI = DMI = 0), with the exposure controls at “no "
              "event” in both runs. Regional shocks are combined with each region's share of neutral "
              "production, irrigated and rainfed palay with their production shares, and the result "
              "is also scaled for DEFINE-PH's quarters. The range is the 90% interval of a block "
              "bootstrap over years (200 draws) that re-estimates the timing in each draw. The paths "
              "are the El Niño quarters (RONI ≥ 0.5) of the three strong episodes, replayed under "
              "today's conditions. The shocks use RONI alone (section 4); with the DMI they are in "
              "Table 8c.")
    table(doc, episode_totals(), [5.4, 1.6, 2.5, 1.8, 1.7, 2.6],
          note="Table 4. Total loss over the path and the four quarters after it, % of one year's "
               "neutral production.",
          fmt={"Palay": "{:.1f}", "Irrigated": "{:.1f}", "Rainfed": "{:.1f}",
               "Draws with a loss (palay, %)": "{:.0f}"})
    figure(doc, FIG / "shocks_rice.png", 16.4,
           "Figure 2. Quarterly palay shock (share of the quarter's neutral production) with the 90% "
           "bootstrap range; dashed: irrigated and rainfed; shaded: quarters of the path.")
    para(doc, "With lags starting at one quarter, the first quarter of a path has no shock; losses "
              "peak one to two quarters after the peak of RONI, in the dry-season harvest (Q1–Q2), at "
              f"about {k['peak_lo']:.1f}–{k['peak_hi']:.1f}% of the quarter's production in the strong "
              "episodes. The quarterly values "
              "are in Annex Table A1.")

    doc.add_heading("2.5 Checks", level=2)
    kan, ctl = rice_checks()
    para(doc, "The El Niño effects do not depend on choices outside the climate terms: adding the "
              "2024–26 Kanlaon eruption (VEI 2 in the GVP file used, VEI 3 in the current database) to "
              f"the eruption marker changes them by at most {kan:.3f} log points; in the first-look model, "
              "dropping the typhoon and flood controls altogether changes the dry-season El Niño effect "
              f"by at most {ctl:.3f} (typhoons are only slightly less frequent in El Niño years in these "
              "data), which supports adding the El Niño shock to the CAT damage ratios without double "
              "counting. With the controls set to “no event” in both runs, the shocks contain only the "
              "drought and heat effect.")

    doc.add_heading("2.6 Limitations", level=2)
    bullets(doc, [
        ("The change in 2000 rests on three strong episodes. ", "The stricter validation chooses it in "
         "every irrigated fold (around 2000–2005 for rainfed), but with three episodes it is a clear "
         "pattern, not proof. A gradual (linear) decline, tested as an alternative, fits worse and "
         "predicts the episodes less well (section 2.3); it puts today's effect closer to zero, so it "
         "gives a lower bound for the loss."),
        ("Rainfed 1997–98 is understated, ", "which supports the two-stage approach for severe droughts."),
        ("The change in 2000 may partly reflect the weather of 2015–16. ", "Stage 1 (Van) shows that "
         "2015–16 was much less dry than its RONI implies, because typhoons Lando and Nona brought "
         "heavy rain to Luzon in October–December 2015, just before the 2016 dry-season harvest. The "
         "typhoon controls measure wind exposure, not rain, so the direct approach may read this as a "
         "smaller El Niño effect after 2000. A check confirms that this matters: without the Luzon "
         "regions in 2015Q4–2016Q2 (21 of 2,496 region-quarters), the gain in fit from the change in "
         f"2000 falls from {luzon('irrigated', 'all quarters', 'fit_gain_from_change'):.0f} to "
         f"{luzon('irrigated', 'without Luzon 2015Q4-2016Q2', 'fit_gain_from_change'):.0f} for irrigated "
         "palay, and today's dry-season effect roughly doubles, from "
         f"{(np.exp(luzon('irrigated', 'all quarters', 'effect_from_2000')) - 1) * 100:.1f}% to "
         f"{(np.exp(luzon('irrigated', 'without Luzon 2015Q4-2016Q2', 'effect_from_2000')) - 1) * 100:.1f}% "
         "per +1 °C (rainfed: "
         f"{(np.exp(luzon('rainfed', 'all quarters', 'effect_from_2000')) - 1) * 100:.1f}% to "
         f"{(np.exp(luzon('rainfed', 'without Luzon 2015Q4-2016Q2', 'effect_from_2000')) - 1) * 100:.1f}%). "
         "The change in 2000 remains (t = "
         f"{luzon('irrigated', 'without Luzon 2015Q4-2016Q2', 't_change'):.1f} for irrigated palay), but "
         "a large part of it comes from these quarters, so today's effect and the rice shocks are "
         "probably understated. Table 4a gives the shocks of this sensitivity. Removing only "
         "favourable weather is one-sided, so they are an upper bound rather than a better estimate; "
         "stage 2, which uses the observed weather of every year including typhoon rain, should "
         "settle where between the two the effect lies (outputs/tables/check_luzon_2015.csv)."),
        ("The effect on irrigated palay is uncertain: ", "its range includes zero, which widens the "
         "palay range."),
        ("The estimators differ on one choice: ", "least squares on logs does not prefer separate El "
         "Niño and La Niña effects, Poisson does."),
        ("The DMI ", "cannot be separated well from RONI (section 4)."),
    ])

    if (TAB / "shocks_rice_episode_totals_no_luzon2015.csv").exists():
        table(doc, luzon_shocks(), [3.0, 2.2, 5.0, 5.4],
              note="Table 4a. Rice shocks with and without the Luzon regions in 2015Q4–2016Q2 in the "
                   "estimation (sensitivity, an upper bound): total loss over the path and the four "
                   "quarters after it, % of one year's neutral production, central value (90% bootstrap "
                   "range).")
    doc.add_heading("2.7 Proposed changes to methodology v5", level=2)
    status(doc, "proposed, for discussion")
    bullets(doc, [
        ("Eq. 4: ", "separate total effects for El Niño (RONI+) and La Niña (RONI−), same timing."),
        ("Eq. 4: ", "smooth regional trends instead of one linear trend per region."),
        ("New: ", "an El Niño effect that changes over time (a step in 2000) for rice, with the shocks "
         "computed for today's conditions; not for corn (section 3)."),
        ("VR and PF: ", "one RONI effect as in Eq. 4, with smooth regional trends and one national "
         "effect, since 16 years of data cannot separate regional effects (section 5)."),
        ("Section 3.6: ", "define the observed loss used in the validation (against the model's "
         "neutral path, as in section 2.2), leave out the quarters after each episode as well, and "
         "make every specification choice inside each fold (Table 2a)."),
        ("Eqs. 4–6 and stage 1: ", "RONI alone as the main driver, with the DMI as a variant and a "
         "stress-scenario option (section 4; used in the results, to be agreed with Alper)."),
        ("Section 3.5: ", "state that, with lags from one quarter, the first quarter of a path has "
         "no shock."),
        ("Additions: ", "the rule for the Eight Cluster Areas, the rule for PSA measurement breaks, "
         "and the exact definitions of the controls."),
    ])

    doc.add_heading("3. Corn", level=1)
    status(doc, "draft; the recommended specification awaits agreement")
    cs = corn_specs()
    cb = pd.read_csv(TAB / "direct_v5_corn_spec_comparison_breaks_no_dmi.csv").set_index(["model", "spec"])
    para(doc, "The same approach is applied to total, white and yellow corn (16 regions, 1987–2025), "
              "with typhoon and flood exposure weighted by corn production. Table 5 repeats the main "
              "tests of section 2 on total corn.")
    table(doc, cs, [6.4, 2.8, 3.4, 3.4],
          note="Table 5. Total corn, Poisson, RONI only. Fit gain against v5 Eq. 4 with RONI only (positive = better after "
               "charging for extra parameters); El Niño effect = production-weighted national effect "
               "of a sustained +1 °C RONI in dry-season harvests (before 2000 for the step); "
               "validation error = mean absolute error of the leave-one-episode-out predictions.",
          fmt={"El Niño effect (log points)": "{:.3f}", "Validation error (pts)": "{:.1f}"})
    para(doc, "Separate El Niño and La Niña effects and smooth trends matter even more for corn than for "
              "rice: methodology v5 as written finds almost no El Niño effect, because La Niña does not "
              "raise corn production either, so a single linear RONI term cancels the El Niño loss. "
              "Unlike rice, the corn effect has not fallen over time: with a step in 2000 the El Niño "
              "effect becomes, if anything, slightly larger, not smaller "
              f"(t = {cb.loc[('ppml', 'step_2000'), 't_shift_RP_post']:.1f}); least squares on logs "
              "prefers no change; and neither the step nor a gradual change clearly improves the "
              "predictions. Plausibly corn, largely rainfed, did not benefit from the expansion of "
              "irrigation. The recommended corn specification therefore has no change over time.")
    table(doc, strict("corn"), [1.9, 3.0, 1.5, 1.5, 1.5, 1.6, 1.8, 3.0],
          note="Table 5a. Stricter validation, total corn (as Table 2a). Here “recommended” lets each "
               "fold choose the year of a change (with the DMI every fold picks 2005, without it 2010, "
               "2010 and 2005); the recommended corn "
               "specification itself has no change over time, because the full-sample test below does "
               "not confirm one.",
          fmt={"1997-98": "{:.1f}", "2015-16": "{:.1f}", "2023-24": "{:.1f}", "Mean abs. error": "{:.1f}"})
    para(doc, "Under the stricter validation the corn specification with separate El Niño and La Niña "
              "effects and smooth trends also predicts every episode better than methodology v5 as "
              "written (mean error "
              f"{strict_mae('corn', 'corn', 'recommended, no DMI (nested break)'):.1f} against "
              f"{strict_mae('corn', 'corn', 'v5 as written, no DMI'):.1f} points, RONI only), again with "
              "1997–98 the largest miss.")
    para(doc, "Since the stricter validation picks a break year inside each fold (2005 or 2010), the break "
              "year was also tested on the full sample (2000, 2005, 2010). With Poisson a step fits "
              f"somewhat better ({-cb.loc[('ppml', 'step_2005'), 'ic_minus_base']:.0f} points for 2005, "
              f"{-cb.loc[('ppml', 'step_2010'), 'ic_minus_base']:.0f} for 2010), but El Niño's effect does not "
              f"change consistently: from {cb.loc[('ppml', 'step_2005'), 'B_RP']:.2f} to "
              f"{cb.loc[('ppml', 'step_2005'), 'B_RP_today']:.2f} with a step in 2005 "
              f"(t = {cb.loc[('ppml', 'step_2005'), 't_shift_RP_post']:.1f}), and from "
              f"{cb.loc[('ppml', 'step_2010'), 'B_RP']:.2f} to {cb.loc[('ppml', 'step_2010'), 'B_RP_today']:.2f} "
              f"with a step in 2010 (t = {cb.loc[('ppml', 'step_2010'), 't_shift_RP_post']:.1f}), a larger "
              "effect today; least squares on logs prefers no break for every year. The recommended corn "
              "specification is kept without a break; a step in 2010 is a sensitivity that would make "
              "today's effect, and so the loss, somewhat larger.")
    table(doc, corn_effects(), [2.0, 3.6, 1.8, 3.6, 1.8],
          note="Table 6. Effect of a sustained +1 °C El Niño (RONI) on corn production, % (Poisson; "
               "production-weighted national effect; recommended corn specification).",
          fmt={"Dry-season harvest (Q1–Q2), %": "{:.1f}", "Wet-season harvest (Q3–Q4), %": "{:.1f}",
               "t (dry)": "{:.1f}", "t (wet)": "{:.1f}"})
    para(doc, "El Niño lowers dry-season corn harvests by about a quarter for each +1 °C; wet-season "
              "harvests rise slightly, which most likely reflects harvests shifting from the first to "
              "the second half of the year rather than a gain, and nets out in the shocks, which add up "
              "the quarters. As for rainfed rice, the 1997–98 loss is not predicted when that episode is "
              "left out, consistent with losses that rise faster than linearly in severe droughts.")
    para(doc, "Negros Occidental: corn area harvested falls from 2023Q3 (about 68,000–70,000 ha a year "
              "in 2018–2022, 27,000 ha in 2025), not seen in the rest of Region VI or the country. The "
              "published data are kept and a level dummy for Region VI corn from 2023Q3 is included. "
              "With the smooth trends of the recommended specification the dummy is small, because the "
              "Region VI trend follows the fall, and its start date cannot be identified; the national "
              "El Niño effect is the same whatever the start, and the same when Region VI corn is "
              "dropped from 2023Q3, or when the 2024–26 Kanlaon eruption is added to the eruption "
              f"marker (largest difference {corn_checks():.3f} log points).")
    if (TAB / "shocks_corn_episode_totals.csv").exists():
        table(doc, episode_totals("corn", "corn", ("corn_white", "corn_yellow")), [5.4, 1.6, 2.5, 1.8, 1.7, 2.6],
              note="Table 7. Corn: total loss over the path and the four quarters after it, % of one "
                   "year's neutral production (same paths and method as Table 4).",
              fmt={"Corn": "{:.1f}", "White": "{:.1f}", "Yellow": "{:.1f}",
                   "Draws with a loss (corn, %)": "{:.0f}"})
        figure(doc, FIG / "shocks_corn.png", 16.4,
               "Figure 3. Quarterly corn shock (share of the quarter's neutral production) with the 90% "
               "bootstrap range; dashed: white and yellow corn; shaded: quarters of the path.")

    doc.add_heading("4. The DMI", level=1)
    status(doc, "RONI alone used as the main driver from 16 November 2026, in the direct approach and "
                "in stage 1; to be agreed with Alper. Tables 8 and 8a are from the specifications with "
                "the DMI, the variant")
    q3, q4 = roni_dmi_corr()
    para(doc, "Methodology v5 includes the Dipole Mode Index (DMI) of the Indian Ocean Dipole with its "
              "own lag profile. In the production equation it raises three concerns. Its timing cannot "
              "be identified: the timing parameter ends at the edge of the grid in most fits. It moves "
              f"together with RONI exactly when El Niño builds (correlation {q3:.2f} in Q3 and {q4:.2f} "
              "in Q4, 1987–2025; all three strong episodes had a positive IOD), so the two effects are "
              "hard to separate. And where it matters it raises production: a positive IOD goes with "
              "higher dry-season harvests of rainfed rice and corn, which has not been checked against the "
              "weather (does a positive IOD bring the Philippines more rain or soil moisture in "
              "October–March?). Part of that positive effect may offset an El Niño effect estimated too "
              "negative. Table 8 compares the recommended specifications with and without the DMI.")
    table(doc, dmi_table(), [2.6, 3.1, 3.1, 3.3, 3.6],
          note="Table 8. With and without the DMI (recommended specification otherwise; Poisson unless "
               "stated). El Niño effect (log points): dry-season harvest, before 2000 for rice; one RONI "
               "effect for VR and PF. Validation errors: mean absolute error over the episodes (three; two "
               "for VR and PF), first and stricter validation. Fit gain without the DMI: positive = better "
               "without it after charging for parameters.")
    table(doc, decomposition(), [2.4, 2.0, 3.6, 3.6, 3.6],
          note="Table 8a. RONI and DMI parts of the episode shocks: total loss over the path and the "
               "quarters after it, % of one year's neutral production (central values, recommended "
               "specifications with the DMI). The parts are computed with the other index set to zero; "
               "they add up to the shock only approximately.",
          fmt={"Shock (RONI and DMI)": "{:.1f}", "RONI part (DMI = 0)": "{:.1f}",
               "DMI part (RONI = 0)": "{:.1f}"})
    para(doc, "The DMI matters much more for the shocks than for the El Niño effect. All three strong "
              "episodes had a positive IOD, so the estimated DMI effect enters every episode path. For "
              "corn it offsets about half of the 1997–98 loss and most of the 2023–24 loss "
              f"({decomp('corn', '2023-24', 'RONI and DMI'):.1f}% with the DMI against "
              f"{decomp('corn', '2023-24', 'RONI only (DMI = 0)'):.1f}% from RONI alone); for palay the "
              "irrigated and rainfed DMI effects cancel; for VR the whole episode loss comes from the DMI. "
              "Since the El Niño effect hardly changes when the DMI is dropped (Table 8), the RONI part is "
              "close to the shock of a model without the DMI.")
    para(doc, "Without the DMI the El Niño effect barely changes, so the main results do not depend on "
              "it. The evidence on keeping it is mixed: rice is predicted better without it, corn with it, "
              "VR and PF give no clear answer, and the estimators disagree on the fit. Its sign also differs across crops: a "
              "positive IOD goes with more rainfed rice, corn and fruit but less irrigated rice and fewer "
              "vegetables and root crops, which is hard to explain physically. The shocks would rise "
              "without it, because the positive IOD of the episodes would no longer offset part of the "
              "El Niño loss: for corn by up to about 6 points of a year's production (Table 8a).")
    doc.add_heading("4.1 The same test for both models", level=2)
    para(doc, "Van tested the DMI in stage 1 by nested cross-validation: 5-year blocks of years are held "
              "out in turn, with the lags and modes chosen without them. Adding the DMI to RONI does not "
              "improve the predictions of any weather variable (changes within about 2%, rainfall "
              "significantly worse in January–March and July–September). Holding RONI fixed, a positive "
              "IOD makes the Philippines drier, not wetter: about 4–5% less October–December rainfall per "
              "standard deviation of the DMI, in all regions and most in Mindanao, against about 16% for "
              "a comparable El Niño anomaly; there is no effect in January–June. The two indices move "
              "together only in the second half of the year (correlation about 0.4 in July–September, "
              "0.45–0.6 in October–December).")
    para(doc, "The same rule is applied to the direct approach: a driver is kept only if it improves "
              "out-of-sample prediction. The 5-year blocks are those of stage 1 (1985–89, …, 2020–25), "
              "each held out with the four quarters after it; the timing and the trends are set on the "
              "remaining years, and every held-out quarter is predicted.")
    table(doc, dmi_blocked(), [2.8, 1.4, 2.6, 2.6, 2.6, 2.4],
          note="Table 8b. Blocked nested cross-validation of the direct approach (Poisson, recommended "
               "specifications): change in the mean squared error of log production when the DMI is "
               "added, % (positive = better with the DMI), with a 90% bootstrap range over blocks "
               "(uninformative with three blocks for VR and PF); the same for the Poisson deviance; and "
               "the number of blocks predicted better with the DMI.",
          fmt={"Error change with the DMI, %": "{:+.1f}", "Deviance change with the DMI, %": "{:+.1f}"})
    para(doc, "As in stage 1, adding the DMI improves the predictions for no series: the changes are "
              "within about 1.5% either way, and the only ranges that exclude zero (irrigated palay, PF) show it "
              "making them worse. The positive effect on production cannot come from typhoons, the one "
              "channel a rainfall-based stage 1 would miss: the DMI effect is estimated with the typhoon "
              "and flood controls, and it is the same without them (corn "
              f"{dmi_controls('corn', 'all controls (recommended)'):.2f} with, "
              f"{dmi_controls('corn', 'no typhoon controls'):.2f} without; rainfed palay "
              f"{dmi_controls('rainfed', 'all controls (recommended)'):.2f} and "
              f"{dmi_controls('rainfed', 'no typhoon controls'):.2f}); nor does a positive IOD go with "
              "less typhoon exposure in the rice and corn areas.")
    if all((TAB / f"shocks_{c}_episode_totals_with_dmi.csv").exists() for c in ("rice", "corn", "vr", "pf")):
        table(doc, no_dmi_totals(), [2.4, 2.0, 5.0, 5.0],
              note="Table 8c. Episode shocks of the recommended specifications, RONI only (the main "
                   "results) and with the DMI (the variant): total loss over the path and the quarters "
                   "after it, % of one year's neutral production, central value (90% bootstrap range).")
        para(doc, "Without the DMI the corn shocks are larger, about 9% of a year's production for 1997–98 "
                  "and 5% for 2023–24 instead of 6% and 2%, and the ranges are narrower: the 2023–24 corn "
                  "and palay ranges and all PF ranges no longer include zero. Palay changes little (the "
                  "irrigated and rainfed DMI effects offset each other), and VR stays close to zero. "
                  "Narrower ranges partly reflect fewer parameters; they do not show that the shocks "
                  "without the DMI are more accurate, which stage 2 will test.")
    doc.add_heading("4.2 Decision", level=2)
    para(doc, "RONI alone is used as the main driver, in the direct approach and in stage 1 (Van, 16 "
              "November 2026), by the same rule for both models: a driver is kept only if it improves "
              "out-of-sample prediction. The DMI is kept as a documented variant (the shocks with the DMI, "
              "Table 8c) and for stress scenarios with a strong El Niño and a strong positive IOD. These "
              "go through the two-stage approach with stage 1's RONI + DMI model, whose October–December "
              "drying matches the observed one, not through the DMI effect of the direct approach. This "
              "changes the agreed scope (RONI and DMI as drivers) and needs Alper's agreement.")

    doc.add_heading("5. Vegetables and root crops (VR) and perennial fruits (PF)", level=1)
    status(doc, "draft; the recommended specification awaits agreement")
    para(doc, "VR and PF are the calorie-weighted production indices of methodology v5 (FNRI factors, "
              "fixed 2021–2023 calorie shares; banana varieties updated 11 November 2026), rebuilt on "
              "the 16 regions from 2010Q1 to 2025Q4. The estimated outcome is the calorie energy of "
              "the index's crops, so the effects are proportional changes of the index. Both indices are "
              "concentrated: root crops (cassava and sweet potato) dominate VR in kcal, with BARMM and "
              "Region X producing half of it; bananas dominate PF, with Regions XI, X and XII producing "
              "over 70%. Typhoon and flood exposure is weighted by each index's calorie output across "
              "the provinces of a region. With quarterly data from 2010, only the 2015–16 and 2023–24 "
              "episodes are in the sample.")
    doc.add_heading("5.1 Specification", level=2)
    table(doc, vrpf_specs(), [4.6, 1.5, 1.6, 1.5, 1.5, 1.6, 1.5],
          note="Table 9. VR and PF, Poisson, RONI only. Fit gain = fall in the information criterion against v5 as "
               "written (positive = better after charging for extra parameters). El Niño effect = "
               "production-weighted national effect of a sustained +1 °C RONI, % (El Niño part when El "
               "Niño and La Niña are separate). Validation error = mean absolute error of the "
               "leave-one-episode-out predictions, 2015–16 and 2023–24, points.",
          fmt={"El Niño effect, VR (%)": "{:.1f}", "El Niño effect, PF (%)": "{:.1f}",
               "Validation error, VR": "{:.1f}", "Validation error, PF": "{:.1f}"})
    para(doc, "Two choices matter, and both point to a simpler model than for rice and corn. Smooth "
              "regional trends are again essential, especially for VR: with v5's linear trends El Niño "
              "appears to raise VR, an artefact of the expansion of cassava in Regions II, IX and XII "
              "until about 2015 and of the fall of root crops in Region V from 2023, which a straight "
              "line cannot follow. And with 16 years of data one national effect fits better than 16 "
              "regional effects for both indices, under both estimators (least squares on logs agrees). "
              "Unlike rice and corn, separate El Niño and La Niña effects are not needed: they worsen "
              "the fit for both indices and both estimators, so one linear RONI term, as in v5, fits "
              "better. A season shift worsens the fit too, and lags 1–6 (v5 allows up to six for PF) "
              "change it by one or two points and leave the effect about the same. The recommended "
              "specification for VR and PF is "
              "therefore methodology v5 (Eq. 4) with smooth regional trends and one national effect.")
    doc.add_heading("5.2 Effects", level=2)
    table(doc, vrpf_effects(), [4.6, 2.6, 1.8, 2.4, 1.8],
          note="Table 10. Effect of a sustained +1 °C El Niño (RONI) on the calorie indices, % (Poisson; "
               "recommended VR / PF specification, RONI only; one national effect), and the El Niño and "
               "DMI effects of the variant with the DMI. The indices without root crops, without "
               "Cavendish and without banana are the checks of methodology v5 Section 3.2.",
          fmt={"El Niño (RONI +1), %": "{:.1f}", "t (RONI)": "{:.1f}", "With the DMI: El Niño, %": "{:.1f}",
               "DMI +1, %": "{:.1f}", "t (DMI)": "{:.1f}"})
    para(doc, f"PF: a sustained +1 °C El Niño lowers fruit production by about "
              f"{-vrpf_effect('pf', 'pf'):.1f}% (t = {vrpf_effect('pf', 'pf', col='t'):.1f}), a small "
              "but clear effect. It comes from bananas: without Cavendish it is about the same "
              f"({vrpf_effect('pf', 'pf_nocavendish'):.1f}%), so it is not driven by the export "
              "plantations alone, while without any banana the sign reverses "
              f"({vrpf_effect('pf', 'pf_nobanana'):+.1f}%, t = {vrpf_effect('pf', 'pf_nobanana', col='t'):.1f}): "
              "mango, pineapple and calamansi do not fall, consistent with dry spells helping mango "
              "flowering.")
    para(doc, f"VR: no El Niño loss can be detected. The effect is close to zero "
              f"({vrpf_effect('vr', 'vr'):+.1f}%, t = {vrpf_effect('vr', 'vr', col='t'):.1f}; without root "
              f"crops {vrpf_effect('vr', 'vr_noroot'):+.1f}%, t = {vrpf_effect('vr', 'vr_noroot', col='t'):.1f}), "
              "and small and positive with the DMI or close "
              "to zero with regional effects; plausibly because root crops, which dominate the index, "
              "tolerate drought and can be left in the ground until needed. With two episodes a small "
              "loss cannot be ruled out.")
    doc.add_heading("5.3 Validation", level=2)
    table(doc, vrpf_strict(), [1.4, 4.0, 2.8, 2.8, 2.4],
          note="Table 11. Stricter validation (as Table 2a; no change over time is chosen, since the "
               "data start in 2010): loss in % of the model's neutral path over the episode, observed / "
               "predicted by the model estimated without the episode and the four quarters after it; "
               "mean absolute error over the two episodes.",
          fmt={"Mean abs. error": "{:.1f}"})
    para(doc, "The recommended specification predicts both episodes better than methodology v5 as "
              f"written (RONI only: mean error {strict_mae('vr', 'vr', 'recommended, no DMI'):.1f} against "
              f"{strict_mae('vr', 'vr', 'v5 as written, no DMI'):.1f} points for VR, "
              f"{strict_mae('pf', 'pf', 'recommended, no DMI'):.1f} against "
              f"{strict_mae('pf', 'pf', 'v5 as written, no DMI'):.1f} for PF), but two episodes are a weak test, "
              "and the observed VR loss of 2023–24 depends on how the trend is extended to the end of "
              "the sample (about zero with the full-sample spline, about 3% when the trend is set on the "
              "years before the episode), probably because of the fall in Region V.")
    para(doc, "1997–98 against FAOSTAT. Methodology v5 asks to check, for 1997–98, outside the quarterly "
              "data, that the shocks add up to sensible annual losses, against FAOSTAT national annual "
              "production (official figures; calorie indices built with the same FNRI factors; "
              "calamansi and mung bean through the closest FAOSTAT items, bitter gourd left out). "
              "In 2010–2024, where both exist, FAOSTAT equals PSA's national production for every crop, "
              "mung bean and calamansi included (mango about 2% higher, as the item also covers guavas "
              "and mangosteens): FAOSTAT passes on PSA's figures (outputs/tables/faostat_vs_psa_2010_2024.csv).")
    table(doc, faostat_table(), [3.8, 2.4, 2.4, 2.4, 4.0],
          note="Table 11a. 1998 in FAOSTAT: deviation of the calorie index from its 1990–2005 log-linear "
               "trend (fitted without 1997–99) and change against the 1996–97 average, % (negative = a "
               "loss), with the standard deviation of the trend residuals; and the model's loss in 1998 "
               "from the replayed 1997–98 path, % of the year's production (RONI only; 90% bootstrap "
               "range). The model replays the path under today's crop mix, so the comparison is about "
               "orders of magnitude.",
          fmt={"1998 vs trend, %": "{:.1f}", "1998 vs 1996–97, %": "{:.1f}", "Trend residual SD, %": "{:.1f}"})
    para(doc, "The signs agree but the model understates 1998, as for rainfed rice and corn. Fruit "
              f"production fell about {-faostat('pf', 'obs_dev_1998_pct'):.0f}% below trend, three times "
              "the usual deviation, against a model loss of "
              f"{faostat('pf', 'model_loss_1998_pct'):.1f}%; as in the quarterly data the loss is bananas, "
              f"while fruit without banana was {faostat('pf_nobanana', 'obs_dev_1998_pct'):.0f}% above trend "
              "(a large mango harvest). For VR, the model finds no El Niño effect in 2010–2025, but in "
              f"1998 the index fell {-faostat('vr', 'obs_1998_vs_1996_97_pct'):.0f}% against 1996–97 "
              f"({-faostat('vr', 'obs_dev_1998_pct'):.0f}% below trend, within normal variation because 1997 "
              "was high), with cassava, sweet potato, potato and tomato all well down. So in a severe "
              "drought vegetables and root crops do lose, and the direct VR and PF shocks are best read "
              "as lower bounds for stress scenarios.")
    if (TAB / "shocks_pf_episode_totals.csv").exists() and (TAB / "shocks_vr_episode_totals.csv").exists():
        doc.add_heading("5.4 Shocks", level=2)
        para(doc, "Same paths and method as for rice and corn (section 2.4): the El Niño quarters of the "
                  "three strong episodes, replayed under today's conditions, and a unit "
                  "path; range from a block bootstrap over years (2010–2025), re-estimating the timing in "
                  "each draw.")
        table(doc, vrpf_totals(), [3.6, 3.2, 3.2, 3.2, 3.2],
              note="Table 12. VR and PF: total loss over the path and the four quarters after it, % of "
                   "one year's neutral production, central value (90% bootstrap range).")
        para(doc, f"PF: replayed today, the 1997–98, 2015–16 and 2023–24 episodes cost about "
                  f"{vrpf_total('pf', 'pf', '1997-98'):.1f}%, {vrpf_total('pf', 'pf', '2015-16'):.1f}% and "
                  f"{vrpf_total('pf', 'pf', '2023-24'):.1f}% of a year's fruit production (in kcal), "
                  f"with ranges of about {vrpf_total('pf', 'pf', '2023-24', 'p05'):.1f}–"
                  f"{vrpf_total('pf', 'pf', '1997-98', 'p95'):.1f}%. VR: "
                  f"{vrpf_total('vr', 'vr', '1997-98'):.1f}%, {vrpf_total('vr', 'vr', '2015-16'):.1f}% and "
                  f"{vrpf_total('vr', 'vr', '2023-24'):.1f}%, with ranges that include no loss. With the DMI "
                  "(Table 8c) the VR episodes show small losses that come entirely from the estimated DMI "
                  "effect (Table 8a), and the positive IOD of 2023 turns the PF loss of 2023–24 into a "
                  "small gain. For DEFINE-PH this means a small loss for fruits, coming from bananas, and "
                  "no El Niño shock for VR; the quarterly values are in Annex Tables A3 and A4.")
        figure(doc, FIG / "shocks_pf.png", 16.4,
               "Figure 4. Quarterly PF shock (share of the quarter's neutral production) with the 90% "
               "bootstrap range; dashed: PF without banana and without Cavendish; shaded: quarters of "
               "the path.")
    doc.add_heading("5.5 Limitations", level=2)
    bullets(doc, [
        ("Two episodes. ", "With data from 2010 only 2015–16 and 2023–24 are in the sample; a drought "
         "as severe as 1997–98 caused losses well beyond those the model gives (FAOSTAT, Table 11a), "
         "so for severe droughts the shocks are lower bounds."),
        ("One national effect. ", "Regional differences are not estimated; the national shock is the "
         "same in every region, which matters only if DEFINE-PH needs regional shocks."),
        ("The DMI ", "has opposite signs for VR (negative) and PF (positive), with its timing at the edge "
         "of the grid: more evidence that its effect in the production equation is not identified "
         "(section 4)."),
        ("Data. ", "Root crops in Region V fall by more than half between 2022 and 2025, and cassava "
         "expands strongly in Regions II, IX and XII until about 2015; the smooth trends follow these "
         "movements, but they make the observed losses at the end of the sample less certain."),
    ])

    if (DELIVERY / "food_shocks_episode_totals.csv").exists():
        doc.add_heading("6. Shocks for DEFINE-PH by food category", level=1)
        status(doc, "draft (tracker G6)")
        corn_k, vr_k, pf_k = delivery_kcal()
        tot_k = corn_k + vr_k + pf_k
        para(doc, "DEFINE-PH takes one production shock per food category, not per crop (methodology v5 "
                  "Sections 3.2 and 3.5). As agreed by the BSP and SOAS, there are four categories: rice, "
                  "corn, vegetables and fruits, and other food, which takes no El Niño production shock. "
                  "Rice and corn are the shocks of sections 2 and 3. VR and PF are combined into one "
                  "vegetables-and-fruits shock, each weighted by its calories, since DEFINE-PH measures food "
                  "in kcal; they are also delivered separately. The weights are the 2021–2023 calorie "
                  "production of each crop, quarter by quarter (the same base years as the VR and PF "
                  "indices): fruits provide about twice the calories of vegetables and root crops. The 90% "
                  "ranges are combined draw by draw from the bootstrap of each crop. All shocks use RONI "
                  "alone.")
        para(doc, "The current manual still has only two food types, rice and other food (Eq. D74). In case "
                  "the four categories are not in place at the delivery, v5 provides a fallback, delivered "
                  "and labelled as such: corn, VR and PF combined with calorie shares into one shock for all "
                  f"food except rice. Corn provides about {corn_k / tot_k * 100:.0f}% of these calories, so "
                  "the fallback mostly follows corn.")
        table(doc, delivery_totals(), [5.4, 3.6, 3.6, 3.6],
              note="Table 13. Total loss over the path and the four quarters after it, % of one year's "
                   "production, by food category, central value (90% range). The quarterly values, as "
                   "a share of the quarter's production and scaled for DEFINE-PH (Eq. 13b), are in "
                   "outputs/delivery/food_shocks_define_ph.csv.")
        bullets(doc, [
            ("The fallback assumes that the items not estimated lose as much. ", "It applies to all "
             "food except rice, including items such as coconut and fish, whose El Niño losses are not "
             "estimated here; this is an assumption (v5 Section 3.5). Its lower bound, with no loss on "
             "those items, is the fallback shock times the calorie share of corn, VR and PF in "
             "DEFINE-PH's other food, a number SOAS has (our crops: "
             f"{tot_k:,} billion kcal a year in 2021–2023). Neither is needed if DEFINE-PH has the four "
             "categories by the delivery."),
            ("Corn calories are provisional (fallback only). ", "Corn is measured in tonnes; for the "
             "fallback it is converted with FNRI food ID A001 (corn grits, white, 357 kcal per 100 g), "
             "the closest record found while the FNRI site was unavailable, to be confirmed. Since corn "
             "dominates the calories either way, a few percent on this factor barely changes the "
             "fallback."),
            ("Rice carries a sensitivity. ", "The file also contains the rice shock estimated without "
             "the Luzon typhoon quarters of late 2015 (section 2.6), an upper bound, labelled as such."),
        ])
        para(doc, "Two points for the DEFINE-PH runs, as v5 asks (Section 3.5), are stated in the note "
                  "accompanying the shocks:")
        bullets(doc, [
            ("Today's climate. ", "The shocks are the El Niño effect under today's climate: the trends "
             "in the estimation keep the slow warming since the 1950s out of the El Niño effect, and the "
             "shocks include no future warming. SOAS adds climate change to DEFINE-PH separately, so the "
             "two can be combined without double counting."),
            ("Check after the first run. ", "DEFINE-PH raises planned production after a shortfall "
             "(Eq. D76), while the shocks, estimated from data, already include the recovery seen after "
             "past El Niños, so realised production in the model may fall by less than the shock in later "
             "quarters. After the first model run, realised production is compared with the shock and "
             "any gap is reported to SOAS."),
        ])

    doc.add_heading("7. Two-stage approach", level=1)
    status(doc, "stage 1 ready (Van); stage 2 model comparison done; chain to come")
    para(doc, "Stage 1 (Van) is ready: regional monthly ERA5 weather predicted from RONI alone (16 "
              "November 2026), with out-of-sample predictions for every year from nested "
              "cross-validation (5-year July–June blocks held out, lags and modes chosen without them), "
              "and a RONI + DMI variant for stress scenarios. Out of sample it reproduces the 1997–98 "
              "drought (October–April rainfall about −84 mm/month predicted against −94 observed) and "
              "2023–24 (−45 against −45), and over-predicts the drying of 2015–16 (−71 against −40), "
              "because of the typhoon rain over Luzon described in section 2.6 (national "
              "cropland-weighted means, Van's figures). Stage 2 (weather → production) "
              "is estimated and compared out of sample (section 7.3); the chain is next. The cropland weights and the ERA5 cells counted as land were agreed with Van "
              "on 17 November 2026 (349 cells).")

    doc.add_heading("7.1 Crop calendars (growing windows for stage 2)", level=2)
    status(doc, "done (rice and corn)")
    para(doc, "Stage 2 relates production in a quarter to the weather in the months the crop harvested "
              "in that quarter was in the field. Those months come from RiceAtlas (Laborte et al. 2017, "
              "Harvard Dataverse), which gives planting and harvest dates for each rice season in 81 "
              "Philippine provinces, covering all 16 regions. For the Philippines the calendars come from the "
              "Department of Agriculture and the PSA, as v5 requires: the DA GMA-Rice Program (2009–2010), "
              "the PhilRice planting calendar of the top rice-producing provinces (2004–2008), the IRRI farm "
              "household survey (1994–1999) and the PSA's Philippine Food Security Information System (2014) "
              "(Laborte et al. 2017, Supplementary Table 1). For each province and harvest quarter, the "
              "season harvested in that quarter is taken, and its window runs from the planting peak to "
              "the harvest peak. Provinces are then combined by their PSA production in that quarter "
              "(2016–2025 mean), separately for irrigated and rainfed palay "
              "(scripts/build_rice_calendar.py, data/processed/rice_growing_window.csv).")
    table(doc, rice_calendar_table(), [2.6, 3.4, 4.6, 3.6],
          note="Table 14. Rice growing windows, total palay, all regions: months in which at least half of "
               "the quarter's harvest was in the field. 'Not covered' is the share of the quarter's PSA "
               "production in provinces where RiceAtlas lists no harvest in that quarter; for these the "
               "nearest season is used.",
          fmt={"Share of annual production (%)": "{:.0f}", "Not covered by the calendar (%)": "{:.0f}"})
    para(doc, "Limitations.", italic=True)
    bullets(doc, [
        "One fixed calendar (around 2010–2015): planting dates that shift from year to year, for example "
        "when the rains come late in an El Niño year, are not captured.",
        "No irrigated/rainfed split in the calendar: the two ecosystems share the windows and differ "
        "only in their production weights.",
        "About 18% of annual production is harvested in quarters that RiceAtlas does not cover (for example, "
        "Cagayan is listed with one crop, but PSA reports dry-season harvests). These are matched to the "
        "nearest season. Some provinces have a single date instead of a planting or harvest range: where "
        "the sources gave only a peak, RiceAtlas set a window of 15 days either side (Laborte et al. 2017).",
        "Batanes and Tawi-Tawi have no calendar (less than 0.1% of production); Davao Occidental "
        "takes the calendar of Davao del Sur, from which it was created in 2013.",
        "GGCMI's rice calendar for the Philippines (Jägermeyr et al. 2021) is taken from RiceAtlas, so it "
        "cannot serve as an independent check.",
    ])
    para(doc, "Corn. No subnational corn calendar comparable to RiceAtlas was found. The windows come from "
              "the GGCMI Phase 3 maize calendar (Jägermeyr et al. 2021, Zenodo), a 0.5° grid built for the "
              "Philippines from Dimou et al. (2018), MIRCA2000, SAGE and Iizumi et al. (2019). Each ERA5 "
              "cell takes the nearest GGCMI cell, and cells are combined with the cropland weights of "
              "stage 1 (scripts/build_corn_calendar.py, data/processed/corn_growing_window.csv). GGCMI has "
              "one season per cell, mostly the wet-season crop planted around May and harvested in "
              "July–September. Quarters with no GGCMI harvest take a standard cycle of the same length, "
              "harvested in the middle month of the quarter. The rainfed calendar is used; PSA does not "
              "split corn by water supply.")
    table(doc, corn_calendar_table(), [2.6, 3.4, 4.6, 3.6],
          note="Table 15. Corn growing windows, all regions (rainfed calendar): months in which at least "
               "half of the quarter's harvest was in the field, and the share of the quarter's PSA "
               "production whose window comes from GGCMI rather than the standard cycle.",
          fmt={"Share of annual production (%)": "{:.0f}", "Window from GGCMI (%)": "{:.0f}"})
    para(doc, "The corn windows are rougher than the rice windows: GGCMI covers about a third of annual "
              "production (mostly the Q3 harvest), and the dry-season crop harvested in Q1 and Q2 and the "
              "late crop of Q4 rely on the standard cycle. Like RiceAtlas, the calendar is fixed and does "
              "not distinguish white and yellow corn.")
    para(doc, "v5 sets the windows from PSA and Department of Agriculture calendars. Neither publishes "
              "regional corn planting or harvest windows (searched 23 Nov 2026): PSA OpenSTAT gives corn "
              "production by quarter, semester, region and province only, and the monthly distribution "
              "collected by the Corn Production Survey is not published. DA has scattered regional "
              "statements but no calendar, and none was found for the National Corn Program. These "
              "statements support the standard cycle. The DA Region 2 corn techno guide gives wet-season "
              "planting from early April to June, dry-season planting from October to December and "
              "maturity at 95–120 days after planting. PSA's monthly corn monitoring tables pair each "
              "quarter's plantings with the next quarter's harvests. FAO GIEWS reports main-season maize "
              "planting from April (to August in some areas) and secondary-season planting finished by "
              "December. Press releases from DA Region 1 (three cropping seasons) and Region 10 (mid-May "
              "wet-season and October–November dry-season plantings) agree, but they are not calendars. "
              "Using GGCMI is therefore a change from v5 to note (for rice, RiceAtlas is built from PSA "
              "and DA calendars).")
    para(doc, "Sources for the corn calendar check (accessed 23 Nov 2026).", italic=True)
    bullets(doc, [
        "DA Region 2, Corn Techno Guide (planting windows p. 3, maturity p. 30): "
        "https://cagayanvalley.da.gov.ph/wp-content/uploads/2018/02/corn_techno_guide_final.pdf",
        "DA Region 1, cropping seasons news item: https://ilocos.da.gov.ph/?p=1434",
        "DA Region 10, seed-trial news: https://cagayandeoro.da.gov.ph/?p=75933, "
        "https://cagayandeoro.da.gov.ph/?p=76413, https://cagayandeoro.da.gov.ph/?p=65543",
        "PSA OpenSTAT corn production (2E4EVCP0): "
        "https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__2E__CS/0012E4EVCP0.px/",
        "PSA Corn Production Survey technical notes (PSA MIMAROPA): "
        "https://rssomimaropa.psa.gov.ph/node/1684057173",
        "PSA monthly corn monitoring tables, Table 7 (April–June 2020 plantings, July–September 2020 "
        "harvests): https://psa.gov.ph/sites/default/files/csd/2022-12/9%2520Statistical%2520Tables.pdf; "
        "system described at https://psa.gov.ph/content/psa-clears-conduct-monthly-palay-and-corn-"
        "situation-reporting-system-mpcsrs",
        "FAO GIEWS Country Brief, Philippines (secondary-season line from the 29 January 2026 brief). The "
        "live pages are overwritten with each brief; archive: "
        "https://cb.apps.fao.org/country/PHL/pdf_archive/PHL_Archive.pdf",
    ])

    doc.add_heading("7.2 Check of Van's scenario simulations", level=2)
    status(doc, "done (a check, not a result): ready for the chain (version f6ddf65, 25 November)")
    para(doc, "Van ran stage 1 on the four scenario paths of the direct approach (1997–98, 2015–16, "
              "2023–24 and the unit path, RONI and RONI + DMI models; dev_Van commit af5e28f, re-run on 24 "
              "November as 30cc20c and on 25 November with the complete hourly record as f6ddf65). For each "
              "path and each of 73 draws there is a scenario run and a neutral run "
              "(RONI = 0) that use the same "
              "historical residuals, so their difference is the El Niño effect (v5 Section 3.5). Before "
              "chaining them with stage 2, scripts/check_stage1_scenarios.py checks that the files are what "
              "the chain needs (outputs/stage1_scenarios_check.md).")
    table(doc, stage1_scen_checks(), [11.0, 3.0],
          note="Table 16. Checks of Van's scenario simulations, version f6ddf65 (4 paths × 2 models; check 7 "
               "for irrigated, rainfed and corn windows).")
    bullets(doc, [
        ("Consistent: ", "the RONI paths are ours month by month; the scenario and neutral runs of each "
         "draw use the same historical month in every region; the neutral weather depends only on the "
         "calendar month (today's climate) and is the same in every path; Van's effects table matches the "
         "draws; and the effects fade to zero within six months of the last El Niño month."),
        ("Leading months (fixed): ", "the first version (af5e28f) dropped the six zero months before each "
         "path. The growing windows reach up to eight months back, so the first one or two harvest "
         "quarters of each path (for 1997–98: 1997Q2 and 1997Q3 for rice) could not be built. Van's re-run "
         "(30cc20c) keeps them, with the observed months before the table set to zero, so the scenario "
         "equals the neutral run there in every draw (checked), and every harvest quarter from the first "
         "El Niño month on is complete."),
        ("Residual years (fixed): ", "the 24 November re-run drew only 51 historical years, skipping the "
         "years without hourly data (1987–2009). The 25 November re-run, with the complete hourly record, "
         "draws all 73 years again, and adds the daily variables of v5 Table 2 (with extreme degree-days "
         "and hot days at 30, 32 and 35 °C)."),
    ])
    table(doc, stage1_scen_effects(), [2.0, 4.4, 4.4, 4.0],
          note="Table 17. Largest national effect of each path on the weather (scenario − neutral, RONI model, "
               "palay-weighted), mean over draws with the 10th–90th percentiles. Temperature and soil "
               "moisture have the same effect in every draw because their transforms are linear.")
    para(doc, "The sizes are plausible: in 1997–98 rainfall falls by about 130 mm in October 1997 and "
              "root-zone soil moisture is lowest in April 1998, at the dry-season harvest. Two features "
              "to raise with Van, as questions rather than errors: rainfall rises by about 50 mm in July "
              "of the onset year (in line with the known wetter early El Niño months), and the "
              "temperature effect drops to zero in June (in the 25 November version also in July) and reappears after. The second comes from "
              "choosing the lag of each target month separately: the June model uses only the RONI of "
              "the same and the previous month, which are zero once the episode has ended.")
    figure(doc, FIG / "stage1_scenarios_effects.png", 16.0,
           "Figure 5. Van's stage 1 on the scenario paths: national effect on the weather by month "
           "(scenario − neutral, palay-weighted); band: 10th–90th percentiles of the draws (RONI model).")
    table(doc, stage1_scen_range(), [2.4, 3.1, 3.1, 3.1, 3.1],
          note="Table 18. Simulated region-months outside the range observed in 1987–2025 for that region "
               "and calendar month (% of region-months, all draws, RONI model; in brackets, the share below "
               "the range).")
    para(doc, "This is a first look at v5's reliability flag. Even the neutral run, which is today's "
              "climate with historical residuals, lies outside the observed range in about 8–10% of "
              "region-months for temperature and 15–24% for soil moisture, almost all above it. For temperature this is "
              "today's warmer climate. For soil moisture it comes mostly from residuals of the 1950s, when "
              "ERA5-Land soil moisture varies more. El Niño adds about 6 points for temperature and little "
              "for rainfall and soil moisture. The flag in the chain will therefore be (i) applied to the "
              "window features, not to single months, (ii) one-sided (hotter or drier than observed, the "
              "side where losses are extrapolated), and (iii) reported for the scenario net of the neutral "
              "run. These are proposed clarifications of v5 Section 3.4.")

    doc.add_heading("7.3 Stage 2: weather to production", level=2)
    status(doc, "model comparison done with monthly and daily weather (diagnostic); chain with stage 1 next")
    para(doc, "Stage 2 relates production to the weather in the months the crop was in the field "
              "(v5 Section 3.4). The weather is Van's observed ERA5-Land variables (the same variables, "
              "units, cells and cropland weights as stage 1), averaged over each crop's growing window "
              "(section 7.1), weighted by the share of the quarter's harvest in the field each month "
              "(scripts/build_stage2_features.py, data/processed/stage2_features.csv). There are 30 "
              "features: the window means of the 11 monthly variables and of the 12 daily variables of v5 "
              "Table 2 (mean daily maximum and minimum temperature, afternoon VPD, extreme degree-days and "
              "hot days above 30, 32 and 35 °C, dry days, longest dry spell, heavy-rain days; Van, 25 "
              "November), and seven extremes: the hottest month (mean and daily maximum), the month with "
              "the highest VPD, the driest month for rainfall, root-zone soil moisture and SPEI-3, and the "
              "longest dry spell of the window. Degree-days above 35 °C are almost always zero on regional "
              "averages (71% of region-months), which is why the 30 and 32 °C thresholds were added.")
    para(doc, "All models are estimated like the direct approach (Poisson, production in levels, region "
              "× quarter effects, smooth regional trends, the typhoon, flood and geophysical controls, and "
              "the Negros corn break), with weather in place of RONI (v5 Eq. 11). Twelve models are "
              "compared (scripts/estimate_stage2.py):")
    bullets(doc, [
        ("Regression, v5 Eq. 11: ", "weather window means with hinges: the loss grows faster beyond a "
         "threshold (above it for heat, VPD and dry spells, below it for rainfall and soil moisture). "
         "Thresholds are chosen by fit among the 5th, 10th, …, 95th percentiles of the data. Versions: "
         "the four monthly means (temperature, VPD, rainfall, soil moisture) with and without hinges; "
         "parsimonious pairs of a heat and a water measure (mean temperature, daily maximum temperature "
         "or degree-days above 30 °C, each with soil moisture; dry spell with daily maximum temperature); "
         "and hinges on the monthly extremes."),
        ("Gradient boosting: ", "on the four monthly means, on the 16 monthly features, and on all 30 "
         "features. Production is constrained to fall with heat, VPD, degree-days, hot days and dry "
         "spells and to rise with soil moisture and SPEI. Region, season, trend and control terms enter "
         "as in the regression: the two parts are fitted in turn (backfitting), so the boosting explains "
         "only what the weather adds. Settings are fixed in advance and not tuned."),
        ("Today's response: ", "the weather effects changed from 2000 (tested below), so two models let "
         "them change: the regression with temperature and soil moisture, with every weather term "
         "shifting from 2000, and the boosting on all 30 features with a post-2000 indicator among the "
         "features. For the shocks, both use the post-2000 response."),
    ])
    para(doc, "Out-of-sample test (v5: the model that predicts better on years left out is kept). Each "
              "model is re-estimated without the held-out quarters, choosing its thresholds and trends "
              "again: first for each 5-year block (1987–91, …, 2022–25), then for each strong episode "
              "(1997Q2–1998Q4, 2015Q2–2016Q4, 2023Q2–2024Q4). Skill is the share of the prediction error "
              "(Poisson deviance) of the model without weather that the weather removes, on the held-out "
              "quarters.")
    sk_tab = stage2_skill()
    table(doc, sk_tab, [4.6, 1.9, 1.9, 1.9, 1.9, 1.9, 1.9],
          note="Table 19. Out-of-sample skill of stage 2 (% of the no-weather model's deviance removed on "
               "held-out quarters; 5-year blocks and the three episodes). Higher is better; negative = "
               "worse than no weather.",
          fmt={c: "{:.1f}" for c in sk_tab.columns[1:]})
    sk = sk_tab.set_index("Model")
    ep = stage2_episodes().set_index(["Series", "Episode"])
    won = stage2_folds_won()
    H, G = STAGE2_MODELS["hinge_sm_t_post2000"], STAGE2_MODELS["gbm_daily_post2000"]
    n_post = int(won.get("hinge_sm_t_post2000", 0) + won.get("gbm_daily_post2000", 0))
    para(doc, f"Two results stand out. First, the models whose response changes from 2000 predict best: "
              f"they are the best model in {n_post} of the 33 folds and have the highest skill in both "
              f"tests for irrigated and rainfed rice and in the 5-year blocks for corn. For irrigated rice "
              f"the regression is best ({sk.loc[H, 'irrigated, 5-yr']:.1f}% in the blocks, "
              f"{sk.loc[H, 'irrigated, episodes']:.1f}% in the episodes); for rainfed rice and corn the "
              f"boosting ({sk.loc[G, 'rainfed, 5-yr']:.1f}% and {sk.loc[G, 'rainfed, episodes']:.1f}% for "
              f"rainfed rice; {sk.loc[G, 'corn, 5-yr']:.1f}% and {sk.loc[G, 'corn, episodes']:.1f}% for corn, "
              f"where the linear regression does slightly better on the episodes). Second, the daily "
              f"variables help the boosting (for irrigated rice, block skill "
              f"{sk.loc[STAGE2_MODELS['gbm_all'], 'irrigated, 5-yr']:.1f}% with the monthly features and "
              f"{sk.loc[STAGE2_MODELS['gbm_daily'], 'irrigated, 5-yr']:.1f}% with the daily ones) but change "
              f"the regressions little: one heat and one water measure capture most of what the regression "
              f"can use, whichever the measure.")
    table(doc, stage2_episodes(), [2.0, 1.8, 2.0, 2.6, 2.6, 2.6, 2.6],
          note="Table 20. Episodes held out: national production over the episode window, observed and "
               "predicted from the observed weather, % against the model without weather (estimated without "
               "the episode).",
          fmt={c: "{:.1f}" for c in ["Observed"] + [STAGE2_MODELS[m] for m in STAGE2_SHOWN]})
    figure(doc, FIG / "stage2_episodes.png", 16.0,
           "Figure 6. Stage 2 out of sample: national production by quarter in each held-out episode, "
           "observed and predicted from the observed weather (% against the model without weather).")
    para(doc, "What the episodes show.", italic=True)
    bullets(doc, [
        ("1997–98: ", f"only the models whose response changes from 2000 reproduce the losses of both rice "
         f"ecosystems. Irrigated rice: {ep.loc[('irrigated', '1997-98'), H]:.0f}% (regression) and "
         f"{ep.loc[('irrigated', '1997-98'), G]:.0f}% (boosting) predicted against "
         f"{ep.loc[('irrigated', '1997-98'), 'Observed']:.0f}% observed, where the models with a fixed "
         f"response predict {ep.loc[('irrigated', '1997-98'), STAGE2_MODELS['hinge_sm_t']]:.0f}% to "
         f"{ep.loc[('irrigated', '1997-98'), STAGE2_MODELS['gbm_all']]:.0f}%. Rainfed rice: "
         f"{ep.loc[('rainfed', '1997-98'), H]:.0f}% and {ep.loc[('rainfed', '1997-98'), G]:.0f}% against "
         f"{ep.loc[('rainfed', '1997-98'), 'Observed']:.0f}%. This corrects the reading of the monthly-only "
         f"comparison (23 November): the irrigated loss of 1997–98 is not mainly a channel that local "
         f"weather misses, such as irrigation water, but a stronger response to the same weather before "
         f"2000. The pre-2000 response is estimated here without 1997–98 itself."),
        ("2023–24: ", f"the models with a fixed response predict a loss that did not happen (irrigated "
         f"{ep.loc[('irrigated', '2023-24'), STAGE2_MODELS['hinge_sm_t']]:.0f}% against "
         f"{ep.loc[('irrigated', '2023-24'), 'Observed']:.0f}%); the post-2000 regression comes closer "
         f"({ep.loc[('irrigated', '2023-24'), H]:.0f}%). For rainfed rice too the post-2000 regression "
         f"comes closest ({ep.loc[('rainfed', '2023-24'), H]:.0f}% against "
         f"{ep.loc[('rainfed', '2023-24'), 'Observed']:.0f}%), the boosting less so "
         f"({ep.loc[('rainfed', '2023-24'), G]:.0f}%)."),
        ("2015–16: ", "the national losses of irrigated rice are predicted well and those of rainfed rice "
         "and corn are under-predicted; the quarterly pattern is missed (the 2015Q3 and 2016Q1 dips)."),
    ])
    para(doc, "The regression. With all four monthly means, the separate effects of temperature, VPD and "
              "soil moisture are poorly identified, because they move together, and some hinges get the "
              "wrong sign. A pair of one heat and one water measure predicts as well. With temperature and "
              "soil moisture, and the response changing from 2000, today's extra loss on dry soil is "
              "positive for all three series: smaller than before 2000 for irrigated rice and corn, larger "
              "for rainfed rice (Table 21). The separate before and after terms should not be over-read: "
              "corn's heat hinge has the wrong sign before 2000, and the rainfed dry-soil threshold sits at "
              "the edge of the grid, where the hinge covers almost all seasons and works with the linear "
              "term. What the chain uses is today's response as a whole, which is what the out-of-sample "
              "test supports.")
    table(doc, stage2_hinge(), [1.8, 5.4, 2.6, 2.2, 2.0, 1.8],
          note="Table 21. Hinge terms of the regression with temperature and soil moisture whose response "
               "changes from 2000, full sample: extra loss beyond the threshold, on top of the linear "
               "effect, before 2000 and today; t of the change from 2000 (Driscoll–Kraay, conditional on "
               "the thresholds). 'Edge': the threshold is at the 5th or 95th percentile of the data.",
          fmt={"Before 2000 (%)": "{:.1f}", "Today (%)": "{:.1f}", "t of the change": "{:.1f}"})
    figure(doc, FIG / "stage2_response.png", 16.0,
           "Figure 7. Response of production to each window mean (5th–95th percentile of the data), "
           "relative to the median, full sample; models changing from 2000 at today's response. The "
           "boosting curves are partial dependences (other features as observed), so they are flatter "
           "where other features carry the same information.")
    br = stage2_break()
    para(doc, "Did the weather effects change from 2000? As in the direct approach (section 2.3), the "
              "test adds post-2000 shifts of all weather terms of the regression with temperature and soil "
              "moisture. They are jointly significant for all three series (Wald, Driscoll–Kraay: "
              + "; ".join(f"{s_} χ²({br[s_][1]}) = {br[s_][0]:.0f}, p = {br[s_][2]:.3f}" for s_ in
                          ("irrigated", "rainfed", "corn"))
              + "), and the models with the change predict better out of sample (above). The response of "
              "production to the same weather has changed, as in the direct rice result; the shocks use "
              "today's response.")
    para(doc, f"Choice for the chain (v5's rule, the model that predicts better out of sample): for irrigated "
              f"rice the regression with temperature and soil moisture, changing from 2000; for rainfed rice "
              f"and corn the boosting on all 30 features, changing from 2000. The chain runs both models for "
              f"every series, so the other one is reported as a check. Boosting cannot extrapolate: beyond "
              f"the hottest or driest window in the data its response stays flat, so the reliability flag "
              f"(section 7.2) matters most for it, and the regression shows what extending the thresholds "
              f"would give.")
    para(doc, "Limitations.", italic=True)
    bullets(doc, [
        "The 2000 change is a step, and the post-2000 response is estimated from 26 years; whether the "
        "response is still changing is not tested here (for the direct rice model, a gradual decline fitted "
        "worse than the step).",
        "The boosting has 30 features and the regression 2, so the comparison is also between feature sets.",
        "The thresholds are chosen on the data and their uncertainty is not in the standard errors. Several "
        "dry-soil thresholds still sit on the edge of the grid (Table 21): losses accelerate only in the "
        "driest or wettest 5% of seasons, or the hinge is close to linear.",
        "VR and PF not yet included (data from 2010, longer fixed windows).",
        "ERA5-Land soil moisture ignores irrigation (v5 Section 3.4): for irrigated rice it measures the "
        "drought before irrigation, not the water in the field.",
    ])
    para(doc, "Next: chain stage 2 with Van's simulations draw by draw (shock of v5 Eq. 12, aggregated as "
              "in Eqs. 13a–13b), with the reliability flag, and compare with the direct shocks by the rule "
              "of v5 Section 3.5.")

    doc.add_heading("Annex", level=1)
    table(doc, quarterly_palay(), [2.0, 2.0, 3.0, 3.4, 3.6],
          note="Table A1. Quarterly palay shock for the episode paths: share of the quarter's neutral "
               "production lost (v5 Eq. 13a), 90% bootstrap range, and the value scaled for DEFINE-PH "
               "(Eq. 13b).",
          fmt={"Shock (% of quarter)": "{:.1f}", "Scaled for DEFINE-PH (%)": "{:.1f}"})
    table(doc, quarterly_corn(), [2.0, 2.0, 3.0, 3.4, 3.6],
          note="Table A2. Quarterly corn shock for the episode paths (as Table A1). Losses in the "
               "dry-season harvest are partly offset by gains in the following quarter, as harvests "
               "shift later in the year.",
          fmt={"Shock (% of quarter)": "{:.1f}", "Scaled for DEFINE-PH (%)": "{:.1f}"})
    if (TAB / "shocks_pf.csv").exists() and (TAB / "shocks_vr.csv").exists():
        table(doc, quarterly_vrpf("pf"), [2.0, 2.0, 3.0, 3.4, 3.6],
              note="Table A3. Quarterly PF shock for the episode paths (as Table A1).",
              fmt={"Shock (% of quarter)": "{:.1f}", "Scaled for DEFINE-PH (%)": "{:.1f}"})
        table(doc, quarterly_vrpf("vr"), [2.0, 2.0, 3.0, 3.4, 3.6],
              note="Table A4. Quarterly VR shock for the episode paths (as Table A1; negative = a gain).",
              fmt={"Shock (% of quarter)": "{:.1f}", "Scaled for DEFINE-PH (%)": "{:.1f}"})
    para(doc, "Code and results: GitHub repository en_shock, branch ginevra-agriculture "
              "(scripts/estimate_direct.py, scripts/compare_direct_v5_rice.py, "
              "scripts/validate_strict.py, scripts/shocks_direct.py; tables in outputs/tables).",
         size=9, color=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
