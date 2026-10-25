# P0 — koszt rzeczywiście zatwierdzonego zapisu wyniku

## Wynik i punkt wyjścia

Praca na `main` `2504e5a503a5f0607986fbe29ac1df35aee87c4b`, po scaleniu
PR #76 i #78, w osobnej gałęzi `perf-durable-result-write`.
Przeczytano plan nadrzędny, AGENTS.md, raporty Issue #73/#75 i aktualny kod.
Zachowano ukończone wcześniejsze pomiary; nowe dotyczą granicy trwałego zapisu.

**Cel <=1 s nie został osiągnięty dla modeli V2.** Potwierdzono i ograniczono
zbędną serializację pełnych archiwów przy dwóch porównaniach modelu. Dalsza
poprawa wymaga odrębnego etapu opisanego w
[projekcie i analizie ryzyka](DURABLE_WRITE_P0_PROJECT.md). Nie wdrożono tej
większej przebudowy ani migracji. Problem P0 pozostaje otwarty.

Właściciel zgłosił około 10 s na fizycznym **Pixel 9**, z najnowszym według
niego Androidem. Dokładne wersje Androida/Chrome i rozmiar jego bazy nie są
znane. Nie mieliśmy dostępu do telefonu ani jego danych. Poniższe liczby są
**syntetycznymi pomiarami Chromium na Linux, nie pomiarami Pixela**.

## Potwierdzona przyczyna w kodzie

`app.js/persist` wywołuje pełny protokół `indexeddb.js/save`, również po
zmianie jednego wyniku. Obejmuje on przygotowanie odłączonego kandydata,
walidację źródła i katalogu, kodowanie/hash, budowę mostka modelu v3,
transakcję strict z CAS, przepisanie tabel, odczyt/walidację źródła,
zapis/odczyt/porównanie modelu i dopiero `complete`, publikację pamięci,
obsługę szkicu i UI. `async` nie usuwa synchronicznej pracy z głównego wątku.

`createLegacyModel` ponownie buduje i sprawdza pełny payload, w tym
`legacySources.raw` zawierające także archiwa. Wywołuje projekcję historii,
reader legacy i backup builder, z wielokrotnymi walidacjami snapshotów,
parsowaniem, kopiowaniem, serializacją i SHA. W transakcji dwa porównania
`canonical(a) === canonical(b)` dodatkowo sortowały i serializowały kompletne
modele. Daje to cztery pełne escaped kopie JSON przy każdym zapisie.
Nie znaleziono podstaw do omijania walidacji, usuwania raw ani zastąpienia CAS
porównaniem samego digest/revision.

Na V2 40 + raw 4 MiB przed zmianą średnie rozłączne etapy wynosiły:

- projekcja/pełna budowa legacy: **5445 ms**;
- walidacja wejścia: **200 ms**, kodowanie/hash źródła: **437 ms**;
- CAS: odczyt **248 ms**, porównanie pełnego modelu **589 ms**;
- zapis źródłowych tabel **246 ms**, odczyt kontrolny **292 ms**, weryfikacja **954 ms**;
- zapis/odczyt/porównanie nowego modelu **1059 ms**;
- końcowy zapis root i oczekiwanie strict complete **150 ms**.

Transakcja obejmuje wykonywany w niej JS i kolejki requestów, nie tylko czas
fizycznego flash. Marker `archives` mierzy tylko obsługę dopisywanych archiwów;
nie wolno z jego małej wartości wnioskować, że raw nie kosztuje — jest ponownie
przetwarzany w budowie legacy i porównaniach modelu.

Oddzielny diagnostyczny zapis V2 4 + raw 4 MiB, z profilerem, wykazał przed/po:
`JSON.stringify.bulk` **345/99 ms**, `TextEncoder` **102/107 ms**,
natywne `crypto.subtle.digest` **24/28 ms**, parser bezpieczny **168/181 ms**,
pełny builder legacy **908/916 ms**. To spany inkluzywne, z narzutem pomiaru;
nie sumujemy ich z etapami. Nazwa `backup.digest` obejmuje przygotowanie
canonical i kodowanie, nie sam algorytm SHA. Haszowanie natywne nie wyjaśnia
samodzielnie wielosekundowego oczekiwania. W zwykłej serii V2 4 + raw 4 MiB
średni `render` po poprawce to około 11 ms, a budowa legacy około 948 ms.
Kolektor dowodów szkiców nie jest uruchamiany przez ten zapis.

