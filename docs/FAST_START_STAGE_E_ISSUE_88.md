# Etap E — szybki start i komendy sesji (Issue #88)

Baza: PR #87, `4aea982d4f77257b3836ef11a76d12f444cbe5ea`.
Łańcuch pozostaje niescalony: #83 → #84 → #85 → #87 → E.
Nie zmieniono CSS, Matrix, Google Drive ani formatów kopii v1–v6.
Poniższe pomiary dotyczą izolowanych danych syntetycznych Chromium/Linux,
CPU ×4, ekranu 390×844. **Nie są wynikami fizycznego Pixela 9.**

## Potwierdzona przyczyna

Zachowane profile D (`docs/performance/startup-p0-*.json`) rozdzielają zwykły
start od konwersji i certyfikacji. Czasy inkluzywne, mediany ms; nie sumować:

| Etap D | 40 sesji / raw 4 MiB | 400 sesji / raw 4 MiB |
|---|---:|---:|
| readTraining: odczyt + pełna weryfikacja live | 762 | 4929 |
| materializeTraining: Merkle, obiekty, graf | 591 | 3593 |
| validateSource: walidacja relacji | 289 | 1553 |
| facade openDatabase (w tym powyższe) | 851 | 5717 |
| odtwarzanie szkiców | 4 | 16 |
| render (w tym main) | 37 | 119 |

DOM nie wyjaśniał wielosekundowego startu. D unikał już raw/checkpointów,
lecz czytał wszystkie sesje, wyniki, snapshoty, węzły Merkle i zbiory ID.
Nie powtórzono analiz PR #79/#81, konwersji v1 ani znanego limitu rekordu
v1 dla 400 sesji. Etap E mierzy zwykły start po D i osobno instalację indeksu.

## Kontrakt indeksu

Root protokołu 2 otrzymuje opcjonalne `runtime`:
`{version:1,indexRoot,sourceRoot}`. `sourceRoot` musi równać się głównemu
`indexRoot`; wszystkie pola są objęte SHA-256 root/epoch/revision.
Schemat IndexedDB i object stores pozostają w wersji 2. Nowe obiekty i
węzły są content-addressed i uwzględnione w limitach allocation.

Oddzielne drzewo AVL zawiera klucze:

- `info`: max sequence, ostatnia zakończona sesja, snapshoty podglądu
  rzeczywiście zgodne z bieżącymi parametrami źródłowymi;
- `context/exerciseId`: najnowsze główki per wariant/plan/jednostka/baza kg
  oraz dokładny wiek zmiany wyniku, z tą samą semantyką co pełny oracle;
- `history/exerciseId`: małe deskryptory pomiaru i kontekstu; odczyt przy
  zmianie tego ćwiczenia, nie podczas uruchamiania;
- `global/resultId`: właściciel każdego globalnego ID wyniku;
- `pair/sessionId/exerciseId` i `session/sessionId`: dokładne powiązania.

Nie porównujemy nieporównywalnych wariantów ani konwencji. L/P, drop,
back-off i nieustalony pomiar zachowują dotychczasową semantykę. Wyliczenie
korzysta z istniejącej funkcji `comparison`, a testy porównują indeks z
`resultChangeAge` na pełnej historii. Kolizje obejmują również niewczytane
wyniki. Usunięte z korekty ID są usuwane z aktywnego indeksu; stare
niezmienne obiekty/węzły nadal pozostają w bazie jako dowód rewizji.

## Odczyt, zapis i granica zaufania

Zwykły reader odczytuje metadata/plan, aktywną sesję, niezbędne główki
wyników, ich snapshoty i uwierzytelnione ścieżki Merkle. Sprawdza root,
marker, SHA obiektów/węzłów, relacje wymaganych snapshotów/wyników i
liczności stores. Nie używa `getAll` historii, indeksu, raw ani checkpointu.
Karty filtrują główki według faktycznego kontekstu, bez zgadywania historii.
Wszystkie jednostki bieżącego planu są przygotowane do dotychczasowej
synchronicznej nawigacji Matrix.

