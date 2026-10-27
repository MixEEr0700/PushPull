# Rozruch P0 na bazie etapu C — Issues #73, #75, #82

Praca bazuje na `5b735e4` z PR #85. PR #83–#85 nie zostały scalone.
Nie powtórzono zakończonych 336 pomiarów zapisu ani diagnostyki limitu
pojedynczego rekordu v1 dla 400 sesji. Nowe pomiary dotyczą zmienionej ścieżki
rozruchu i kontroli regresji zapisu. Wyłącznie izolowane dane syntetyczne.
**Nie wykonano pomiaru na fizycznym Pixelu 9.**

## Przyczyna i zakres minimalnego odczytu

Stary v1 sprawdzał całe źródło, jego digest oraz source-backed model v3.
C na każdym starcie dodatkowo pobierał checkpoint v1, ponownie uruchamiał
jego pełny walidator, parsował wszystkie zachowane obiekty, a przy walidacji
bieżącego źródła budował jeszcze jedną pełną kopię v3 wraz z raw i checksum.
To praca zależna od wielkości historii i zagnieżdżonych archiwów, nawet gdy
archiwum nie jest potrzebne do żadnej operacji treningowej.

W pierwszej serii CPU ×4 renderowanie zajmowało 17–40 ms, a pełny start
z 40 sesjami i archiwum 4 MiB: v1 7,96–8,78 s, C 13,04–14,16 s.
Przy 16 MiB escaped: v1 12,19–12,52 s, C 33,91–37,54 s.
Jednorazowa konwersja C: odpowiednio 44,79 i 113,84 s. Nie należy dodawać
czasów zagnieżdżonych profilerów: są to przedziały inkluzywne.

Nowy start sprawdza root/marker, liczność i identyfikatory zachowanych
rekordów, pełny indeks Merkle oraz wszystkie obiekty bieżącego grafu.
Pobiera bieżący plan, sesje, wyniki, katalog i niezmienne modele snapshotów.
Nie pobiera raw archiwów, checkpointów ani nieużywanych dawnych obiektów.
Modele identyczne bajtowo nadal współdzielą wyłącznie głęboko zamrożone
struktury. Statystyki są obliczane dopiero po otwarciu odpowiedniego widoku.

**Granica zakresu:** natywne wyniki i snapshoty historii nadal są potrzebne
przy starcie do zatwierdzonych kart ostatniego wyniku, porównania kontekstu
oraz wieku zmiany, a także wykrycia globalnych kolizji identyfikatorów przed
zapisem. Nie zastąpiono ich pustymi tablicami ani niepełnymi porównaniami.
Dalsze ograniczenie tego grafu wymagałoby osobnego indeksu kontekstu/ID.

Pełny domyślny reader API pozostaje audytem całej bazy. Tylko UI żąda widoku
treningowego. Synchroniczny eksport niepełnego widoku odmawia; Dane,
pełny eksport, preimage i przywracanie wymagają audytu zawartości archiwów
oraz checkpointów. Uszkodzenie nieczytanego raw nie blokuje treningu,
ale uniemożliwia wydanie go jako zweryfikowanej kopii. To jawna granica,
nie obietnica audytu fizycznego całej bazy przy każdym zapisie wyniku.

## Integralność i bezpieczna aktualizacja

- Root v2 ma dodatkowe, hashowane pole `allocation`: `bytes`, `records`,
  `maxObjectBytes`. Dotyczy wszystkich zachowanych obiektów, checkpointów
  i indeksów. Pełny audyt przelicza je i wymaga dokładnej zgodności.
  Zapis wyniku aktualizuje je razem z root w tej samej strict transakcji.
- Stary root C bez tego pola jest nadal odczytywany. Pierwsze otwarcie przez
  UI wykonuje pełny audyt i jednorazowy strict CAS małego root, z readback.
  Nie konwertuje ponownie historii i nie zmienia schematu/stores IndexedDB.
  Kolejne starty nie zapisują nic do bazy.
- **Zgodność kodu:** starszy reader C odrzuca nowe pole root (fail closed).
  Należy aktualizować przez sprawdzony komplet plików PWA. Rollback wymaga
  readera rozumiejącego oba kształty root; samo przywrócenie starego JS nie
  jest zgodnym rollbackiem. Nie obniżamy wersji ani nie resetujemy bazy.