## Minimalna implementacja

W `indexeddb.js` dodano porównanie pełnej wartości modelu bez tworzenia JSON
z wielomegabajtowych stringów. Zastosowano je wyłącznie w dotychczasowym CAS
i kontroli nowego modelu. Sprawdza wszystkie klucze (również nieznane pola),
kolejność tablic i dokładną treść każdego raw; nie ma cache ważności ani
skrótu opartego wyłącznie na SHA. Dla nietypowych wartości legacy zachowano
obsługę dotychczasowego canonical. Dodano testy równoważności i rzeczywistego
CAS/readback w Chromium. Odświeżono wyłącznie pochodny hash/cache SW.

Bez zmian pozostają: Matrix, komunikat/blokada oczekiwania z #78, chwila
sukcesu po strict complete, CAS, SHA, walidatory, schemat i protokół IndexedDB,
wszystkie zapisy/odczyty kontrolne, historia, wyniki, plany, rotacja, szkice,
archiwa, backupy v1–v6 i istniejące odtwarzanie, Drive. Nie dodano nowego
przywracania ani następnego etapu v6. Nie otwierano produkcyjnej bazy.

Osobny [obserwator DevTools](../scripts/pixel_write_probe.js) nie jest assetem
aplikacji. Nie inicjuje zapisu/odczytu IDB ani sieci, nie zbiera formularzy,
ID, rekordów i raw. Daje dobrowolny pomiar istniejącej operacji właściciela,
z `strict complete` i czasami transakcji/SHA; bufor tylko RAM, maksymalnie
20 operacji, przywracanie hooków przez `stop()`. Test potwierdza brak zmian
bazy po instalacji, brak sukcesu przed complete i odtworzenie oryginalnych metod.
Instrukcja i ograniczenia korelacji są w projekcie. Nie jest to wykonany pomiar telefonu.

## Benchmark przed/po

Chromium 154.0.8037.57, Linux x86_64, Xeon Platinum 8573C, viewport 390×844,
CDP CPU ×4. To ograniczenie CPU na serwerze, nie emulacja sprzętu Androida.
288 zakończonych zapisów: 6 scenariuszy × 2 wersje × 3 niezależne profile ×
8 nowych wyników różnych ćwiczeń. Osiem zapisów w jednym profilu jest
skorelowanych. Nie uruchamiano równolegle regresji. Wszystkie zapisy offline
z aktywnym SW; szkic trwały przed kliknięciem. Uruchomienie aplikacji/start
sesji pozostają poza zegarem tych pomiarów; nie powtarzano zakończonych
pomiarów cold/warm z #75.

Czas od rzeczywistego zdarzenia submit do `complete` transakcji historii
`meta/state`, z potwierdzonym `durability: strict`, a nie do zapisu szkicu
ani samego pokazania oczekiwania. DOM/dwie klatki są tylko proxy odmalowania.
Mediana standardowa, p95 nearest-rank (23. z 24 próbek). Czas w ms:

| Profil | Przed mediana/p95 | Po mediana/p95 |
|---|---:|---:|
| legacy 4, bez dodatkowego raw | 85/111 | 84/96 |
| V2 4, bez dodatkowego raw | 1254/1367 | 1125/1225 |
| V2 4, raw ASCII 4 MiB | 1772/1918 | 1559/1680 |
| legacy 400, raw ASCII 4 MiB | 1913/2229 | 1817/2071 |
| V2 40, raw ASCII 4 MiB | 10004/10668 | 9171/9892 |
| V2 4, raw Unicode/escapes 16 MiB | 6215/6462 | 4321/4672 |

Największa redukcja mediany to **30,5%** przy raw wymagającym escapowania.
CAS tego scenariusza spadł średnio **968 → 28 ms**, a zapis/odczyt/porównanie
modelu **1387 → 440 ms**. Dominująca budowa legacy pozostała **3113 → 3132 ms**.
Na dużym V2 mediana poprawiła się o 8,3%, ale **maksimum pogorszyło się
10962 → 11766 ms**. To nie dowód uniwersalnej poprawy każdej próby.
Legacy jest kontrolą bez modelu V2; jego różnic nie przypisujemy optymalizacji
raw. Współdzielony host i mała liczba profili ograniczają wnioski z ogona.
Wczesny komunikat nadal pojawia się około 30 ms; nie uznajemy go za trwały zapis.

