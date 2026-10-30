"""Build the map's data files (data/zips.json, data/cbsa.json).

Usage:
    python scripts/build_data.py "<folder with ZIP_CBSA_122024.xlsx, ZIP-COUNTY_062026.xlsx,
                                   zip_housing_costs_march_2026 taxes fixed.xlsx and
                                   zhvi 4 bedroom by zip march 2026.xlsx>"

Census boundary files are downloaded into .cache/ on first run. California and Florida property
taxes are replaced with new-buyer estimates from sources/*_new_buyer_property_tax_rates.csv.
"""
import sys, json, pathlib, urllib.request, zipfile
import numpy as np, pandas as pd, geopandas as gpd, shapely

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache'
OUT = ROOT / 'data'
SRC = pathlib.Path(sys.argv[1])
COSTS = SRC / 'zip_housing_costs_march_2026 taxes fixed.xlsx'
CROSSWALK = SRC / 'ZIP_CBSA_122024.xlsx'
ZIP_COUNTY = SRC / 'ZIP-COUNTY_062026.xlsx'
FOUR_BED = SRC / 'zhvi 4 bedroom by zip march 2026.xlsx'
RATES = ROOT / 'sources'
REPL = ROOT / 'replication'
WAGE_FACTOR = 32.12 / 30.12   # FRED AHETPI: March 2026 / 2024 annual average

CENSUS = {
    'zcta': 'https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip',
    'cbsa': 'https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_cbsa_500k.zip',
}
NON_STATES = {'PR', 'VI', 'GU', 'AS', 'MP', 'FM', 'MH', 'PW', 'AA', 'AE', 'AP'}
LIMIT = 0.31
ZIP_TOLERANCE = 0.0003   # degrees; no edge moves more than ~30 m
CBSA_TOLERANCE = 0.001


def census(name):
    d = CACHE / name
    if not d.exists():
        d.mkdir(parents=True)
        z = d / 'src.zip'
        urllib.request.urlretrieve(CENSUS[name], z)
        zipfile.ZipFile(z).extractall(d)
    return gpd.read_file(next(d.glob('*.shp'))).to_crs(4326)


# housing cost table (second tab): header on row 7, data from row 8
x = pd.read_excel(COSTS, sheet_name=1, header=None, dtype=str)
t = x.iloc[7:, :24].copy(); t.columns = x.iloc[6, :24].tolist()
t = t[t['ZIP'].notna()]
for c in ['ZHVI_2026_03', 'Annual cost 6.00%', 'Married median family income', 'Housing / income 6.00%',
          'Annual property tax', 'County property tax rate', 'Insurance rate', 'Annual P&I 6.00%', 'Annual PMI']:
    t[c] = pd.to_numeric(t[c])
v = t['ZHVI_2026_03']
assert np.allclose(t['Annual property tax'], t['County property tax rate'] * v)

# California and Florida reassess at sale, so a buyer pays more than the county's average
# effective rate. Swap in new-buyer property tax, with each ZIP in the HUD county holding most
# of its residential addresses.
hud = pd.read_excel(ZIP_COUNTY, dtype=str)
for c in ('res_ratio', 'tot_ratio'):
    hud[c] = pd.to_numeric(hud[c])
county = hud.sort_values(['res_ratio', 'tot_ratio'], ascending=False).drop_duplicates('zip').set_index('zip')['geoid']
ca = pd.read_csv(RATES / 'ca_new_buyer_property_tax_rates.csv', dtype={'county_fips': str}).set_index('county_fips')
fl = pd.read_csv(RATES / 'fl_new_buyer_property_tax_rates.csv', dtype={'county_fips': str}).set_index('county_fips')
fips = t['ZIP'].map(county)
is_ca = (t['State'] == 'CA') & fips.isin(ca.index)
is_fl = (t['State'] == 'FL') & fips.isin(fl.index)
print('new-buyer tax applied: CA', int(is_ca.sum()), 'FL', int(is_fl.sum()),
      '| CA/FL ZIPs without a county match', int(((t['State'].isin(['CA', 'FL'])) & ~(is_ca | is_fl)).sum()))


def property_tax(v):
    # CA: Prop 13 base + voter-approved debt on the purchase price, less the $7,000 homeowners' exemption
    ca_tax = fips.map(ca['boe_avg_tax_rate_2024_25']) * (v - 7000).clip(lower=0)
    # FL: just value ~85% of price; $25,000 homestead exemption on all levies, $50,000 on non-school levies
    jv = 0.85 * v
    fl_tax = (fips.map(fl['school_millage']) / 1000 * (jv - 25000).clip(lower=0)
              + fips.map(fl['nonschool_millage']) / 1000 * (jv - 50000).clip(lower=0))
    return (t['County property tax rate'] * v).where(~is_ca, ca_tax).where(~is_fl, fl_tax)