- Zwykłe zmiany sesji, daty, planu i notatek przebudowują zwalidowany graf
  live z zachowaniem dokładnych referencji archiwów i checkpointów. Sprawdzają
  CAS root/marker/liczność i wymagane rekordy, zapis/readback i strict complete,
  następnie niezależny odczyt grafu. Nie przeniesiono przetwarzania raw na
  pierwszy przycisk Rozpocznij. Import i preimage pozostają pełnymi operacjami.
- Konwersja v1 pobiera jeden snapshot źródła i raz go waliduje przed
  przygotowaniem. Nie otwiera wcześniej drugiego pełnego readera v1.
  Dowody ponownie wykorzystuje tylko dla identycznych, głęboko niezmiennych
  danych; natywny readback i pełny oracle konwersji pozostają obowiązkowe.
  Hash/rozmiar niezmiennego checkpointu nie wymaga kolejnej serializacji
  przy każdym wykorzystaniu tego samego obiektu w pamięci.
- Przygotowanie, atomowa aktywacja, checkpoint, pending/resume i blokada
  odtworzenia starszego v1 po utracie aktywnego root pozostają zachowane.
  Quota/abort nie powodują automatycznego usuwania danych.

## Wyniki końcowe

Linux/Chromium 154, AMD EPYC 9V74, ograniczenie CPU ×4, viewport 390×844.
Zwykłe cold/warm uruchomienia po instalacji PWA odbywały się offline.
`readyMs` to obserwacja gotowego widoku przez Playwright; po zmianie dodatkowy
mark `pushpull-training-ready` powstaje po renderze i rejestracji handlerów.
Mark nie mierzy czasu dotyku do fotonu. Mediany obserwacji mają po zmianie
n=6 (3 proces-cold + 3 warm); bazowy profiler v1/C ma n=2 dla zwykłych startów.

| Historia / raw | v1: obserwacja widoku | C: obserwacja widoku | Po: obserwacja widoku | Po: mark gotowości mediana / p95 |
|---|---:|---:|---:|---:|
| 0 sesji | — | — | 1,116 s | 0,571 / 0,605 s |
| 4 sesje | 1,986 s | 2,061 s | 1,278 s | 0,715 / 1,529 s |
| 40 / 4 MiB | 8,209 s | 13,598 s | 1,853 s | 1,487 / 1,953 s |
| 40 / 16 MiB escaped | 12,356 s | 35,725 s | 1,691 s | 1,284 / 1,390 s |
| 400 / 4 MiB | brak legalnej dużej reprezentacji v1 | 12,645 s* | 6,771 s | 6,532 / 6,868 s |
| 400 / 16 MiB escaped | brak legalnej dużej reprezentacji v1 | 14,909 s* | 7,093 s | 6,818 / 10,277 s |

\* Bazę 400 porównano z istniejącym pomiarem wzrostu v2 na tym samym modelu
CPU i tych samych zachowanych fixtures. Wykorzystano ukończone wyniki;
nie powtarzano nieudanego tworzenia ogromnego rekordu v1. Instrumentacja
tej starszej serii różni się od profilera etapów; nie jest to precyzyjna
izolacja różnicy pojedynczej instrukcji. Dowody: istniejący raport etapu C
oraz nowe `startup-p0-growth.json`.

Maksimum próbkowanego heap JS przy zwykłym starcie 40: C 484,0 / 532,6 MiB,
po zmianie 14,9 / 14,8 MiB (raw 4 / escaped 16). Dla 0/4 sesji: 5,2/6,4 MiB,
dla 400: 77,9/84,3 MiB. To **nie** RSS, całkowity RAM procesu ani gwarantowany
peak: sampler nie widzi wszystkich przejściowych alokacji wewnątrz długiego
zadania. Pełny import/eksport nadal wymaga osobnego większego budżetu.

Jednorazowa konwersja v1→v2: C 44,787 → 25,628 s (40/4),
113,844 → 55,384 s (40/16). Próbkowane maksima heap: 977,4 → 335,2 MiB
oraz 1026,9 → 612,6 MiB. Certyfikacja istniejącego root C bez `allocation`
trwała 21,288 / 29,455 s; nie jest zwykłym startem i nie należy jej ukrywać
w średniej. Dane i checkpoint nie zostały usunięte.

