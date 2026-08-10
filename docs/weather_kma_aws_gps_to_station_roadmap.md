# GPS to nearest KMA AWS direct observation roadmap

## Current production behavior

- Current temperature and humidity: nearest KMA ASOS direct observation when available.
- Secondary fallback: KMA grid observation.
- Final fallback and forecast: existing Open-Meteo location provider.
- The response records source, station identifier, station name, distance, and observation time.

## AWS direct-observation completion requirements

1. Obtain approval for KMA `Aws1miInfoService/getAws1miList`; the public service is approval-controlled.
2. Obtain an approved AWS station catalog with station IDs, coordinates, and validity periods.
3. Add nearest-station selection using GPS coordinates and query the latest one-minute AWS record.
4. Record AWS ID, station name, distance, observed time, raw temperature, humidity, and provider response version with each applied value.
5. Keep ASOS, KMA grid, and Open-Meteo only as explicitly labelled fallback sources; never present a fallback as an AWS observation.
6. Validate against the KMA/Naver displayed observation for multiple sites before changing the default from ASOS to AWS.

## Record-use safeguard

External weather observations are reference evidence. The temperature field used for a legally required site record must retain the worker's on-site measurement and measurement time when the applicable rule requires on-site measurement.
