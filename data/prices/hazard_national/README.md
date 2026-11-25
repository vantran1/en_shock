# National typhoon and flood exposure, by quarter (for the food price equation, Eq. 3)

Built by Ginevra on `ginevra-agriculture` (commit 381d43c, 24 Nov 2026) with
`scripts/build_national_hazard_controls.py`; copied here on 25 Nov 2026 from `origin/ginevra-agriculture` at 8b898ad.
The tables are byte-for-byte copies (the figure has the same pixels). To refresh them after she updates the branch:

```bash
git fetch origin ginevra-agriculture
for f in data/processed/hazard_national_quarter.csv data/processed/hazard_national_weights.csv \
         outputs/tables/hazard_national_checks.csv outputs/figures/hazard_national_quarter.png; do
  git show origin/ginevra-agriculture:$f > data/prices/hazard_national/$(basename $f)
done
```

| File | Content |
|---|---|
| `hazard_national_quarter.csv` | weighting × quarter, 1987Q1–2025Q4 (156 quarters × 3 weightings) |
| `hazard_national_weights.csv` | the fixed weights of the 82 provinces in each version |
| `hazard_national_checks.csv` | Ginevra's checks: palay version = regional controls × palay shares, calorie-factor sensitivity, correlation between versions |
| `hazard_national_quarter.png` | the series, by version |

**Columns.** As the regional controls of the direct (agricultural) model, each with its previous quarter (`_lag1`):
- `ty_share_ts`, `ty_share_ty`, `ty_share_sty`: weighted share of the country with winds of at least tropical-storm,
  typhoon and super-typhoon strength in the quarter (PAGASA categories, 10-min sustained; cumulative, so ts ≥ ty ≥ sty);
  from IBTrACS with a Rankine wind field;
- `flood_share`: weighted share of the country in provinces hit by at least one EM-DAT flood event.

**Weightings** (`weighting` column), fixed so that a control does not move with what it explains:
- `palay`: provinces' shares of national palay production, 2016–2025. For the rice equation.
- `food`: provinces' shares of food calories from palay, corn, VR and PF, 2016–2025 (about 52 % palay, 34 % corn,
  13 % VR + PF; corn includes feed corn). For the food equation. The palay and corn calorie factors are provisional
  (`data/TO_VERIFY.md` on her branch); ±20 % on the palay factor leaves the series correlated at 0.9995 or more.
- `population`: WorldPop 2020 shares, including Metro Manila (12 % of the weight), which the agricultural controls
  leave out. A check for the food equation; it differs from the other two mainly for the strongest typhoons that hit
  Metro Manila (e.g. 1995Q4).

**Keep in mind.**
- EM-DAT records many more floods from about 2004, mostly because reporting improved: the mean `flood_share` is
  about 0.06 in 1987–2003 and 0.27 in 2004–2025, and the share of quarters with any flood rises from 49 % to 78 %.
- The series end in 2025Q4, so with the PSA CPI (from January 1994) the estimation sample is 1994Q1–2025Q4.
- In the shocks the controls are set to "no event" (zero) in both the El Niño and the neutral run.
