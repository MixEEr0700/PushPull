# P0 durable write — pomiary syntetyczne

CPU ×4, Chromium 154, 390×844, offline. Każda komórka: mediana / p95 / max w ms; n=24, 3 profile × 8 zapisów. To nie Pixel 9.

| Profil | Przed: klik → strict complete | Po: klik → strict complete | Zmiana mediany |
|---|---:|---:|---:|
| legacy 4, raw 0 MiB | 84.7 / 110.9 / 118.9 | 83.7 / 95.9 / 96.5 | -1.2% |
| V2 4, raw 0 MiB | 1253.8 / 1367.0 / 1375.0 | 1125.4 / 1225.2 / 1230.6 | -10.2% |
| V2 4, raw 4 MiB ASCII | 1771.5 / 1918.2 / 1943.7 | 1559.2 / 1679.7 / 1698.8 | -12.0% |
| legacy 400, raw 4 MiB ASCII | 1913.2 / 2228.5 / 2229.6 | 1817.0 / 2071.2 / 2145.2 | -5.0% |
| V2 40, raw 4 MiB ASCII | 10003.6 / 10667.6 / 10962.0 | 9171.4 / 9891.9 / 11765.6 | -8.3% |
| V2 4, raw 16 MiB escaped Unicode | 6214.6 / 6462.1 / 6462.8 | 4320.6 / 4672.2 / 4829.9 | -30.5% |

Legacy jest kontrolą: nie ma kompletnego modelu V2; różnicy nie przypisujemy optymalizacji raw. Mała próba i współdzielony host ograniczają wnioski.

| Profil | Pierwsza reakcja przed → po (mediana/p95) | Pełny UI przed → po (mediana/p95) |
|---|---:|---:|
| legacy 4, raw 0 MiB | 30.0/31.2 → 30.1/31.5 | 137.6/178.6 → 131.1/147.4 |
| V2 4, raw 0 MiB | 29.2/30.8 → 29.9/31.0 | 1316.8/1428.5 → 1180.0/1296.6 |
| V2 4, raw 4 MiB ASCII | 29.7/30.6 → 29.4/31.0 | 1847.1/1979.6 → 1621.3/1762.8 |
| legacy 400, raw 4 MiB ASCII | 29.8/30.7 → 29.6/31.0 | 1981.7/2279.0 → 1896.2/2147.3 |
| V2 40, raw 4 MiB ASCII | 29.7/30.9 → 29.4/30.5 | 10094.5/10730.2 → 9238.1/10106.0 |
| V2 4, raw 16 MiB escaped Unicode | 29.3/30.5 → 29.2/31.6 | 6295.9/6513.9 → 4378.3/4745.4 |

## v2-archive4: średnie rozłączne etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 27.5 | 28.0 |
| source-encode-hash | 52.3 | 52.2 |
| archives | 0.2 | 0.2 |
| legacy-projection | 934.0 | 948.4 |
| transaction-open | 0.6 | 0.5 |
| cas-read | 54.1 | 53.6 |
| cas-compare | 124.1 | 19.1 |
| source-write | 33.9 | 35.1 |
| source-readback | 61.1 | 56.4 |
| source-verify | 122.8 | 116.2 |
| model-write-readback-compare | 252.1 | 135.4 |
| root-verified-complete | 24.8 | 20.9 |
| post-complete | 0.0 | 0.0 |

## v2-large: średnie rozłączne etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 199.6 | 201.7 |
| source-encode-hash | 436.5 | 450.9 |
| archives | 0.1 | 0.2 |
| legacy-projection | 5445.5 | 5579.9 |
| transaction-open | 0.8 | 0.8 |
| cas-read | 248.5 | 261.1 |
| cas-compare | 589.2 | 122.9 |
| source-write | 246.1 | 234.0 |
| source-readback | 292.2 | 302.2 |
| source-verify | 953.5 | 964.3 |
| model-write-readback-compare | 1058.8 | 586.1 |
| root-verified-complete | 150.3 | 152.8 |
| post-complete | 0.0 | 0.0 |

## v2-archive16: średnie rozłączne etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 29.4 | 28.0 |
| source-encode-hash | 56.1 | 54.7 |
| archives | 0.2 | 0.3 |
| legacy-projection | 3113.4 | 3131.8 |
| transaction-open | 0.8 | 3.1 |
| cas-read | 179.5 | 202.3 |
| cas-compare | 967.6 | 28.1 |
| source-write | 41.5 | 33.9 |
| source-readback | 173.0 | 182.4 |
| source-verify | 128.2 | 123.8 |
| model-write-readback-compare | 1387.3 | 440.3 |
| root-verified-complete | 37.4 | 22.6 |
| post-complete | 0.0 | 0.0 |

## Osobna próbka diagnostyczna, V2 4 + raw ASCII 4 MiB

Profiler CPU i interceptory dodają narzut; n=1, nie wchodzą do powyższych median/p95. Czasy inkluzywne — nie sumować. SHA mierzy await API, nie sam czas CPU algorytmu.

| Span | Przed (ms) | Po (ms) |
|---|---:|---:|
| app.js:bindingFor | 0.2 | 0.1 |
| native.JSON.stringify.bulk | 344.7 | 99.0 |
| model/training-model.mjs:validateModel | 268.0 | 268.5 |
| model/training-model.mjs:validateSessionSnapshot | 319.6 | 319.9 |
| model/performance.mjs:validatePerformance | 236.8 | 245.7 |
| indexeddb.js:catalogFor | 1.2 | 1.9 |
| storage.js:validate | 52.6 | 57.6 |
| indexeddb.js:validateCatalog | 45.9 | 53.0 |
| indexeddb.js:encode | 38.6 | 45.3 |
| native.TextEncoder | 101.9 | 107.4 |
| native.SHA256 | 23.8 | 27.5 |
| native.JSON.parse.bulk | 39.3 | 45.5 |
| model/backup-json.mjs:parseJson | 167.8 | 181.1 |
| model/legacy-backup.mjs:validateV1 | 5.6 | 4.4 |
| model/legacy-backup.mjs:validateV2 | 8.2 | 6.7 |
| model/legacy-backup.mjs:readLegacyBackup | 202.8 | 215.7 |
| model/training-model.mjs:createModel | 15.4 | 11.3 |
| model/journal.mjs:project | 297.7 | 302.4 |
| model/legacy-model.mjs:payload | 409.8 | 415.2 |
| model/backup.mjs:validatePayload | 173.4 | 181.3 |
| model/backup.mjs:digest | 268.5 | 259.7 |
| model/backup.mjs:createBackup | 498.0 | 500.8 |
| model/legacy-model.mjs:createLegacyModel | 908.1 | 916.1 |
| indexeddb.js:decode | 18.5 | 18.9 |
| indexeddb.js:verifyRows | 74.5 | 81.9 |
| indexeddb.js:save | 1743.5 | 1533.6 |
| app.js:persist | 1763.6 | 1553.6 |
| innerHTML | 4.5 | 3.8 |
| app.js:render | 8.4 | 7.1 |

[Surowe próbki, rozmiary, hashe i CPU self](durable-write-measurements.json). Warianty tymczasowe opisano osobno w [projekcie](../DURABLE_WRITE_P0_PROJECT.md).