Kalendarz/historia/statystyki doczytują i walidują pełny graf live.
Zwykła edycja pełnego modelu odmawia, jeżeli caller nie wczytał historii
**przed** przygotowaniem mutacji. Dane/eksport/preimage/import wymagają
pełnego audytu, obejmującego raw, checkpointy i semantyczne przeliczenie
całego indeksu z pełnego źródła. Bulk edits przebudowują indeks atomowo.
Historyczne szkice wymagające innej sesji powodują pełny odczyt live przed
oceną zgodności — brak danych nie jest przedstawiany jako konflikt szkicu.

`saveResult`, `startSession`, `finishSession` przygotowują hashe poza IDB,
sprawdzają root/epoch/revision, wymagane obiekty i ścieżki, aktualizują
zmienione rekordy i oba drzewa w jednej transakcji `durability:strict`.
Readback odbywa się przed jej końcem, a publikacja i sukces dopiero po
natywnym `complete`. Powtórna komenda nie tworzy drugiej sesji. Zakończenie
nie omija szkiców ani reguł rotacji przy zmianie planu w trakcie sesji.
Nie użyto `reload()` ani `flush()` jako dowodu trwałości treningu.

Indeks powstaje wyłącznie z uprzednio zweryfikowanego grafu live.
Backup nie dostarcza zaufanego indeksu. Skrócony start jest dowodem
wymaganych fragmentów, a nie pełnym audytem każdego nieczytanego bajtu
historii/archiwów. Pełny audyt wykrywa również indeks poprawnie hashowany,
ale semantycznie niezgodny ze źródłem. Złośliwe przepisanie całej bazy wraz
z ponownym wyliczeniem wszystkich hashy nie jest chronione podpisem ani
zewnętrznym kluczem — ten kontrakt pozostaje niezmieniony.

## Instalacja, odmowa i rollback

Baza D bez indeksu: jednorazowy zweryfikowany odczyt live, wyprowadzenie
indeksu, strict CAS/readback i aktywacja nowego root. Sama instalacja indeksu
nie zmienia rewizji dziennika ani obserwacji szkiców: nie zmieniła treningów.
Zmiana pełnego root nadal odrzuca każdego wcześniej przygotowanego writera.
Oryginalne wiersze,
archiwa, checkpointy, rewizje i modele pozostają. Równoległa instalacja
nie nadpisuje nowszego root. Przerwanie/quota pozostawia poprzedni root;
ponowne otwarcie może powtórzyć przygotowanie bez częściowego indeksu.
Stara konwersja v1 → v2 i jej checkpoint/wznowienie pozostają oddzielne.
Nie resetujemy danych testowych automatycznie.

Uszkodzony indeks: odmowa treningu/zapisu, bez cichej przebudowy. Zachować
pobranie diagnostyczne całej bazy. Świadoma ścieżka odzyskania to istniejący
import zweryfikowanej pełnej kopii z preimage; nie reset, nie wycinanie
indeksu w DevTools. Bez dobrej kopii konieczna jest osobna procedura naprawy
z pełnym audytem dowodu źródłowego, przed jakimkolwiek nadpisaniem.

Stare A–D readery nie rozumieją pola `runtime` i odmawiają (fail closed).
Root CAS blokuje starszego writera pozostawionego w otwartej karcie.
Rollback wymaga readera znającego oba kształty root lub jawnego odtworzenia
sprawdzonej kopii z zachowaniem preimage. Nie obniżać wersji DB i nie
przywracać samego starego JS do nowej reprezentacji.

## Pomiary i testy