def write_replication():
    """Per-ZIP inputs and outputs, plus CBSA incomes, as plain CSVs (derived values only, no raw source files)."""
    REPL.mkdir(exist_ok=True)
    ct = pd.read_excel(COSTS, sheet_name='County taxes', header=None, dtype=str)
    geonames = ct.iloc[7:, :2].dropna().set_index(0)[1]
    rows = pd.DataFrame({
        'zip': t['ZIP'], 'cbsa': t['CBSA'], 'city': t['City'].str.title(), 'state': t['State'],
        'county_fips': fips.where(is_ca | is_fl, t['ZIP'].map(geonames)),
        'county_source': np.where(is_ca | is_fl, 'HUD ZIP-county crosswalk', 'GeoNames'),
        'property_tax_method': np.select([is_ca, is_fl], ['CA new buyer', 'FL new buyer'], 'Tax Foundation county rate'),
        'tax_foundation_rate': t['County property tax rate'], 'insurance_rate': t['Insurance rate'].round(6),
        'income_2026_03': t['Married median family income'].round(0).astype('Int64'),
    })
    for s, val in (('3br', v), ('4br', t['v4'])):
        rows[f'zhvi_{s}'] = val.round(0).astype('Int64')
        rows[f'principal_interest_{s}'] = (t['Annual P&I 6.00%'] / v * val).round(2)
        rows[f'pmi_{s}'] = (t['Annual PMI'] / v * val).round(2)
        rows[f'property_tax_{s}'] = property_tax(val).round(2)
        rows[f'insurance_{s}'] = (t['Insurance rate'] * val).round(2)
        rows[f'annual_cost_{s}'] = annual_cost(val).round(2)
        rows[f'cost_to_income_{s}'] = (annual_cost(val) / t['Married median family income']).round(6)
    rows.to_csv(REPL / 'zip_costs.csv', index=False)

    inc = t.dropna(subset=['Married median family income']).drop_duplicates('CBSA')
    adj = inc['Married median family income']
    base = (adj / WAGE_FACTOR).round(-2)
    assert np.allclose(base * WAGE_FACTOR, adj)
    pd.DataFrame({'cbsa': inc['CBSA'], 'metro': inc['HOAM CBSA'], 'income_2024': base.astype(int),
                  'wage_factor': round(WAGE_FACTOR, 6), 'income_2026_03': adj.round(2)}
                 ).sort_values('cbsa').to_csv(REPL / 'cbsa_income.csv', index=False)
    return f'{len(rows)} ZIPs, {len(inc)} CBSAs'


# P&I, PMI and insurance are fixed shares of the home value, so the same per-ZIP rates price any home
rate = (t['Annual P&I 6.00%'] + t['Annual PMI']) / v + t['Insurance rate']
annual_cost = lambda v: rate * v + property_tax(v)
plain = ~(is_ca | is_fl)
assert np.allclose(annual_cost(v)[plain], t.loc[plain, 'Annual cost 6.00%'], equal_nan=True)
t['Annual cost 6.00%'] = annual_cost(v)
t['Housing / income 6.00%'] = t['Annual cost 6.00%'] / t['Married median family income']

# 4-bedroom ZHVI, priced with the same rates and compared against the same income
four = pd.read_excel(FOUR_BED, dtype={'RegionName': str})
t['v4'] = t['ZIP'].map(four.set_index(four['RegionName'].str.zfill(5))['March 2026 home value'])
t['cost4'] = annual_cost(t['v4'])
t['r4'] = t['cost4'] / t['Married median family income']
print('replication files:', write_replication())
in_file = t.set_index('ZIP')   # every ZIP in the file, including ones without a ratio
t = t[t['Housing / income 6.00%'].notna()]

# only CBSAs that have cost data
cb = census('cbsa')
cb = cb[cb['GEOID'].isin(set(t['CBSA']))]

# ZIPs with data by code; no-data ZCTAs whose interior point falls in a covered CBSA
z = census('zcta')[['ZCTA5CE20', 'geometry']].rename(columns={'ZCTA5CE20': 'zip'})
zd = z.merge(t, left_on='zip', right_on='ZIP')
rest = z[~z['zip'].isin(t['ZIP'])]
pts = gpd.GeoDataFrame(rest[['zip']], geometry=rest.geometry.representative_point(), crs=4326)
hit = gpd.sjoin(pts, cb[['GEOID', 'geometry']], predicate='within').drop_duplicates('zip')
zg = rest.merge(hit[['zip', 'GEOID']], on='zip')
xw = pd.read_excel(CROSSWALK, dtype=str).drop_duplicates('ZIP').set_index('ZIP')
# ZIPs that are in the file but have no ratio keep the file's CBSA and say why
listed = zg['zip'].isin(in_file.index)
zg.loc[listed, 'GEOID'] = zg.loc[listed, 'zip'].map(in_file['CBSA'])
zg = zg[zg['GEOID'].isin(set(cb['GEOID']))]
listed = zg['zip'].isin(in_file.index)
why = np.where(~listed, '', 'In the file with a home value, but no March 2026 insurance input for its HOAM area ('
               + zg['zip'].map(in_file['HOAM CBSA']).fillna('').str.replace(r' \(.*\)$', '', regex=True) + ').')

