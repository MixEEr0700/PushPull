# Dane na żądanie — Issue #90

Baza: `cbbf2d1` na main, po scaleniu A–E. Pixel 9: właściciel zgłosił
około 25 s przy wejściu do Dane i szybkie zapisy <1 s. Poniższa weryfikacja
używa wyłącznie izolowanych baz syntetycznych; nie wykonano pomiaru telefonu.

## Przyczyna i zmiana

Handler `data-tab=settings` czekał na `database.ensureFull()` przed zmianą
zakładki. To pełny odczyt, audyt checkpointów/legacy i archiwów, walidacja
modelu oraz semantyczne przeliczenie indeksu, a nie koszt samego panelu.
Profiler zapisuje przedziały inkluzywne: nie należy ich sumować.

Usunięto audyt z nawigacji. Podstawowy panel Dane, status Drive i PWA oraz
przyciski nie potrzebują pełnych danych. Nie wykonuje się audytu w tle
po samym wejściu. Lista zachowanych kopii ma jawny przycisk wczytania.
Plany, statystyki ogólne i porównanie podglądu v4 doczytują historię live,
żeby nie używać niepełnych liczników; nie potrzebują raw archiwów.

Pełny audyt jest wymagany przed eksportem JSON/v4/v5, wysyłką Drive,
operacjami przywracania/preimage, zapisem/aktywacją planu, starszą aktywacją
wersjonowania oraz odczytem zachowanych kopii. Nie zmieniono walidatorów,
writerów A–E, protokołu IndexedDB v2, CAS, readback i strict complete.
API eksportu nadal niezależnie wymaga audytu: sam przycisk nie przyznaje
niezweryfikowanym danym autorytetu.

Operacja pokazuje status przed kosztownym odczytem. Anulowanie albo
przejście do innej zakładki blokuje jej dalsze wykonanie: nie ma pobrania,
wysłania ani zapisu. Rozpoczęty audyt read-only może dokończyć się w pamięci;
nie dodano przerywania jego wewnętrznych transakcji ani zmian API bazy.
Kalendarz czeka na zweryfikowaną historię; nie renderuje częściowych danych.
Podczas audytu nowe mutacje UI są blokowane, a kolejka zachowuje kolejność.

## Pomiary

Chromium/Linux, CPU ×4, viewport 390×844, kontrolowane profile, offline po
instalacji PWA. Te same zachowane fixtures z etapu E; nie tworzono ponownie
historii ani konwersji. Trzy wejścia po restarcie strony dla każdej bazy,
każde z rzeczywistym eksportem JSON i pobraniem pliku. Nawigacja: zdarzenie
click do obserwacji nagłówka Dane, z narzutem Playwright; eksport: click do
zdarzenia pobrania. Nie są to pomiary dotyku do fotonu ani strict zapisu.
Pełny eksport po zmianie zawiera również audyt przeniesiony z nawigacji;
nie jest bezpośrednim porównaniem samego serializatora. SHA źródeł,
fixtures i plików wynikowych oraz wszystkie próby są w dowodach.

| Baza | Dane przed: mediana / max [ms] | Dane po: mediana / max [ms] | Eksport przed / po: mediana [s] |
|---|---:|---:|---:|
| empty | 563 / 640 | 51 / 58 | 0.30 / 0.99 |
| history40-raw4 | 14274 / 15858 | 45 / 54 | 9.81 / 24.68 |
| history40-escaped16 | 23592 / 24592 | 39 / 56 | 21.83 / 50.97 |
| history400-raw4 | 9872 / 10323 | 46 / 48 | 51.74 / 57.25 |
| history400-escaped16 | 11680 / 12411 | 43 / 48 | 70.03 / 79.97 |

Po zmianie wszystkie 15 wejść do Dane wykonało **zero odczytów IndexedDB**.
Max przy n=3 jest również empirycznym p95; nie jest stabilnym estymatorem
ogona rozkładu. Zachowano wszystkie próby. Puste/40/400 mają różne struktury
checkpointów, dlatego koszt pełnego audytu nie rośnie liniowo z liczbą sesji.

Przykład 40/raw4 przed zmianą: `openWriter` 13,191 s, w tym
`verifyEvidence` 7,322 s i `materialize` 3,894 s (przedziały inkluzywne).
To potwierdza koszt audytu przed nawigacją. [Pełne dowody](performance/issue-90-data-tab.json).

## Weryfikacja i ograniczenia

Nowe testy sprawdzają brak odczytów przy przełączaniu Dane/Trening offline
przy 360/390/412 px, doczytanie statystyk, odmowę eksportu JSON/v4/v5/Drive
przy uszkodzonym archiwum, anulowanie bez pobrania oraz jawne otwarcie
zachowanych kopii i pełny eksport. Pełna regresja obejmuje istniejące
scenariusze PWA/update/restart, plany, Drive mock, kopie/restore, szkice,
CAS, quota/abort i treningi. Nowe testy lokalne: **5/5 PASS** (14,323 s); produkcyjny build i spójność
SW: PASS. Końcowe statusy pełnego CI są podane w PR.

Nie zmieniono CSS Matrix, Google Drive, formatów kopii v1–v6 ani danych
urządzenia. Nie migrowano ani nie usuwano żadnej bazy. Duże eksporty,
pełne audyty i aktywacja planu z preimage nadal mogą trwać wiele sekund.
Synchroniczne fragmenty parsowania/serializacji mogą opóźnić reakcję na
anulowanie; przycisk nie obiecuje natychmiastowego zakończenia odczytu.
Cel tego PR to szybkie wejście do panelu, nie przebudowa pełnych audytów.

Odbiór Pixel 9: po aktualizacji kompletnego PWA uruchomić ponownie offline,
wejść Dane 10 razy, sprawdzić szybkie wyświetlenie statusu PWA i przycisków;
następnie osobno zmierzyć eksport, anulowanie, pobranie zachowanej kopii,
plany/statystyki i Drive na koncie testowym. Sprawdzić zapisy <1 s bez
regresji i porównać pełną kopię danych przed/po. Nie czyścić bazy.

Po pomiarach poprawiono wyłącznie zakończenie anulowanej operacji: render
resetuje wybór pliku, aby ponowne wskazanie tego samego pliku działało.
Odtworzono błąd testem i dodano regresję. Zmiana nie dotyczy zmierzonych
ścieżek zwykłego wejścia i nieanulowanego eksportu.
