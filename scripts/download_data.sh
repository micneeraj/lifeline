#!/usr/bin/env bash
# Re-downloads every raw source into data/raw, then: python scripts/build_data.py
set -e
mkdir -p data/raw && cd data/raw
curl -sSL -o eo_nc.csv https://www.irs.gov/pub/irs-soi/eo_nc.csv
curl -sSL -o pub78.zip https://apps.irs.gov/pub/epostcard/data-download-pub78.zip && unzip -o -q pub78.zip
curl -sSL -o revoked.zip https://apps.irs.gov/pub/epostcard/data-download-revocation.zip && unzip -o -q revoked.zip
curl -sSL -o sdn.csv https://www.treasury.gov/ofac/downloads/sdn.csv
curl -sSL -o fema_helene_nc.json 'https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=disasterNumber%20eq%204827&$top=1000'
curl -sSL -o iceye_helene_wnc.geojson 'https://services5.arcgis.com/LsNj2OtQESAjac8r/arcgis/rest/services/ICEYE_FSD_2227_flood_extent_Helene_Juvare/FeatureServer/0/query?where=1%3D1&geometry=-84.4,34.9,-80.9,36.6&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&outFields=*&f=geojson'
for f in 2023_Gaz_place_national 2023_Gaz_zcta_national 2023_Gaz_counties_national; do
  curl -sSL -o $f.zip "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/$f.zip" && unzip -o -q $f.zip
done
