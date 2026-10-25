# Etap B — natywny strict complete

Syntetyczne bazy V2; Chromium/Linux, CPU ×4, 390×844, offline. 24 zapisy/wersja/scenariusz: 3 niezależne procesy × 8 zapisów. Historia przed rozpoczęciem jednej bieżącej sesji. To nie pomiar Androida.

| Profil | Przed mediana/p95/max (ms) | Po mediana/p95/max (ms) | Mediana zmiana |
|---|---:|---:|---:|
| V2 0, raw 0 | 353.9/414.4/419.8 | 266.6/295.5/299.6 | -24.7% |
| V2 4, raw 0 | 1093.7/1191.9/1271.1 | 635.5/681.8/699.3 | -41.9% |
| V2 4, raw 4 MiB | 1545.2/1849.1/2677.1 | 932.9/1027.5/1295.6 | -39.6% |
| V2 40, raw 4 MiB | 8675.5/9120.1/9149.3 | 4766.4/5274.3/5344.2 | -45.1% |

Zegar: początek w tej samej ewaluacji co klik; koniec w transaction.oncomplete przed resolve Promise. Późny listener complete i DOM/two-rAF UI mierzone oddzielnie. p95 nearest-rank (23. z 24), osiem zapisów/profil skorelowanych; nie jest to gwarancja ogona rozkładu telefonu.

| Profil | Mediana natywnego complete po | Mediana późnego callbacku po | Mediana pełnego UI po |
|---|---:|---:|---:|
| V2 0, raw 0 | 266.6 | 276.9 | 331.2 |
| V2 4, raw 0 | 635.5 | 668.8 | 737.5 |
| V2 4, raw 4 MiB | 932.9 | 965.0 | 1021.3 |
| V2 40, raw 4 MiB | 4766.4 | 5014.9 | 5080.1 |

## V2 0, raw 0: rozłączne średnie etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 11.7 | 12.1 |
| source-encode-hash | 18.0 | 18.6 |
| archives | 0.0 | 0.1 |
| legacy-projection | 168.5 | 93.5 |
| transaction-open | 0.6 | 0.6 |
| cas-read | 11.3 | 12.3 |
| cas-compare | 5.1 | 5.4 |
| source-write | 12.1 | 13.1 |
| source-readback | 14.1 | 9.3 |
| source-verify | 42.0 | 5.3 |
| model-write-readback-compare | 21.6 | 21.1 |
| root-verified-complete | 8.8 | 9.3 |
| strict-complete | 0.0 | 0.0 |
| post-complete | 0.0 | 0.0 |
| source-preparation | 0.0 | 15.6 |

## V2 4, raw 0: rozłączne średnie etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 27.6 | 28.4 |
| source-encode-hash | 51.8 | 53.0 |
| archives | 0.2 | 0.2 |
| legacy-projection | 638.3 | 232.1 |
| transaction-open | 0.4 | 0.4 |
| cas-read | 35.3 | 33.0 |
| cas-compare | 14.6 | 14.4 |
| source-write | 33.4 | 33.4 |
| source-readback | 36.0 | 20.6 |
| source-verify | 118.9 | 14.2 |
| model-write-readback-compare | 66.8 | 63.2 |
| root-verified-complete | 22.6 | 25.4 |
| strict-complete | 0.0 | 0.0 |
| post-complete | 0.0 | 0.0 |
| source-preparation | 0.0 | 42.2 |

## V2 4, raw 4 MiB: rozłączne średnie etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 28.4 | 28.7 |
| source-encode-hash | 57.7 | 53.6 |
| archives | 0.1 | 0.1 |
| legacy-projection | 1010.6 | 462.9 |
| transaction-open | 0.7 | 0.5 |
| cas-read | 56.3 | 52.5 |
| cas-compare | 20.6 | 22.5 |
| source-write | 35.4 | 33.9 |
| source-readback | 58.8 | 19.9 |
| source-verify | 124.5 | 14.3 |
| model-write-readback-compare | 147.7 | 129.3 |
| root-verified-complete | 26.4 | 22.1 |
| strict-complete | 0.1 | 0.0 |
| post-complete | 0.0 | 0.0 |
| source-preparation | 0.0 | 44.0 |

## V2 40, raw 4 MiB: rozłączne średnie etapy (ms)

| Etap | Przed | Po |
|---|---:|---:|
| validation | 196.7 | 204.4 |
| source-encode-hash | 428.3 | 452.8 |
| archives | 0.2 | 0.2 |
| legacy-projection | 5344.1 | 2080.7 |
| transaction-open | 0.6 | 0.8 |
| cas-read | 231.7 | 253.7 |
| cas-compare | 116.3 | 113.5 |
| source-write | 235.7 | 233.2 |
| source-readback | 269.1 | 135.0 |
| source-verify | 943.5 | 111.7 |
| model-write-readback-compare | 561.9 | 531.8 |
| root-verified-complete | 146.8 | 142.1 |
| strict-complete | 0.1 | 0.1 |
| post-complete | 0.0 | 0.0 |
| source-preparation | 0.0 | 325.4 |

Każdy profil potwierdza SHA zachowania pierwotnych sesji, wyników, snapshotów i wszystkich archiwów. Zmieniło się wyłącznie siedem plików runtime wskazanych w raporcie; app.js/CSS/manifest pozostają identyczne.

[Próbki i hashe](stage-b-measurements.json). Wcześniejsza seria późnego callbacku jest osobnym artefaktem; nie łączymy jej z tymi statystykami.