zd = gpd.GeoDataFrame({
    'zip': zd['zip'], 'cbsa': zd['CBSA'], 'city': zd['City'].str.title(), 'st': zd['State'],
    'k': np.where(zd['Housing / income 6.00%'] > LIMIT, 'over', 'under'),
    'v': zd['ZHVI_2026_03'].round(0), 'cost': zd['Annual cost 6.00%'].round(0),
    'inc': zd['Married median family income'].round(0), 'r': zd['Housing / income 6.00%'].round(6),
    'k4': np.where(zd['r4'].isna(), 'nodata', np.where(zd['r4'] > LIMIT, 'over', 'under')),
    'v4': zd['v4'].round(0), 'cost4': zd['cost4'].round(0), 'r4': zd['r4'].round(6),
}, geometry=zd.geometry, crs=4326)
zg = gpd.GeoDataFrame({
    'zip': zg['zip'], 'cbsa': zg['GEOID'], 'k': 'nodata', 'k4': 'nodata', 'why': why,
    'city': zg['zip'].map(in_file['City']).fillna(zg['zip'].map(xw['USPS_ZIP_PREF_CITY'])).fillna('').str.title(),
    'st': zg['zip'].map(in_file['State']).fillna(zg['zip'].map(xw['USPS_ZIP_PREF_STATE'])).fillna(''),
}, geometry=zg.geometry, crs=4326)
zips = pd.concat([zd, zg], ignore_index=True)
zips = zips[~zips['st'].isin(NON_STATES)].reset_index(drop=True)
zips.loc[zips['why'] == '', 'why'] = np.nan

zips['geometry'] = zips.geometry.simplify(ZIP_TOLERANCE, preserve_topology=True).make_valid()
cb['geometry'] = cb.geometry.simplify(CBSA_TOLERANCE, preserve_topology=True).make_valid()

# keep the western Aleutians next to the rest of Alaska
unwrap = lambda g: shapely.transform(g, lambda c: np.where(c[:, :1] > 0, c - [360, 0], c))
ak = zips['st'] == 'AK'; zips.loc[ak, 'geometry'] = zips.loc[ak, 'geometry'].apply(unwrap)
ak = cb['NAME'].str.endswith(', AK'); cb.loc[ak, 'geometry'] = cb.loc[ak, 'geometry'].apply(unwrap)

lp = zips.geometry.representative_point()
zips['lng'], zips['lat'] = lp.x.round(4), lp.y.round(4)

stats = []
for s in ('', '4'):   # 3-bedroom, 4-bedroom
    d = zips[zips['k' + s] != 'nodata']
    agg = d.groupby('cbsa')['r' + s].agg(n='size', over=lambda v: int((v > LIMIT).sum()), med='median').add_suffix(s)
    cb = cb.merge(agg, left_on='GEOID', right_index=True, how='left')
    cb['nodata' + s] = cb['GEOID'].map(zips[zips['k' + s] == 'nodata'].groupby('cbsa').size()).fillna(0).astype(int)
    cb['med' + s] = cb['med' + s].round(4)
    stats += [c + s for c in ('n', 'over', 'med', 'nodata')]
lp = cb.geometry.representative_point()
cb['lng'], cb['lat'] = lp.x.round(4), lp.y.round(4)
cb = cb[['GEOID', 'NAME', 'lng', 'lat', *stats, 'geometry']].rename(columns={'GEOID': 'id', 'NAME': 'name'})
zips['cname'] = zips['cbsa'].map(dict(zip(cb['id'], cb['name'])))


def ring(r):
    # 1e-4 degree integers, delta-encoded: [x0, y0, dx1, dy1, ...]
    q = np.round(np.asarray(r)[:, :2] * 1e4).astype(np.int64)
    q[1:] = np.diff(q, axis=0)
    return q.ravel().tolist()


def polygons(geo):
    if geo.geom_type == 'Polygon':
        return [geo]
    if geo.geom_type == 'MultiPolygon':
        return list(geo.geoms)
    return [p for g in getattr(geo, 'geoms', []) for p in polygons(g)]


def pack(g, path):
    rows = []
    for rec, geo in zip(g.drop(columns='geometry').to_dict('records'), g.geometry):
        rec = {k: v for k, v in rec.items() if not (isinstance(v, float) and np.isnan(v))}
        rec['g'] = [[ring(p.exterior.coords)] + [ring(i.coords) for i in p.interiors] for p in polygons(geo)]
        rows.append(rec)
    path.write_text(json.dumps(rows, separators=(',', ':')), encoding='utf-8')
    return path.stat().st_size / 1e6


OUT.mkdir(exist_ok=True)
print('zips.json', round(pack(zips, OUT / 'zips.json'), 1), 'MB',
      '3-bed', zips['k'].value_counts().to_dict(), '4-bed', zips['k4'].value_counts().to_dict())
print('cbsa.json', round(pack(cb, OUT / 'cbsa.json'), 1), 'MB', len(cb), 'CBSAs')
