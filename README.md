# Housing cost burden map
March 2026

An interactive map of ZIP codes across 258 U.S. metropolitan areas (core-based statistical areas, or CBSAs). For each ZIP code, the map shows whether the annual cost of owning a typical 3-bedroom or 4-bedroom home is more than **31% of the area's median family income for nonelderly married-couple households**. It assumes a 6% 30-year fixed-rate mortgage, a 10% down payment and other assumptions from the Atlanta Fed's [Home Ownership Affordability Monitor](https://www.atlantafed.org/research-and-data/data/home-ownership-affordability-monitor).

- **Red:** housing cost is over 31% of family income, in bands of 31–35%, 35–40%, 40–45%, 45–50% and 50% and up (darker is higher).
- **Green:** housing cost is 31% of family income or less, in bands of under 15%, 15–20%, 20–24%, 24–28% and 28–31% (darker is lower).
- **Gray:** the ZIP code is inside a covered CBSA, but data isn't available. This is usually because there's no Zillow home value for it.

## View it

The page loads its data with `fetch`. Opening `index.html` straight from disk won't work.

- **GitHub Pages:** Settings → Pages → Deploy from branch → `main` / root.
- **Locally:** run `python -m http.server` in this folder, then open http://localhost:8000.

## Methodology

Home values and costs come from `zip_housing_costs_march_2026 taxes fixed.xlsx` (the "ZIP housing costs" tab). For California and Florida, property taxes instead use new-buyer effective rates, as described below. The same explanation is on the map under **Methodology & sources**.

**Ratio** = annual ownership cost at a 6% 30-year fixed mortgage rate ÷ the median family income for nonelderly married couples in that CBSA. ZIP codes over 31% are red, and those at 31% or less are green. (31% is FHA's standard guideline for the maximum housing payment as a share of income, also known as the front-end ratio.)

- **Home value:** the Zillow Home Value Index (ZHVI) for 3-bedroom and 4-bedroom homes, March 2026. This is the mid-tier series (33rd to 67th price percentiles), smoothed and seasonally adjusted. See the [ZHVI methodology](https://www.zillow.com/research/methodology-neural-zhvi-32128/) and [Zillow data](https://www.zillow.com/research/data/). The 4-bedroom values come from `zhvi 4 bedroom by zip march 2026.xlsx` and use the same cost assumptions and income.
- **Income:** metro area median family income for married-couple families where neither spouse is elderly (both aged 18–64), from the 2024 [American Community Survey](https://www.census.gov/programs-surveys/acs) 5-year sample, using [IPUMS USA](https://usa.ipums.org/usa/) microdata. Income is total family income in 2024 dollars, for metro areas approximated from Public Use Microdata Areas (PUMAs). Incomes are updated to March 2026 using FRED's [Average Hourly Earnings of Production and Nonsupervisory Employees, Total Private](https://fred.stlouisfed.org/series/AHETPI) (AHETPI): the 2024 income is multiplied by the March 2026 value divided by the 2024 annual average. (That's an increase of about 6.6% across the board.)
- **Housing costs:** following the Atlanta Fed's [Home Ownership Affordability Monitor](https://www.atlantafed.org/research-and-data/data/home-ownership-affordability-monitor) (HOAM; see its [explainer](https://www.atlantafed.org/research-and-data/data/home-ownership-affordability-monitor/explainer)), costs add up:
  - principal and interest on a 30-year fixed-rate loan for 90% of the ZHVI, assuming 10% down,
  - property tax at the county's rate, as described below,
  - homeowners insurance at the CBSA's effective rate, based on HOAM's March 2026 monthly insurance amount,
  - private mortgage insurance (PMI) at 0.558% of the loan per year.

  The down payment, closing costs, maintenance, utilities and HOA fees are excluded.
- **Property tax:** the county's effective rate from the Tax Foundation's [Property Taxes by State and County, 2026](https://taxfoundation.org/data/all/state/property-taxes-by-state-county/) (based on 2024 5-year ACS estimates), multiplied by each ZIP code's ZHVI. California and Florida reassess homes at sale, so their property taxes are adjusted using the county files in `sources/`:
  - **California:** the county's average tax rate (the 1% Prop 13 rate plus voter-approved debt) from the Board of Equalization's [2024-25 Annual Report](https://www.boe.ca.gov/legdiv/2024-2025/pub306.pdf) × (ZHVI − $7,000 homeowners' exemption).
  - **Florida:** each county's school and non-school tax rates, calculated as taxes levied ÷ taxable value from the Department of Revenue's [2025 County Property Tax Overviews](https://floridarevenue.com/property/Documents/2025_County_Profiles.pdf). Tax = school mills/1000 × (0.85 × ZHVI − $25,000) + non-school mills/1000 × (0.85 × ZHVI − $50,000). The 0.85 reflects Florida's assessment at sale price less 15% for costs of sale; the dollar amounts are homestead exemptions.
- **County matching:** ZIP codes are matched to counties using [GeoNames](https://www.geonames.org/) postal-code counties, with Connecticut planning regions via a crosswalk. For California and Florida, they use HUD's [USPS ZIP–county crosswalk](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) (June 2026); each ZIP is assigned to the county with most of its residential addresses.
- **Mortgage rate:** 6% is the average 30-year FHA rate for March 2026, rounded to the nearest 0.1%, based on the Optimal Blue [30-Year Fixed Rate FHA Mortgage Index](https://fred.stlouisfed.org/series/OBMMIFHA30YF) for that month.

**Caveats:**
- Property tax rates are county averages, and insurance rates are CBSA averages. Actual rates vary by town, school district and individual property.
- Special assessments aren't included, such as California's Mello-Roos and parcel taxes or Florida's flat fees for fire, trash and stormwater.
- HOA fees aren't included.
- The ZHVI is an estimate of a typical home value, not of recent sale prices in the area.
- ZIP codes are assigned to CBSAs using HUD's December 2024 [USPS ZIP–CBSA crosswalk](https://www.huduser.gov/portal/datasets/usps_crosswalk.html). Each ZIP code goes to the CBSA that holds most of its residential addresses. Connecticut ZIPs were assigned separately, using the crosswalk provided in the cost file.

## Data sources

- ZIP boundaries: U.S. Census Bureau, 2020 cartographic ZCTAs (`cb_2020_us_zcta520_500k`)
- CBSA boundaries: U.S. Census Bureau, 2025 cartographic CBSAs (`cb_2025_us_cbsa_500k`)
- Basemap: [OpenFreeMap](https://openfreemap.org) (Positron style) © OpenMapTiles © OpenStreetMap contributors, rendered with [MapLibre GL JS](https://maplibre.org)

## Replication data

The `replication/` folder has every number behind the map as plain CSV files. `sources/` has the California and Florida county tax inputs.

- **`zip_costs.csv`:** one row per ZIP code in the cost file (16,731), with its inputs and results for both home sizes.
  - `county_fips`, `county_source`: the county used for property tax and how it was matched.
  - `property_tax_method`: Tax Foundation county rate, CA new buyer or FL new buyer.
  - `tax_foundation_rate`, `insurance_rate`: annual rates as a share of home value.
  - `income_2026_03`: the CBSA's wage-adjusted median income. Blank for CBSAs without income data, which aren't on the map.
  - `zhvi_3br` / `zhvi_4br`, then for each size: `principal_interest`, `pmi`, `property_tax`, `insurance`, `annual_cost` (all annual dollars) and `cost_to_income`.
- **`cbsa_income.csv`:** each CBSA's 2024 median income from IPUMS (rounded to $100), the AHETPI wage factor (32.12 ÷ 30.12) and the March 2026 income.

No raw source files are included: no IPUMS microdata, and no Zillow, HUD, HOAM or Tax Foundation downloads. The CSVs hold only the values used here, with credit to each source:

- **Zillow:** ZHVI values are Zillow Group data, free for public use with attribution.
- **IPUMS USA:** the incomes are medians we calculated from IPUMS USA microdata; no microdata is redistributed. Citation: Steven Ruggles, Sarah Flood, Matthew Sobek, Daniel Backman, Grace Cooper, Julia A. Rivera Drew, Stephanie Richards, Renae Rodgers, Jonathan Schroeder, and Kari C.W. Williams. IPUMS USA: Version 16.0 [dataset]. Minneapolis, MN: IPUMS, 2025. https://doi.org/10.18128/D010.V16.0
- **Tax Foundation:** county rates from Property Taxes by State and County, 2026, licensed [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (noncommercial use with attribution).
- **GeoNames:** postal-code counties, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Atlanta Fed HOAM:** insurance rates are derived from HOAM's March 2026 insurance and home price figures.
- **Public government data:** HUD USPS crosswalks, Census boundaries, California BOE, Florida DOR, and BLS wages via FRED. The Optimal Blue rate index is cited, not redistributed.

## Rebuilding the data

```
pip install pandas geopandas openpyxl
python scripts/build_data.py "<folder containing ZIP_CBSA_122024.xlsx, ZIP-COUNTY_062026.xlsx, zip_housing_costs_march_2026 taxes fixed.xlsx and zhvi 4 bedroom by zip march 2026.xlsx>"
```

The first run downloads the Census boundary files into `.cache/`, then writes `data/zips.json`, `data/cbsa.json` and the `replication/` CSVs.

- **Shape detail:** ZIP shapes are simplified by at most 0.0003° (~30 m) and CBSA shapes by at most 0.001°. On a 2,000-ZIP sample, the median edge error against the Census file is about 25 m and the largest is about 43 m.
- **Storage:** to keep the files small, shapes are stored as integer coordinate offsets (1e-4°), and `index.html` converts them back when the page loads.

## Updates

- **October 30, 2026:** added the 4-bedroom view.
- **October 29, 2026:** property tax changed from CBSA-wide HOAM rates to county rates (Tax Foundation), with new-buyer estimates for California and Florida.
