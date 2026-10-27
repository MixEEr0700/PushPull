# Issue #82 — syntetyczne pomiary zapisu przyrostowego

Chromium/Linux, CPU throttle ×4, viewport 390×844; **nie fizyczny Android**.
Przed: `46475114841895ad063a8eaea5054b10ef2b2094`; po: `c11c9a07acc7bad9e94a6e4ec20499281ef651e4`.
Runtime SHA-256 i manifesty instrumentowanych wydań: [pełne pomiary](incremental-write-measurements.json).
Host par: AMD EPYC 7763 64-Core Processor, Chromium 154.0.8037.57 built on Debian GNU/Linux 13 (trixie). Limity cgroup: `{'cpu': '400000 100000', 'memory': '34359738368'}`.
Osobny host testów wzrostu v2: AMD EPYC 9V74 80-Core Processor. To osobna seria, bez porównywania 400 z poprzednim hostem.

**400 sesji nie ma porównania before/after:** stary writer nie potrafił utworzyć fixture. Chromium odrzucił training-model-v1: 156140248 B (raw 4 MiB) i 181306072 B (escaped 16 MiB), limit 133169152 B. Quota wynosiła około 10 GiB. Obie transakcje wycofano; po restarcie stara pusta historia pozostała poprawna. Dokładne zdarzenia w JSON. Dlatego 400 zbudowano przez rzeczywisty bulk API v2 i testowano wyłącznie jako wzrost v2; nie jest to dowód konwersji tak dużej bazy v1.

W sześciu sparowanych przypadkach po 3 niezależne profile/procesy dla wariantu, po 8 zapisów offline w profilu (4 nowe, 4 korekty bieżącej sesji). Oba warianty otrzymały dokładnie te same rekordy v1 i localStorage, przygotowane raz przez stary walidowany writer. SHA pełnego początkowego eksportu sprawdzono po otwarciu/konwersji w każdym profilu. Kolejność par: przed/po, po/przed, przed/po. Bez równoległych lokalnych testów.

Każde p95 to najbliższa ranga (ceil(0,95·n)); 24 operacje są skorelowane wewnątrz trzech profili. To statystyka opisowa tej próby, nie gwarancja sprzętu. Wynik obejmuje pierwszy zapis; nie wybierano najszybszych operacji. Cel Androida p50 <500 ms, p95 <1000 ms pozostaje do osobnego odbioru.

Zegar zaczyna się bezpośrednio przed wywołaniem kliknięcia formularza, kończy w natywnym handlerze strict transaction complete, przed publikacją Promise/UI. Osobno zachowano event.timeStamp i późniejszy callback. Test kontrolny dodaje 60 ms po complete, nie zmieniając natywnego wyniku. To potwierdzenie IndexedDB durability strict, nie pomiar fizycznego fsync kontrolera telefonu.

## Kliknięcie → natywne strict complete (ms)

| Baza | Live JSON MiB | Raw UTF-8 MiB / kształt | Przed mediana / p95 / max | Po mediana / p95 / max |
|---|---:|---|---:|---:|
| empty | 0.10 | 0 / ASCII | 383.6 / 428.1 / 437.1 | 112.7 / 127.0 / 150.8 |
| small | 0.53 | 0 / ASCII | 917.2 / 1029.5 / 1041.4 | 124.1 / 161.5 / 162.8 |
| history40 | 4.37 | 0 / ASCII | 5812.8 / 6549.3 / 6759.0 | 155.5 / 453.3 / 558.2 |
| history40-raw4 | 4.37 | 4 / ASCII | 6407.7 / 6779.5 / 6822.6 | 152.5 / 559.7 / 693.1 |
| history40-unicode4 | 4.37 | 4 / Unicode | 6152.1 / 6645.0 / 6890.0 | 167.4 / 453.7 / 554.5 |
| history40-escaped16 | 4.37 | 16 / escaped | 9608.5 / 9980.0 / 10143.1 | 166.2 / 439.6 / 468.1 |
| history400-raw4 | 42.79 | 4 / ASCII | n/a — limit rekordu v1 | 138.0 / 417.3 / 448.8 |
| history400-escaped16 | 42.79 | 16 / escaped | n/a — limit rekordu v1 | 138.1 / 453.4 / 489.8 |

## Rodzaje zapisu po zmianie (ms)