| Kliknięcie → strict complete wyniku | mediana | p95 | max | n |
|---|---:|---:|---:|---:|
| C, 40/4, kontrola na tym samym hoście | 156,8 ms | 519,7 ms | 519,7 ms | 8 |
| Po, 40/4 | 114,7 ms | 210,7 ms | 230,0 ms | 24 |
| Po, 40/16 escaped | 103,1 ms | 189,1 ms | 224,7 ms | 24 |

Pierwsze cztery wyniki w każdym z 3 profili są nowe, kolejne cztery są
korektami. Wszystkie 48 zapisów zachowały hashe oryginalnej historii,
snapshotów, katalogu i archiwów; niezależny pełny reader/audyt przeszedł.
Zegar pochodzi z natywnego `oncomplete`, przed publikacją Promise, z
`durability: strict`; osobno zapisano `event.timeStamp` i pełne otwarcie UI.
Nie wykorzystano toastu jako potwierdzenia trwałości.

**Rozpoczęcie nowej sesji:** C 27,765 s do strict complete / 43,562 s do UI
(jedna próba 40/4). Po zmianie 3,045–3,717 s do strict complete /
3,680–4,477 s do UI (6 prób, oba archiwa). To nadal przekracza 2 s.
Nie czyta raw; koszt pozostał w operacji całego grafu live i jej readback.

**Werdykt odbioru: częściowa poprawa P0, nie pełne osiągnięcie celów.**
Zwykły start 40 zbliżył się do 2 s, zapis przyrostowy zachował duży zapas
w badanych próbach. Reakcja całego interfejsu ≤1 s, nowa sesja ≤2 s i
start 400 ≤2 s nie są potwierdzone; część pomiarów wprost ich nie spełnia.
Żaden pomiar nie potwierdza jeszcze celu na fizycznym Pixelu 9.

### Dowody i odtworzenie

Nowe pliki `docs/performance/startup-p0-{before,after,growth,certification}.json`
zawierają wszystkie próby, rozdzielone przedziały, liczniki native IDB,
long tasks, heap, identyfikatory wydań oraz SHA-256 źródłowych raportów.
Przedziały są inkluzywne, a sumy opóźnień równoległych requestów nie są
czasem ściennym. Pliki `startup-p0-writes-{before,after}.json` zachowują
każdy pomiar wyniku, natywne znaczniki i hashe oracle.

Pomiar implementacji: `c580d694a43dc9de5299b16ceb46a5cd8439df0d`,
produkcyjny artifact tej wersji `814bfedc899b4ba9a65347b9`.
Końcowy przegląd dodał odmowę gettera `model` dla niepełnego widoku
oraz atomowy dump wszystkich stores w ścieżce odzyskiwania, także tabel v1
w stanie pending v2. Żadna z tych zmian nie dotyczy mierzonej ścieżki
normalnego startu/zapisu. Test wyniku wymusza rzucanie
wyjątku przy dostępie do `model`, `value` i `export`, a więc potwierdza,
że ścieżka wyniku ich nie wykonuje. Końcowy artifact z tą blokadą:
`0399ce3be8754f3635ba52cf`. Nie publikowano żadnego artifactu na telefon.

Pomiary należy uruchamiać szeregowo, bez regresji w tle. Fixtures są
syntetycznymi plikami utworzonymi wcześniej przez
`scripts/measure_incremental_write.py`; nie dodaje się wielkich dumpów bazy
do repozytorium. Profiler `scripts/measure_startup.py` przyjmuje katalog
fixtures, ref, suffix i liczbę powtórzeń; `scripts/measure_fast_start_writes.py`
używa zachowanego capture C oraz odpowiadającego mu hasha źródła v1.
Duże wiadomości CDP są przesyłane porcjami 1 MiB wyłącznie przez harness;
format bazy i backupu nie jest w ten sposób zmieniany.

### Regresja

