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

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TAB, FIG = ROOT / "outputs/tables", ROOT / "outputs/figures"
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
    s = pd.read_csv(TAB / "direct_v5_rice_spec_comparison.csv")
    s = s[s.model == "ppml"].copy()
    s["effect"] = s.get("B_RP").fillna(s.get("B_R"))
    s["t_eff"] = s.get("t_RP").fillna(s.get("t_R"))
    labels = {"base": "v5 as written (Eq. 4)", "split": "El Niño and La Niña separate",
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
    a = pd.read_csv(TAB / "direct_v5_rice_validation.csv")
    b = pd.read_csv(TAB / "direct_v5_rice_validation_candidate.csv")
    v = pd.concat([a[a.spec == "base"], b[b.spec.isin(["candidate", "candidate_break2000"])]])
    names = {"base": "v5 as written", "candidate": "split + spline + season",
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


def episode_totals():
    t = pd.read_csv(TAB / "shocks_rice_episode_totals.csv")
    t["path"] = t.path.str.replace("unit RONI +1 (4 quarters from Q3)", "unit path: RONI +1 for 4 quarters", regex=False)
    w = t.pivot_table(index="path", columns="crop", values="total_loss_pct_of_annual")
    r = t[t.crop == "palay"].set_index("path")
    out = pd.DataFrame({"Path (replayed under today's conditions)": w.index,
                        "Palay": w["palay"].values,
                        "90% range": [f"{r.loc[k, 'p05']:.1f} to {r.loc[k, 'p95']:.1f}" for k in w.index],
                        "Irrigated": w["irrigated"].values, "Rainfed": w["rainfed"].values,
                        "Draws with a loss (palay, %)": [r.loc[k, "share_of_draws_with_loss_pct"] for k in w.index]})
    return out


def quarterly_palay():
    s = pd.read_csv(TAB / "shocks_rice.csv")
    s = s[(s.crop == "palay") & ~s.path.str.startswith("unit")]
    s = s.assign(S=s.S * 100, lo=s.S_p05 * 100, hi=s.S_p95 * 100, SD=s.S_D * 100)
    return pd.DataFrame({"Path": s.path, "Quarter": s.scenario_q,
                         "Shock (% of quarter)": s.S, "90% range": [f"{a:.1f} to {b:.1f}" for a, b in zip(s.lo, s.hi)],
                         "Scaled for DEFINE-PH (%)": s.SD})


# ---------------------------------------------------------------- document
def decline():
    """Step (2000) versus gradual linear change of the El Nino effect, Poisson."""
    s = pd.read_csv(TAB / "direct_v5_rice_spec_comparison_decline.csv")
    s = s[s.model == "ppml"].set_index(["ecosystem", "spec"])
    v = pd.read_csv(TAB / "direct_v5_rice_validation_decline.csv")
    mae = v.groupby(["ecosystem", "spec"]).error_pts.apply(lambda x: x.abs().mean())
    return {(e, sp): {"ic": s.loc[(e, sp), "ic_minus_base"], "today": s.loc[(e, sp), "B_RP_today"],
                      "y1995": s.loc[(e, sp), "B_RP_1995"], "mae": mae[(e, sp)]}
            for e in ("irrigated", "rainfed") for sp in ("step_2000", "gradual_linear")}


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
        "mae_base_irr": val[("irrigated", "v5 as written")],
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
              "Rice is complete up to the shocks; corn, vegetables and root crops (VR), perennial "
              "fruits (PF) and the two-stage approach follow. All results are provisional.")
    bullets(doc, [
        ("Methodology v5 as written does not reproduce the past El Niño episodes for rice. ",
         "Estimated without each strong episode in turn, it predicts a small loss in 1997–98, "
         "when production fell sharply, and a loss in 2015–16, when there was almost none."),
        ("Three changes, supported by the data, fix most of this: ",
         "separate effects for El Niño and La Niña, smooth regional trends, and an El Niño effect "
         "that is smaller from 2000 on. The specification with these changes is the one I "
         "recommend; it differs from methodology v5 and the changes are proposed for "
         "discussion (section 2.6)."),
        ("El Niño effect today: ", f"a sustained +1 °C RONI lowers dry-season rice harvests by about "
         f"{k['irr_now']:.0f}% (irrigated) and {k['rf_now']:.0f}% (rainfed); before 2000 the effects were "
         f"about {k['irr_before']:.0f}% and {k['rf_before']:.0f}%."),
        ("Shocks: ", f"replayed under today's conditions, the 1997–98 and 2015–16 episodes cost about "
         f"{k['s97']:.1f}% and {k['s15']:.1f}% of a year's palay production and 2023–24 about "
         f"{k['s23']:.1f}%, with wide ranges, mainly because the effect on irrigated rice is uncertain."),
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
              "1991 separately). They measure exposure, not damage, and are set to “no event” in the "
              "shocks, so that the El Niño shock can be combined with the CAT damage ratios.")

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
          note="Table 1. Fit gain = fall in the information criterion against v5 as written "
               "(deviance + k ln n; positive = better after charging for extra parameters). El Niño "
               "effect = production-weighted national total effect of a sustained +1 °C RONI, log "
               "points (El Niño part when El Niño and La Niña are separate; dry-season harvest when "
               "effects differ by season).",
          fmt={"Fit gain, irrigated": "{:,.0f}", "Fit gain, rainfed": "{:,.0f}",
               "El Niño effect, irrigated": "{:.3f}", "El Niño effect, rainfed": "{:.3f}"})
    para(doc, "Two choices matter. Smooth regional trends give by far the largest improvement in fit, "
              "without changing the El Niño effect much. Separate El Niño and La Niña effects "
              "roughly double the El Niño effect: in these data La Niña does not raise rice "
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
              "line keeps falling and puts today's effect lower (irrigated "
              f"{dc[('irrigated', 'gradual_linear')]['today']:+.2f} against "
              f"{dc[('irrigated', 'step_2000')]['today']:+.2f} log points; rainfed "
              f"{dc[('rainfed', 'gradual_linear')]['today']:+.2f} against "
              f"{dc[('rainfed', 'step_2000')]['today']:+.2f}). The step is kept; the gradual decline is "
              "a sensitivity that gives a lower bound.")
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
              "are the El Niño quarters (RONI ≥ 0.5) of the three strong episodes, with their DMI, "
              "replayed under today's conditions.")
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

    doc.add_heading("2.5 Limitations", level=2)
    bullets(doc, [
        ("The change in 2000 rests on three strong episodes. ", "It is a clear pattern, not proof. A "
         "gradual (linear) decline of the effect, tested as an alternative, fits worse and predicts "
         "the episodes less well (section 2.3); it would put today's effect lower, so it gives a "
         "lower bound."),
        ("Rainfed 1997–98 is understated, ", "which supports the two-stage approach for severe droughts."),
        ("The effect on irrigated palay is uncertain: ", "its range includes zero, which widens the "
         "palay range."),
        ("The estimators differ on one choice: ", "least squares on logs does not prefer separate El "
         "Niño and La Niña effects, Poisson does."),
        ("The DMI timing is poorly determined ", "(the timing parameter often lies at the edge of the grid)."),
    ])

    doc.add_heading("2.6 Proposed changes to methodology v5", level=2)
    status(doc, "proposed, for discussion")
    bullets(doc, [
        ("Eq. 4: ", "separate total effects for El Niño (RONI+) and La Niña (RONI−), same timing."),
        ("Eq. 4: ", "smooth regional trends instead of one linear trend per region."),
        ("New: ", "an El Niño effect that changes over time (a step in 2000), with the shocks computed "
         "for today's conditions."),
        ("Section 3.6: ", "define the observed loss used in the validation (against the model's "
         "neutral path, as in section 2.2)."),
        ("Section 3.5: ", "state that, with lags from one quarter, the first quarter of a path has "
         "no shock."),
        ("Additions: ", "the rule for the Eight Cluster Areas, the rule for PSA measurement breaks, "
         "and the exact definitions of the controls."),
    ])

    doc.add_heading("3. Corn", level=1)
    status(doc, "to come")
    para(doc, "Same approach as rice, on total, white and yellow corn, with typhoon and flood exposure "
              "weighted by corn production. Negros Occidental corn falls sharply from 2023Q3 (area "
              "harvested about 68,000–70,000 ha a year in 2018–2022, 27,000 ha in 2025), in a way not "
              "seen in the rest of Region VI or the country; it is treated as a measurement break, "
              "with a level dummy for Region VI corn whose start will be chosen by the data, and a "
              "check without Region VI corn from 2023Q3.")

    doc.add_heading("4. Vegetables and root crops (VR) and perennial fruits (PF)", level=1)
    status(doc, "to come")
    para(doc, "Calorie-weighted indices from 2010 (FNRI factors; banana varieties updated 11 November "
              "2026). With only two strong episodes since 2010, pooled effects and up to six lags for "
              "PF will be tested.")

    doc.add_heading("5. Two-stage approach", level=1)
    status(doc, "to come")
    para(doc, "Regional monthly weather from ERA5 is prepared; cropland weights and the treatment of "
              "provinces without an ERA5 land cell are being agreed with Van.")

    doc.add_heading("Annex", level=1)
    table(doc, quarterly_palay(), [2.0, 2.0, 3.0, 3.4, 3.6],
          note="Table A1. Quarterly palay shock for the episode paths: share of the quarter's neutral "
               "production lost (v5 Eq. 13a), 90% bootstrap range, and the value scaled for DEFINE-PH "
               "(Eq. 13b).",
          fmt={"Shock (% of quarter)": "{:.1f}", "Scaled for DEFINE-PH (%)": "{:.1f}"})
    para(doc, "Code and results: GitHub repository en_shock, branch ginevra-agriculture "
              "(scripts/estimate_direct_rice.py, scripts/compare_direct_v5_rice.py, "
              "scripts/shocks_rice.py; tables in outputs/tables).", size=9, color=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