| Baza | Nowe: mediana / p95 (n=12) | Korekty: mediana / p95 (n=12) | Pierwszy: mediana / max (n=3) |
|---|---:|---:|---:|
| empty | 116.0 / 150.8 | 106.9 / 114.0 | 127.0 / 150.8 |
| small | 125.4 / 162.8 | 120.0 / 131.5 | 161.5 / 162.8 |
| history40 | 160.1 / 558.2 | 153.6 / 170.6 | 453.3 / 558.2 |
| history40-raw4 | 168.2 / 693.1 | 150.7 / 172.8 | 559.7 / 693.1 |
| history40-unicode4 | 170.3 / 554.5 | 155.2 / 186.7 | 453.7 / 554.5 |
| history40-escaped16 | 169.8 / 468.1 | 164.1 / 191.1 | 439.6 / 468.1 |
| history400-raw4 | 138.2 / 448.8 | 135.3 / 186.7 | 417.3 / 448.8 |
| history400-escaped16 | 147.6 / 489.8 | 122.6 / 146.5 | 453.4 / 489.8 |

## UI i główny wątek po zmianie

Pierwsza reakcja jest proxy DOM + dwa requestAnimationFrame, nie nagraniem ekranu. UI-ready obejmuje koniec blokady i dwa kolejne rAF. Pomiar DOM i instrumentacja dodają narzut; zachowano je po obu stronach. Long tasks są mierzone w oknie operacji.

| Baza | Pierwsza reakcja mediana / p95 ms | UI-ready mediana / p95 ms | Najdłuższe zadanie max ms |
|---|---:|---:|---:|
| empty | 28.8 / 29.5 | 179.5 / 196.0 | 0.0 |
| small | 29.2 / 30.3 | 195.2 / 229.6 | 56.0 |
| history40 | 27.9 / 29.9 | 229.3 / 540.0 | 422.0 |
| history40-raw4 | 28.5 / 30.6 | 230.2 / 641.1 | 505.0 |
| history40-unicode4 | 28.5 / 30.1 | 245.6 / 537.1 | 359.0 |
| history40-escaped16 | 28.4 / 30.1 | 244.2 / 527.1 | 305.0 |
| history400-raw4 | 29.5 / 30.9 | 263.7 / 564.3 | 330.0 |
| history400-escaped16 | 29.9 / 31.4 | 263.6 / 596.9 | 356.0 |

## Otwieranie i pamięć — ograniczenie, nie czas zapisu

Dla sześciu sparowanych przypadków initial obejmuje rzeczywistą konwersję v1→v2 (po) albo zwykłe otwarcie v1 (przed). Dla 400 initial jest otwarciem już istniejącego fixture v2, bez konwersji/checkpointu dużej v1 — nie porównywać tych dwóch rodzajów initial. Process-cold oznacza nowy proces przeglądarki z zachowanym profilem; nie czyszczenie cache systemu/dysku. Warm to reload offline w tym samym procesie. Start sesji/bulk są poza zegarem wyniku i nadal mogą trwać wiele sekund. Poniżej mediany z 3 profili, w sekundach; nie p95 z trzech próbek.

| Baza | Przed initial / cold / warm s | Po initial / cold / warm s |
|---|---:|---:|
| empty | 1.0 / 0.9 / 0.5 | 2.4 / 1.4 / 1.2 |
| small | 2.2 / 2.0 / 1.3 | 6.5 / 2.4 / 2.3 |
| history40 | 8.5 / 9.0 / 8.8 | 44.6 / 12.5 / 12.4 |
| history40-raw4 | 9.6 / 9.7 / 9.3 | 52.3 / 15.2 / 14.8 |
| history40-unicode4 | 8.9 / 9.0 / 9.5 | 49.9 / 14.8 / 14.1 |
| history40-escaped16 | 15.4 / 15.4 / 15.1 | 110.6 / 32.0 / 31.0 |
| history400-raw4 | n/a | 12.9 / 13.1 / 12.6 |
| history400-escaped16 | n/a | 15.5 / 15.3 / 14.8 |

Próbkowany JS heap high-water nie jest absolutnym peak procesu: blokujący JS może uniemożliwić próbkę, brak narzutu natywnego IndexedDB/Chrome. Przed serią i po niej jawnie wywołano CDP HeapProfiler.collectGarbage, aby mierzyć retained heap; nie symuluje to losowego ciśnienia pamięci telefonu. Post-GC to usedSize z CDP, nie pamięć fizyczna Androida. Archiwa powtarzają syntetyczny wzorzec, co może wpływać na kompresję i I/O.