Node: **204 PASS**. Lokalny pełny Chromium/PWA: 172 przypadki, 171 PASS
oraz 1 timeout oczekiwania na controller SW podczas zmieniania plików
wydania. Po zamrożeniu plików ten przypadek przeszedł wraz z 14 innymi
przypadkami celowanymi. Dodatkowy nowy test błędu preloadu: PASS.
Nowy test wymuszonego quota w pending v2 wykazał pominięcie tabel v1 w
pobieranej diagnostyce; poprawka odczytu wszystkich stores w jednej
transakcji przeszła wraz z testem uszkodzonego live i odtwarzania preimage.
W ten sposób zweryfikowano 174 różne scenariusze; nie ukryto timeoutu
pierwszego przebiegu. Końcowa blokada gettera ma osobną kontrolę celowaną.
Pełny wymagany wynik GitHub Actions dla końcowego HEAD jest w checks PR.

Zakres: natywna IndexedDB/CAS, quota/abort, odrzucenie błędnego readback,
wiele kart, podwójne kliknięcie, brak aktywnego root, pending/resume konwersji,
restart szkicu, backupy/odtwarzanie, duże archiwa (także 65 MiB v5), stare
wersje PWA i aktualizacje, tryb offline, źródłowa para A/B, V2/V3, plany,
historia, statystyki, notatki i build produkcyjny. Nie osłabiono istniejących
asercji; zmieniono jedynie marker testowej ekspozycji handle po dodaniu
jawnej opcji odczytu treningowego.

## Następny krok dla pozostałych opóźnień

Dalszego zysku nie należy szukać w kolejnym pełnym przetwarzaniu historii.
Potrzebny jest jawny indeks kontekstów treningowych i globalnych ID wyników,
wiązany z root, wraz z odczytem samych wymaganych ścieżek Merkle.
Czytnik otwierałby plan/aktywną sesję i dokładne ostatnie wyniki kontekstu;
pozostałe snapshoty oraz wykresy byłyby uwierzytelniane po otwarciu widoku.
Nie można zgadywać wieku zmiany ani sprawdzać kolizji ID tylko w bieżącej
sesji. Pełny audyt musi porównywać nowe indeksy z całym źródłem.

Osobne polecenie startu/końca sesji powinno atomowo aktualizować tylko
sesję, snapshot, aktywny wskaźnik, katalog i wymagane indeksy, zamiast
przebudowywać cały graf live. Powinno używać tego samego wzorca CAS,
readback i strict complete co wynik. Bezpieczna aktualizacja wymaga
jednorazowego zbudowania/zweryfikowania indeksów, zachowania checkpointu,
obsługi pending/abort i readera dla obu reprezentacji. To konkretna
następna zmiana kontraktu wewnętrznego; **nie została ukryta w tym PR**.

Przed odbiorem telefonu: zachować pełny backup, odnotować wersję wydania,
Androida i Chrome, zamknąć pozostałe karty przed aktualizacją PWA, oddzielić
pierwszą konwersję od kolejnych uruchomień i wykonać serię nowych wyników
oraz korekt offline. Istniejący `scripts/pixel_write_probe.js` pozwala
obserwować potwierdzenie trwałego zapisu. Żadnego resetowania danych w celu
uzyskania korzystniejszego czasu.

## Zachowane funkcje i granice odbioru

Matrix/CSS/ikony/identyfikator PWA, rotacja, start/koniec, sesje, wyniki,
serie, notatki, wersje planów, snapshoty, historia, szkice i ich konflikty,
komunikaty oczekiwania z #78, CAS i potwierdzenie dopiero po strict complete.
Kontrakty plików v1–v6, eksport, dotychczasowe przywracanie oraz Google Drive
nie są zmieniane. Brak nowego produkcyjnego przywracania v4/v6 i Issue #61.

Cele Pixel 9 (reakcja ≤1 s, trening ≤2 s, zapis p95 <1 s) wymagają osobnego
odbioru na urządzeniu. CPU ×4 na Linuksie nie symuluje Androida, flash ani
zarządzania pamięcią. Pierwsze uruchomienie z v1 i certyfikację starego root C
raportujemy oddzielnie od zwykłego startu; nadal mogą trwać wiele sekund.
Pełny eksport/import oraz wejście do archiwów wymagają pamięci na pełny
odczyt i są proporcjonalne do danych. Nic nie zmienia limitów plików v5,
limitu pojedynczego rekordu v1 ani limitów protokołu. Nie wolno usuwać danych
ani podnosić tych limitów w celu uzyskania korzystniejszego benchmarku.