Każdy profil potwierdza SHA-256 zachowania starej historii, wyników, snapshotów
i wszystkich archiwów przed/po swoich zapisach. Między rewizjami zgadzają się
struktury, liczby i rozmiary fixture; generowane ID/czasy V2 mogą się różnić,
więc hashe pomiędzy osobnymi profilami nie muszą być identyczne. Hash runtime
potwierdza, że z assetów zmienił się tylko `indexeddb.js`; aplikacja i CSS są
identyczne. Poza serią są dwa pojedyncze diagnostyczne profile CPU.

[Pełne tabele](performance/durable-write-tables.md) i
[próbki, rozmiary oraz hashe](performance/durable-write-measurements.json).
Reprodukcja serialna (zależności z `tests/requirements.txt`, Chromium):

```sh
# Dla każdego wariantu --ref 2504e5a / --ref working:
python scripts/measure_durable_write.py --ref working --kind v2 --count 4 --archive-mib 4 --profiles 3 --writes 8 --cpu 4 --output /tmp/write-v2.json
# Pozostałe: legacy 4/raw0, V2 4/raw0, legacy 400/raw4,
# V2 40/raw4, V2 4/raw16 --archive-shape escaped.
# Szczegóły CPU osobno, bez dołączania do statystyk:
python scripts/measure_durable_write.py --ref working --kind v2 --count 4 --archive-mib 4 --profiles 1 --writes 1 --cpu 4 --detail --cpu-profile --output /tmp/write-detail.json
```

## Weryfikacja i ograniczenia

Nowe testy Node sprawdzają zgodność z canonical dla wartości JSON, 500
deterministycznych drzew, zmian wszystkich pól, Unicode i wielomegabajtowego
raw bez serializacji oraz fallback legacy. Nowe testy Chromium zmieniają raw
bez zmiany revision/digest i symulują uszkodzony odczyt nowego modelu:
CAS odrzuca obcy model, a błąd readback wycofuje wszystkie tabele i zachowuje
szkic/archiwum. Asercje istniejących testów integralności nie zostały osłabione.

Wykonano po zmianie, bez pomijania testów:

- `node --test tests/*.test.*`: **185/185 PASS**, 0 skipped, około 12 s.
- `python -m unittest discover -s tests -p 'test_*.py' -v`:
  **135/135 PASS**, 654,336 s, Chromium 154.0.8037.57 / Playwright 1.62.0.
- Osobno przed pełną regresją: nowe testy porównania Node **4/4 PASS**,
  CAS/readback Chromium **2/2 PASS**, obserwator telefonu **1/1 PASS**.
- `node --check` dla runtime i obserwatora oraz kompilacja skryptów Python: PASS.
- `python scripts/build_release.py --check`: PASS.
- `python scripts/build_release.py --output dist/durable-write`: PASS,
  release `527f06550d88de0a4bd8f013`, bez deploymentu.
- `git diff --check`: PASS.

Pełna regresja obejmuje m.in. quota/abort, wymuszony błąd readback, strict
complete przed sukcesem, równoczesne karty i CAS, wielokrotne kliknięcia,
przywracanie szkiców po restarcie/crashu, historię/plany/wyniki, backupy
oraz istniejące odtwarzanie, offline i aktualizacje wcześniejszych PWA.
Nie zastąpiono jej samymi benchmarkami ani testami nowych helperów.

**GitHub Actions:** do PR skierowano pełny istniejący workflow regresji na
standardowym `ubuntu-latest`, bez zmian zakresu i płatnych runnerów.
Końcowy status przebiegu należy sprawdzić w checks PR; lokalne PASS nie
zastępują wyniku CI. Wynik i link do przebiegu są raportowane w opisie PR.

Przejściowo poświadczenie środowiska było odrzucane (HTTP 401); dostęp wrócił
przed publikacją gałęzi. Ponowny fetch potwierdził aktualny main `2504e5a`.
Nie publikowano tokenów ani nie zmieniano konfiguracji CI.

To minimalne usprawnienie nadaje się do niezależnego przeglądu; nie zamyka P0.
Następny etap wymaga zatwierdzenia [konkretnego projektu](DURABLE_WRITE_P0_PROJECT.md)
i weryfikacji na fizycznym Pixelu z reprezentatywną bazą. Nie wdrożono
większej przebudowy tylko na podstawie korzystnego prototypu syntetycznego.