| Baza | Startup high-water max MiB przed / po | Save high-water max MiB przed / po | Post-GC po serii mediana MiB przed / po |
|---|---:|---:|---:|
| empty | 22.0 / 29.0 | 51.2 / 13.2 | 6.7 / 5.3 |
| small | 72.3 / 114.8 | 96.2 / 17.2 | 13.8 / 9.0 |
| history40 | 250.6 / 668.8 | 460.3 / 52.8 | 70.7 / 43.7 |
| history40-raw4 | 414.6 / 917.8 | 585.9 / 72.8 | 90.7 / 59.7 |
| history40-unicode4 | 351.5 / 744.0 | 535.9 / 67.0 | 82.7 / 56.2 |
| history40-escaped16 | 1028.1 / 1778.6 | 786.1 / 140.9 | 156.1 / 118.3 |
| history400-raw4 | n/a / 1409.7 | n/a / 61.6 | n/a / 40.7 |
| history400-escaped16 | n/a / 965.5 | n/a / 89.0 | n/a / 58.0 |

## Zachowanie danych i reprodukcja

Wszystkie 42 profile (36 sparowanych + 6 tylko v2): preserved=true; po 336 zapisach porównano SHA całej wcześniejszej historii, snapshotów oraz wszystkich archiwów przed/po serii. Dokładne fixtureSourceHash i liczniki pozostają w JSON. Nie używano profili telefonu, nie usuwano danych produkcyjnych. Błędy/CAS/quota/abort/wielokartowość/PWA i odzyskiwanie są osobnymi testami regresji, nie częścią udanej serii wydajnościowej.

```sh
python scripts/measure_incremental_write.py --before 4647511 --after c11c9a07acc7bad9e94a6e4ec20499281ef651e4 --profiles 3 --writes 8 --cpu 4 --cases empty small history40 history40-raw4 history40-unicode4 history40-escaped16 --output /tmp/incremental-new.json --artifacts /tmp/incremental-new
python scripts/measure_incremental_write.py --after c11c9a07acc7bad9e94a6e4ec20499281ef651e4 --v2-only --cases history400-raw4 history400-escaped16 --profiles 3 --writes 8 --cpu 4 --output /tmp/incremental-v2-new.json --artifacts /tmp/incremental-v2-new
python scripts/diagnose_legacy_record_limit.py --before 4647511 --output /tmp/legacy-record-new
```

Skrypt odmawia nadpisania pomiarów i tworzy wyłącznie świeże profile syntetyczne. Wymaga Chromium, Playwright i historii Git. Trwa długo, ponieważ również wolne operacje sprzed zmiany są mierzone w pełni. Nie uruchamiać równolegle testów/benchmarków. Smoke harness nie został dołączony do dowodów wydajności.

Dodatkowe [kopie dużych baz](incremental-large-backups.json): v3 eksport/odczyt 2/2 zgodne, v5 2/2 odmowy przez istniejący limit 64 MiB live-model (brak zaliczonego dużego roundtrip v5; strict skrypt zakończył się błędem). [Rzeczywisty import v3 do dwóch świeżych izolowanych IndexedDB v2](incremental-v3-restores.json) zachował dane/katalog/archiwa, source read-only i preimage target. Weryfikacja działała po benchmarkach, bez ich równoległego obciążenia.

```sh
python scripts/verify_incremental_large_backups.py --fixtures /tmp/incremental-v2-new --output /tmp/incremental-backup-new --ref c11c9a0
# Po zdiagnozowanej odmowie v5: tylko brakujący import v3, bez powtarzania v5.
python scripts/verify_incremental_large_backups.py --fixtures /tmp/incremental-v2-new --output /tmp/incremental-restore-new --ref c11c9a0 --restore-v3-only
```

## Rozłączne etapy ścieżki trwałego zapisu

Mediany przedziałów między markerami (ms) dla 40 sesji + 16 MiB escaped raw. Mediana sumy nie musi być sumą median. Nie są to same czasy CPU ani fizycznego fsync; oczekiwanie transakcji i readback pozostaje w odpowiednich przedziałach. Brak wielkiego źródła/modelu na ścieżce po zmianie nie oznacza pominięcia walidacji zmienionego wyniku.

### Przed

| Marker do następnego etapu | Mediana ms |
|---|---:|
| validation | 287.5 |
| source-encode-hash | 575.9 |
| archives | 0.1 |
| legacy-projection | 5395.3 |
| source-preparation | 396.9 |
| transaction-open | 0.6 |
| cas-read | 510.2 |
| cas-compare | 165.7 |
| source-write | 346.6 |
| source-readback | 176.4 |
| source-verify | 157.6 |
| model-write-readback-compare | 1113.0 |
| root-verified-complete | 221.6 |

### Po

| Marker do następnego etapu | Mediana ms |
|---|---:|
| detach-validate | 0.5 |
| context | 5.6 |
| entry-hash | 0.9 |
| index-prepare | 5.9 |
| transaction-open | 0.2 |
| cas | 49.0 |
| write-objects | 12.7 |
| write-result-root | 0.2 |
| readback | 57.1 |

