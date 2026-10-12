# El Niño Shocks on Macroeconomic Models

This GitHub explores the application of machine learning models to predict agricultural, labor, and hydropower shocks from El Niño and the Indian Ocean Dipole (IOD).

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-in%20development-orange)

## Motivation
 
El Niño-Southern Oscillation (ENSO) is one of the strongest drivers of year-to-year climate variability, and the Indian Ocean Dipole (IOD) is a second major mode that often co-occurs with it and can amplify or offset its regional effects. Their effects propagate through the real economy: crop yields fall or rise, heat and rainfall anomalies change how much people can safely work, and shifts in precipitation alter reservoir inflows and hydropower output. Macroeconomic models typically treat these as exogenous noise. This project asks whether machine learning can turn ENSO and IOD signals into usable, forecastable shock estimates that feed into macroeconomic analysis.

## Research Questions
 
1. How well can ML models predict sector-level shocks (agriculture, labor, hydropower) from El Niño indicators?
2. How do ENSO and IOD interact? Do joint events produce larger or different shocks than either mode alone?
3. How do ML-based shock estimates compare with traditional econometric baselines (e.g., distributed-lag regression approaches)?
4. Can predicted shocks be integrated into macroeconomic models to improve scenario analysis?

## Data Sources
 
- **ENSO indices:** NOAA Climate Prediction Center (Niño 3.4, ONI/RONI)
- **IOD index:** NOAA Physical Sciences Laboratory (Dipole Mode Index, DMI)
- **Climate reanalysis:** ECMWF ERA5 (temperature, precipitation, humidity)
- **Agriculture:** OpenSTAT
- **Labor:** TBD
- **Hydropower:** TBD

## Getting Started
 
```bash
# Clone the repository
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
