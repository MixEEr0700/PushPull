# Opis PR etapu B

Base: `perf-durable-result-write` (#79); head: `perf-stage-b-prepared-model`.

Zapis pojedynczego wyniku ponownie budował i sprawdzał kompletny source-backed model oraz dekodował pełny odczyt kontrolny. Etap B przygotowuje odłączony, zwalidowany kandydat raz, współdzieli tylko udowodnione niezmienne grafy i porównuje wszystkie odczytane rekordy z zamrożonym wynikiem kodowania. Pozostają pełny CAS poprzedniego modelu/revision, SHA, readback nowego modelu i sukces dopiero po strict complete.

**Cel <=1 s na Androidzie nie został osiągnięty dla dużej historii.** Nie deklarujemy poprawy zmierzonej na fizycznym Pixelu 9. Kolejnego writera nie implementowano; przygotowano konkretny projekt protokołu przyrostowego z bezpieczną aktualizacją i analizą zgodności.

PR etapu B bazuje na niescalonym #79 (`perf-durable-result-write`, `4a74d1d`). Nie scalać automatycznie. Issue #75 pozostaje otwarte.

| V2, historia / dodatkowe raw | Przed mediana / p95 (ms) | Po mediana / p95 (ms) |
|---|---:|---:|
| 0 / 0 | 354 / 414 | 267 / 296 |
| 4 / 0 | 1094 / 1192 | 635 / 682 |
| 4 / 4 MiB | 1545 / 1849 | 933 / 1028 |
| 40 / 4 MiB | 8676 / 9120 | 4766 / 5274 |

192 finalne próbki, 3 niezależne procesy/profil x 8 wyników/wersja/scenariusz, naprzemienne pary, Chromium/Linux, CPU x4, 390x844, offline. Natywny koniec jest rejestrowany w transaction.oncomplete **przed resolve Promise**. Poprawiono błąd wcześniejszego harnessu (późny listener mógł zawierać kontynuację Promise); test z wymuszonymi 60 ms pracy po complete chroni tę granicę. Starych 288 wartości callbacku nie mieszamy z finalną serią natywną. Statystyki nie są pomiarem telefonu ani gwarancją ogona rozkładu Androida.

Dla 40 sesji budowa modelu spada średnio 5344 -> 2081 ms, kontrola źródła 944 -> 112 ms, z nowym przygotowaniem projekcji 325 ms. Pełny source/hash oraz duży model nadal dają koszt zależny od całej bazy. Dalsze marginalne poprawki nie są wdrażane.

- Format/schemat DB bez zmian; Matrix i komunikaty z #78 bez zmian. Zachowane plany, snapshoty, sesje, serie/segmenty/strony, historia, szkice, archiwa, backupy v1-v6 i istniejące odtwarzanie/Drive. Bez resetu i usuwania danych.
- Prywatne WeakSet/WeakMap nie przyjmują publicznego tokenu skipValidation i nie cache'ują validity po ID/revision. Mutowalne grafy i płytki freeze przechodzą pełną walidację ponownie. Dowód źródła zachowuje tylko wersję, nie drugi parsed raw.
- Nowe testy: dokładne bajty/SHA wobec writera #79 i odczyt starym readerem; mutacja po await, nieznane pola, Unicode/duży raw, fałszywe dowody, retencja pod heap 128 MiB; atomowe odrzucenie uszkodzonego root/wiersza przy tych samych licznikach/SHA.
- Lokalne pełne testy: **Node 192/192 PASS**, **Chromium/PWA 140/140 PASS**, kontrola SW i build produkcyjny PASS. Asercje integralności nie zostały osłabione.
- GitHub Actions: oczekuje na uruchomienie/zweryfikowanie; API środowiska obecnie blokowane polityką sieci (Forbidden). Nie traktować lokalnych PASS jako CI PASS. Workflow bez zmian; bez płatnych larger runners.

Raport: `docs/DURABLE_WRITE_STAGE_B.md`; dowody i tabele: `docs/performance/stage-b-measurements.json`, `stage-b-tables.md`.

Do osobnego zatwierdzenia: `docs/INCREMENTAL_WRITE_P0_DESIGN.md` — polecenia pojedynczego wyniku, niezmienne obiekty planów/snapshotów, mały root integralności, DB protocol 2 z zachowanym checkpointem v1, CAS, readback, fail-closed starych kart, konwersja z kontrolą rewizji, quota/abort/restart i zgodny reader rollbacku. Bez automatycznego kasowania bazy. Nie implementowano tego protokołu w etapie B.

Refs #75, #79.