Pomiary końcowe: `643928914a420b874cb096f90129f63b94db025a`.
Ostatnia kontrola formatu po tych pomiarach dodatkowo odrzuca jawne
`runtime:null/false/0` zamiast traktować je jak dawny root bez indeksu.
Nie zmienia ścieżki poprawnych danych. Dokładne manifesty źródeł i hashe
artefaktów zapisano w dowodach. Nie uruchamiano pomiarów na telefonie.

### Zwykły start, bez instalacji/konwersji

CPU ×4, 3 uruchomienia nowego procesu i 3 nowe strony ciepłego procesu,
wszystkie offline po przygotowaniu PWA; n=6 per przypadek. Gotowość to
`pushpull-training-ready` po renderowaniu i rejestracji handlerów, nie
sam napis oczekiwania. p95 przy n=6 jest największą próbą, a nie stabilnym
oszacowaniem ogona rozkładu. Zachowano również czasy obserwowane przez
sterownik, osobno cold/warm oraz wszystkie przedziały inkluzywne.

| Baza | D mediana / p95 [s] | E mediana / p95 [s] | D / E szczyt próbki JS [MiB] |
|---|---:|---:|---:|
| 0 sesji | 0,571 / 0,605 | 0,707 / 0,798 | 5,2 / 5,3 |
| 4 sesje | 0,715 / 1,529 | 1,455 / 1,578 | 6,4 / 8,1 |
| 40, raw 4 MiB | 1,487 / 1,953 | 2,059 / 3,387 | 14,9 / 7,9 |
| 40, escaped 16 MiB | 1,284 / 1,390 | 1,613 / 1,761 | 14,8 / 7,6 |
| 400, raw 4 MiB | 6,532 / 6,868 | 3,816 / 8,802 | 77,9 / 7,6 |
| 400, escaped 16 MiB | 6,818 / 10,277 | 2,361 / 3,347 | 84,3 / 7,4 |

**Cel startu <2 s nie został potwierdzony dla wszystkich przypadków.**
Nie odrzucono wolnych prób ani nie powtarzano serii dla lepszego wyniku.
Mniejsze bazy mają narzut punktowych odczytów/proofów, a 400/raw4 ma duży
rozrzut. Wcześniejsze serie E również zachowano lokalnie jako diagnostykę,
nie podstawiono ich lepszych czasów do tej tabeli. Stare pomiary D pochodzą
z tego samego hosta i narzędzia, ale z wcześniejszej sesji pomiarowej.

Zmniejszenie kosztu pamięci i liczby odczytywanych danych jest potwierdzone:
na starcie 400 sesji jest 291 żądań w profilerze, bez `getAll` wyników,
sesji, snapshotów lub całego indeksu. Nie jest to jednak dowód gotowości
w 2 s na Pixelu 9. Metadane, katalog i bieżący model planów nadal są
wczytywane; mogą zawierać więcej niż samą aktywną definicję. Historyczne
szkice innej sesji świadomie uruchamiają pełny odczyt live.

### Trwały zapis i komendy sesji

Po 3 izolowane profile i 8 zapisów (4 nowe, 4 korekty), n=24 per baza,
łącznie **96 zapisów**. Zegar pochodzi z natywnego `oncomplete` transakcji
strict, przed publikacją Promise/UI. Niezależny test opóźnia publikację
60 ms i potwierdza, że zegar nie mierzy późniejszego listenera ani toastu.
Przed/po profile porównują dokładny SHA całej pierwotnej historii,
snapshotów oraz archiwów i pełny audyt źródła. Wszystkie oracles PASS.

| Baza | Zapis klik → strict complete: mediana / p95 / max [ms] | Start: mediana / max [ms] | Finish: mediana / max [ms] |
|---|---:|---:|---:|
| 0 | 133,7 / 235,1 / 285,3 | 291 / 292 | 233 / 236 |
| 4 | 242,0 / 440,5 / 757,9 | 445 / 607 | 215 / 270 |
| 40, raw 4 MiB | 264,4 / 508,4 / 510,5 | 553 / 633 | 275 / 289 |
| 400, raw 4 MiB | 421,5 / 698,3 / 726,6 | 638 / 1104 | 419 / 473 |

