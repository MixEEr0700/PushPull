# Issue #75 — reakcja interfejsu przed trwałym zapisem

## Zakres i stan początkowy

Baza: `main` `1dd4aaf1407da2b32332996f054a6bd49fddf12d` (PR #74).
Przeczytano `AGENTS.md`, plan nadrzędny, pełne Issue #75, raport Issue #73
oraz kod wcześniejszych wersji. PR #76 pozostawał otwarty podczas pracy.
Nie zmieniono `AGENTS.md` ani żadnego workflow; ta gałąź nie zawiera zmian #76.
Praca dotyczy wyłącznie istniejącej aplikacji. Nie rozpoczyna kolejnego etapu v6.

Przed wznowieniem pracy istniał skrypt pomiarowy, sześć testów oraz robocza
obsługa komunikatu oczekiwania. Historyczne i bazowe serie pomiarowe były już
zakończone; zachowano ich wyniki zamiast powtarzać te przebiegi.

## Metoda pomiaru

`scripts/measure_ui_response.py` buduje osobny, instrumentowany artefakt ze
wskazanego commitu (`git archive`) lub checkoutu. Serwer na loopback udostępnia
wyłącznie allowlistę runtime, z przeliczonymi hashami service workera.
Każda próbka ma nowy profil z wyłącznie syntetycznymi danymi. Nie otwiera
istniejących profili, nie łączy się z Drive i nie dotyka bazy właściciela.

Chromium 154.0.8037.57, Linux x86_64, Intel Xeon Platinum 8573C;
viewport 390×844. CDP CPU ×4 dla legacy 4/400 i V2 4; oddzielna seria V2 40
z CPU ×1. Nie porównujemy bezpośrednio różnych ustawień CPU. Pięć niezależnych
próbek na wariant; mediana i p95 nearest-rank. **Przy n=5 p95 jest maksimum**,
nie wiarygodnym opisem ogona rozkładu urządzeń. Współdzielony host jest źródłem
wariancji; nie uruchamiano równolegle benchmarków i regresji.

- `processCold`: zamknięcie całego procesu Chromium po przygotowaniu danych,
  ponowne uruchomienie z tym samym syntetycznym profilem i otwarcie aplikacji.
  Pomiar dokumentu nie obejmuje uruchamiania binarnego procesu. Cache PWA oraz
  cache dyskowy OS są ciepłe. To nie jest cold boot Androida.
- `warm`: kolejna nawigacja w tym samym procesie; `offline`: następne otwarcie
  po `context.set_offline(True)`, z kontrolującym SW. Wszystkie dalsze akcje
  scenariusza wykonano offline.
- Pierwsza reakcja: pierwsza mutacja UI i dwie klatki rAF. Przy starcie dokumentu
  używamy FCP (może to być sam napis „Otwieranie bazy danych…”).
- Pełne otwarcie: oczekiwany DOM i dwie klatki rAF. Dla zapisu dodatkowo
  zakończenie blokady operacji. Jest to proxy odmalowania, bez fizycznego
  pomiaru dotyk–piksel, klawiatury Androida czy dostępności GPU.
- Trwały zapis: zdarzenie `complete` rzeczywistej transakcji historii zawierającej
  `meta/state`, z `durability: strict`. Nie liczymy zapisu szkicu jako zatwierdzenia
  wyniku. Dwa `put(state)` w tej samej transakcji mają wspólną granicę trwałości.
  To granica oferowana przez przeglądarkę; nie symuluje utraty zasilania urządzenia.
- Osobno rejestrowane są inkluzywne spany funkcji, `innerHTML`, transakcje,
  długie zadania i czas wywołania poszczególnych callbacków względem zdarzenia.
  Callbacki po `persist()` mogą czekać za nim; ich opóźnienie nie jest czasem
  pierwszego handlera. Spany zachodzą na siebie, nie wolno ich sumować.

Początkowy przebieg kontrolny wykrył throttling rAF w karcie tła trwałego
profilu. Skrypt zamyka dodatkowe karty i jawnie aktywuje mierzoną kartę.
Odrzucone smoke/przerwane próbki nie wchodzą do publikowanych serii.

Dane: legacy 4/400 sesji, 34/3400 wyników z seriami; natywne V2 4/40 sesji
z rzeczywistymi strukturami snapshotów, referencji, segmentów i serii.
Każdy podstawowy profil zawiera dodatkowe raw archiwum ASCII 4 MiB.
Osobna seria kontrolna V2 4 bez tego archiwum izoluje jego koszt — nie jest
propozycją usuwania danych. Rozmiary faktycznych fixture i hashe źródeł runtime
znajdują się w plikach dowodowych.

Odtworzenie (serialnie, zależności jak dla testów Chromium):

```sh
python scripts/measure_ui_response.py --ref adadf8f --runs 5 --counts 4 400 --output /tmp/history.json
python scripts/measure_ui_response.py --ref 1dd4aaf --runs 5 --counts 4 400 --output /tmp/before-legacy.json
python scripts/measure_ui_response.py --ref working --runs 5 --counts 4 400 --output /tmp/after-legacy.json
# Powtórzyć dla before/working:
python scripts/measure_ui_response.py --ref 1dd4aaf --kind v2 --counts 4 --runs 5 --output /tmp/before-v2.json
python scripts/measure_ui_response.py --ref working --kind v2 --counts 4 --runs 5 --output /tmp/after-v2.json
python scripts/measure_ui_response.py --ref 1dd4aaf --kind v2 --counts 40 --cpu 1 --runs 5 --output /tmp/before-large.json
python scripts/measure_ui_response.py --ref working --kind v2 --counts 40 --cpu 1 --runs 5 --output /tmp/after-large.json
python scripts/measure_ui_response.py --ref 1dd4aaf --kind v2 --counts 4 --archive-mib 0 --runs 5 --output /tmp/archive-control.json
```

## Potwierdzone mechanizmy i minimalna poprawka

1. Zapis aktualnego modelu nadal przechodzi przez pełną walidację,
   serializację/hash, projekcję mostka v3, przepisanie tabel oraz odczyt kontrolny.
   `legacySources.raw` zachowuje także archiwa. Asynchroniczna funkcja nie
   przenosi synchronicznej walidacji i serializacji poza główny wątek. Dla
   legacy 400 `persist` zajmuje średnio około 2956 ms przy zapisie, a `render`
   około 29 ms. Dla V2 4 odpowiednio około 3292 i 11 ms. Sam DOM nie wyjaśnia
   wielosekundowego oczekiwania.
2. Wcześniej `start` i zapis nie dawały widocznego potwierdzenia przed
   `await persist()`. Kolejka `actions` czekała także z obsługą kolejnych kliknięć.
   `input` pozostawał synchroniczny, lecz nie mógł przerwać długiego zadania JS.
   Teraz w chwili przyjęcia lokalnej operacji pojawia się stan oczekiwania,
   zanim uruchomi się kosztowny handler. Dwie klatki i zadanie oddają przeglądarce
   możliwość odmalowania. Fallback 150 ms zapobiega uzależnieniu zapisu od
   wstrzymanych rAF; w ukrytym dokumencie nie czekamy na klatki.
3. Podczas tej operacji `#app` jest `inert` i `aria-busy`; komunikat statusu
   znajduje się poza zablokowanym poddrzewem. Kolejne submit/click/input z aplikacji
   nie trafiają do kolejki. Nie pokazujemy niezacommitowanych danych jako
   zatwierdzonych ani nie umożliwiamy nawigacji po mutowanym stanie roboczym.
   `finally` usuwa blokadę również po błędzie, anulowaniu lub walidacji.
   Przy zdarzeniu z formularza odłączonego przez wcześniejszą akcję nie
   wykonujemy zapisu. Komunikaty sukcesu pozostają w dotychczasowych miejscach,
   po ukończeniu zapisu i obsłudze szkicu.
4. `entriesFor` wykonywał liniowe `sessions.find` dwa razy w komparatorze
   sortowania. Na `main`, legacy 400, kosztował średnio około 26 ms przy
   powrocie do Treningu oraz 22–24 ms przy zapisie/otwieraniu edytora. Lokalna,
   świeża mapa sesji eliminuje te wyszukiwania. Komparator daty/sequence,
   stabilność sortowania i źródła danych są zachowane. Nie ma trwałego cache
   ważności ani problemu z unieważnianiem po korekcie daty/zmianie karty.

Oryginalny Matrix `92390b1` zapisywał synchronicznie do localStorage i nie miał
porównywalnej granicy trwałości IndexedDB. Referencją funkcjonalną jest
`adadf8f` (pierwsze PWA z IndexedDB, bez późniejszych planów V2). Na małym
profilu była nieco szybsza; na dużej historii pełna weryfikacja była dużo
wolniejsza niż na obecnym main. Nie jest dowodem „szybkiego Androida”.
Brak podstaw do przypisania wielosekundowych zapisów kolektorowi z PR #72:
jego odczyt dowodów uruchamia się jawnie, a porównanie #73 przed/po #72
nie wykazało takiej regresji. Nowe wyniki oddzielają koszt funkcji z wielu
etapów od samego kosztu nawigacji.

## Wyniki

Zakończono **55 niezależnych syntetycznych przebiegów**, po 5 na wariant.
[Pełne tabele](performance/issue75-tables.md) obejmują wszystkie operacje,
cold/warm/offline, historię, długie zadania oraz inkluzywne spany.
[Dowody JSON](performance/issue75-measurements.json) zachowują każdą próbkę,
rozmiary fixture, granice transakcji `strict`, hashe runtime i oryginalnych
raportów. Powtarzające się spany zgrupowano w obrębie fazy; czasy zaokrąglono
do 0,001 ms. `--compact` pozwala uzyskać taki sam rodzaj agregacji ze skryptu.

Czasy w ms, **mediana/p95 przed → po**, zapis wyniku:

| Profil | Pierwsza reakcja | Strict commit | Cała operacja |
|---|---|---|---|
| legacy 4, CPU ×4 | 188/281 → 39/68 | 137/147 → 254/307 | 197/312 → 341/409 |
| legacy 400, CPU ×4 | 3151/3462 → 29/59 | 3076/3399 → 3409/4315 | 3161/3478 → 3480/4470 |
| V2 4, CPU ×4 | 3106/4580 → 32/69 | 3056/4513 → 3433/3935 | 3117/4585 → 3584/4028 |
| V2 40, CPU ×1 | 3515/4526 → 30/33 | 3482/4492 → 3954/5387 | 3531/4542 → 3995/5430 |

Uzyskano wcześniejszą widoczną reakcję, **nie uzyskano skrócenia trwałego
zapisu**. Zarejestrowano pogorszenia median całej operacji; celowe oddanie
klatek wnosi dodatkowy narzut. Mała próba na współdzielonym hoście nie
rozstrzyga całej pozostałej różnicy — nie przypisujemy jej automatycznie
szumowi ani nie ukrywamy gorszych wyników. Nie ma podstaw do deklaracji
ogólnego przyspieszenia ani zamknięcia problemu płynności fizycznego Androida.

Legacy 400: średni koszt `entriesFor` przy powrocie do Treningu spadł
26,1 → 12,3 ms, przy otwieraniu edytora 23,7 → 7,3 ms. Cały powrót do Treningu
111/131 → 77/215 ms; edytor 150/192 → 105/346 ms. Mediany są lepsze,
**p95 tych akcji nie poprawiło się**. Sam `innerHTML` zajmuje kilka ms;
nie znaleziono powodu do przebudowy DOM w tym etapie. Długie zadania nadal
występują i są jawnie przedstawione w tabelach.

Kontrola V2 4 na main: bez dodatkowego archiwum pełny zapis wyniku
2049/4151 ms, z archiwum 4 MiB 3117/4585 ms. Cold odpowiednio 2696/2856
i 3930/4707 ms. Archiwum zwiększa koszt mostka przechowującego pełne źródło,
ale brak archiwum nadal pozostawia ponad dwusekundowy koszt modelu.
Nie jest to wyłącznie problem liczby sesji, kolektora ani renderowania.

## Zachowane funkcje i granice zmiany

Nie zmieniono `indexeddb.js`, schematu, transakcji, `strict`, CAS, walidatorów,
formatów lub implementacji backupu v1–v6, Google Drive, kolektora ani zapisu
szkiców. Nie usunięto danych ani archiwów, nie wykonano migracji/resetu.
Matrix CSS, układ ekranów, ćwiczenia, historia, plany, rotacja, snapshoty,
notatki i wyniki pozostają w istniejącej aplikacji. Dodany status korzysta
z istniejącego stylu toast; nie ma przebudowy interfejsu.

**Ograniczenie:** w trakcie commitu nawigacja i edycja są świadomie zablokowane.
To widoczny stan oczekiwania, nie pełna płynność podczas wielosekundowego
zapisu. Koszt walidacji/durability i długie zadania nadal istnieją. Na małym
profilu oddanie klatek może zwiększać czas całej operacji. Wyniki desktopowego
Chromium z CDP nie potwierdzają poprawy na fizycznym Androidzie, presji pamięci,
termiki, wolnego flash ani konkretnego historycznego profilu użytkownika.

## Projekt większego usprawnienia — do osobnego zatwierdzenia

Tego projektu **nie zaimplementowano** w tym PR. Do jednoczesnego korzystania
z ekranów podczas zapisu i usunięcia ciężkiej pracy z głównego wątku potrzeba
oddzielnego etapu, nie skrócenia walidacji:

1. Najpierw profilowanie na urządzeniu właściciela: identyfikator wydania,
   mały/duży profil, cold/warm, offline, pierwsza reakcja i commit, long tasks.
   Zabezpieczyć pełną kopię poza aplikacją; nie czyścić ani nie przenosić bazy.
   Przekazywać zagregowane czasy, bez wyników treningowych i surowych backupów.
2. Rozdzielić niezmienny ostatni zatwierdzony widok od kandydata operacji.
   Nawigacja czyta tylko zatwierdzony widok, a formularz pokazuje oczekiwanie.
   Publikacja nowej rewizji dopiero po istniejącej kompletnej walidacji,
   transakcji i CAS; przy konflikcie zachować szkic oraz wcześniejszy widok.
   Trzeba zaprojektować zachowanie anulowania, utraty karty, kliknięć w trakcie
   zapisu, zdarzeń innych kart i zakończenia sesji. Nie wolno po prostu
   przepuszczać nawigacji przez obecny mutowany obiekt `data`.
3. Oddzielnie ocenić worker dla pełnej serializacji/walidacji/hash/projekcji,
   z ograniczeniem liczby kopii dużych raw archiwów. Wynik workera nie może
   omijać kontroli rewizji, readback ani `tx.oncomplete`; przenoszenie i pamięć
   też wymagają pomiarów. Obecne zależności od `window` i asynchronicznej
   transakcji nie pozwalają bezpiecznie „dopisać await” jako takiej zmiany.
   Nie zmieniać schematu, formatu backupu ani kontraktu odzyskiwania bez
   osobnego projektu. Dopiero po dowodzie potrzeby rozważać różnicowy render.

Każdy etap wymaga before/after na tym samym profilu, p95, granic pamięci,
przerwania i quota, wielu kart/CAS, zachowania pełnych eksportów i szkiców,
upgrade PWA oraz regresji. Nie realizowano Issue #61 ani kolejnych funkcji v6.

## Weryfikacja

- `node --test tests/*.test.*`: **181/181 PASS**, 20,8 s.
- Pełne `python -m unittest discover -s tests -p 'test_*.py' -v`:
  **131 scenariuszy, 125 PASS, 4 FAIL i 2 ERROR**, 1034,8 s.
  Pięć problemów ujawniło założenie testów, że kliknięcie oznacza już
  zakończenie zapisu/dialogu. Dodano jawne oczekiwania na zakończenie operacji
  przed odczytem stanu lub zmianą handlera dialogu; zachowano wszystkie
  asercje danych. Szósty przypadek to domyślne 5 s na otwarcie po przywróceniu
  16 MiB źródła z zachowaniem preimage: ekran nadal pokazywał otwieranie bazy.
  Tylko dla tego otwarcia test integralności korzysta teraz z istniejącego
  w tym scenariuszu budżetu dużego pliku 90 s, bez zmiany domyślnego oczekiwania
  innych przypadków i bez uznania takiej latencji za akceptowalną wydajność.
- Celowane powtórzenie **wszystkich sześciu przypadków oraz kontrolnego testu
  dwukliku: 7/7 PASS**, 184,0 s. Zmierzony czas zamknięcia/ponownego otwarcia
  okna po dużym restore w tym pojedynczym przebiegu: **4032 ms**. To n=1,
  nie p95 ani dowód poprawy względem pierwszego przebiegu (>5 s oczekiwania).
  Nie powtarzano całej kosztownej regresji po poprawkach synchronizacji testów.
- Wszystkie **10 nowych scenariuszy PASS** w pełnym przebiegu: rzeczywista
  IndexedDB, opóźnione zakończenie, quota, abort i zamknięcie strony, dwuklik,
  blokada nawigacji, konflikt CAS z inną kartą, wznowienie nieukończonych kg/reps,
  offline oraz ukryty dokument i wstrzymane klatki.
- W dowodach „po” **60/60** startów/zapisów/zakończeń pokazało pierwszy sygnał
  przed `complete` transakcji historii; wszystkie te transakcje były `strict`.
- `node --check app.js`, `node --check sw.js`, kompilacja Python,
  `git diff --check`, `build_release.py --check` i normalny build: **PASS**.
  Lokalny release: `d6c8321415adba54817c6465`. Nie wdrożono go na telefon.
- Nie uruchamiano ręcznie Actions ani nie zmieniano CI/Billing. Status
  automatycznych kontroli finalnego commitu jest podany w PR; lokalna regresja
  nie jest deklaracją zaliczenia GitHub Actions.

Pełna regresja obejmowała także dotychczasowe odczyty/eksporty i przywracanie,
błędy/no-write, duże archiwa i ograniczony renderer dla kodeków, Drive z mockiem,
plany, rotację, zmiany daty, serie, L/P/drop/back-off, stare i nowe szkice,
ich odzyskanie po awarii renderera, kolektor tylko do odczytu, upgrade PWA
z wcześniejszych wydań, pracę offline i zachowanie kompletnego preimage.
Nie ograniczono testów integralności dla oszczędzania czasu. Nie testowano
produkcyjnego konta Drive, bazy użytkownika ani fizycznego Androida.