Start/finish mają tylko n=3, więc max jest również empirycznym p95;
nie traktować tego jako miarodajnego oszacowania ogona. Przy 400 sesjach
jedna próba startu przekroczyła sekundę. Zapis wyniku spełnił syntetyczne
progi mediana <0,5 s i p95 <1 s we wszystkich czterech bazach.

**Nie potwierdzono braku regresji względem D.** Zachowane D/40 (n=24):
114,7 / 210,7 ms mediana/p95, E/40: 264,4 / 508,4 ms. Nowe indeksy mają
mierzalny koszt. Dodatkowa kontrola D/400 tym samym aktualnym harness
(n=8): 168,2 / 704,5 ms, E/400 (n=24): 421,5 / 698,3 ms. Różne n i brak
pomiaru urządzenia nie pozwalają ogłosić równoważności wydajności.

Korzyść komend sesji jest znaczna: D/40 wymagał 3,045–3,717 s do strict
startu; E/40: 0,394–0,633 s. Kontrola D/400: start 41,943 s, finish
56,577 s; E/400 odpowiednio 0,636–1,104 s i 0,384–0,473 s.
Wygląd i komunikaty oczekiwania pozostały; sukces wymaga complete.

Retained JS po GC przed/po 8 zapisach (mediany trzech profili, MiB):
0: 3,82 → 4,71; 4: 5,35 → 5,79; 40: 11,13 → 11,68;
400: 9,45 → 10,74. To JS heap, nie całkowity RSS ani RAM Androida.

### Jednorazowe przygotowanie i pamięć

Oddzielna próba aktualnej implementacji z istniejącego D/400/raw4:
**86,692 s** do obserwowanej gotowości, szczyt próbki JS **108,8 MiB**.
Z tego `readTraining` 10,898 s, `buildRuntime` 4,037 s, a instalacja z
CAS/readback 72,681 s (przedziały inkluzywne, nie sumować). Kolejne dwa
starty tej bazy: obserwowane 2,342/2,348 s. Nie jest to koszt każdego startu
ani ponowna konwersja v1. Nie optymalizowano dalej kosztownej aktualizacji
starych testowych danych kosztem codziennego mechanizmu.

Osobna próba read-only 400 sesji / 3500 wyników przy CPU ×4 i
`--max-old-space-size=128`: **PASS**, root bez zmian, zero transakcji RW,
pełny wiek zmiany „100 sesji temu”, szczyt próbki JS 7 329 715 B (~7,0 MiB).
Seed utworzono wcześniej nieograniczonym procesem. Ten test obejmuje zwykły
reader, nie instalację indeksu, eksport lub całkowity limit RAM procesu.

### Weryfikacja i reprodukcja

- Node: **210 PASS** na końcowym kodzie, w tym dokładny oracle kontekstów,
  długie równe serie/zmiany, fałszywy poprawnie hashowany indeks,
  membership/absence/deletion AVL, redukcja tylko niezatwierdzonych węzłów,
  odmowa jawnie wadliwej wersji indeksu i wszystkie wcześniejsze kodeki.
- Wykonano pełną lokalną regresję 178 przypadków. Pierwszy przebieg na
  zmieniającym się kodzie ujawnił błędy; nie uznano go za PASS. Poprawiono
  źródłowe konteksty, zachowanie rewizji instalacji, zakres prezentacji
  opisów i synchronizację lazy widoków. Zakończone testy częściowe obejmują
  wszystkie te przypadki oraz 20 testów aktualnego writera/clock/feedback:
  CAS dwóch klientów, quota/abort/readback, zamknięcie, restart, szkice,
  niekompletny zapis, native tamper mimo ponownego użycia proofu i offline.
- Pełną regresję końcowego SHA w GitHub Actions należy odczytać z PR.
  Oczekiwane 183 przypadki Chromium/PWA; status/URL zostaną uzupełnione
  w opisie PR po rzeczywistym zakończeniu. Nie uruchomiono płatnych runners
  ani workflow publikacji. Build produkcyjny i spójność SW: PASS.
- Piksele zatwierdzonego Matrix: PASS, 360/390/412 px. Test czeka na
  gotowy widok statystyk zamiast fotografować wcześniejszy ekran.

Dowody: [starty](performance/issue-88-e-startup.json),
[96 zapisów i native clocks](performance/issue-88-e-writes.json),
[kontrola D/400](performance/issue-88-d-control.json),
[instalacja](performance/issue-88-index-install.json),
[old-space 128](performance/issue-88-memory-128.json).
Zachowano dowody A–D w `performance/startup-p0-*.json` i raport D.
Duże fixture/profile pozostają poza repozytorium i zawierają wyłącznie
syntetyczne dane. Scripts `measure_startup.py`, `measure_fast_start_writes.py`
i `check_indexed_memory.py` budują allowlistowany, instrumentowany artefakt
z podanego ref; SHA źródeł i instrumentowanego release są w dowodach.
Przykład pamięci: `python scripts/check_indexed_memory.py --ref <SHA>
--fixture <syntetyczny-indexed-fixture.json> --output <nowy-katalog>`.

## Stan odbioru i ograniczenia

Implementacja E jest przeznaczona do przeglądu w osobnym PR opartym na #87.
**P0 nie jest zamknięte:** brak odbioru fizycznego Androida, niejednorodne
starty (do 8,802 s w końcowej serii), mierzalny narzut zapisu względem D i
koszt pierwszej instalacji. Brak zgody na automatyczne scalanie/wdrożenie.
Po tym raporcie zatrzymujemy dalsze optymalizacje syntetyczne; następnym
krokiem jest odbiór na Pixelu 9, chyba że testy ujawnią istotny błąd.

Pełny eksport/restore/audyt i statystyki nadal wymagają całego właściwego
grafu; nie mają gwarancji czasu/pamięci zwykłego treningu. Zmiana wyniku
wczytuje deskryptory jego ćwiczenia, więc ich koszt rośnie z jego historią.
Zachowano limity protokołu i wszystkie stare niezmienne rewizje; brak
nowego automatycznego GC/resetu. Nie wykonano Issue #61 ani etapu v6.


## Odbiór na fizycznym Pixelu 9

1. Zachować pełną kopię dotychczasowej testowej bazy i szkiców. Zanotować
   wersję Chrome/Androida, release PWA, rozmiary/liczby sesji oraz źródło
   instalacji. Zamknąć pozostałe karty, zaktualizować kompletny release.
2. Oddzielić jednorazową instalację indeksu/konwersję od zwykłego startu.
   Nie zamykać w trakcie. Zweryfikować eksport i liczby danych po aktualizacji.
3. Wykonać osobno 10 zimnych i 10 ciepłych startów (także bez sieci),
   zmierzyć pierwszą reakcję i gotowość do treningu. Cel: gotowość <2 s.
4. Wykonać 20 zapisów/korekt oraz start/finish wszystkich jednostek.
   Mierzyć klik → natywny complete transakcji strict, osobno gotowy UI;
   raportować medianę/p95/max. Cele: zapis p95 <1 s, start sesji <1 s.
5. Sprawdzić szkic po zamknięciu procesu, drugi tab, quota/abort na izolowanej
   bazie testowej, Kalendarz, historię, rotację, notatki, statystyki, kopię i
   odtworzenie. Porównać dane z kopią sprzed aktualizacji.
6. Przy przekroczeniu celu zachować trace i liczby, bez czyszczenia bazy.
   Po etapie E zatrzymujemy dalsze optymalizacje syntetyczne; następny krok
   to ten odbiór urządzenia, chyba że pozostał istotny błąd.
