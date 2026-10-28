# Issue #99 — kompaktowy edytor serii

Baza: `main` po PR #98, `42fc1010092c7adea0ad3520a493f7600d9b1bdc`. Osobna gałąź `compact-series-issue-99`, jeden PR. Nie obejmuje Issue #94, wdrożenia ani scalania.

## Zmiana interfejsu

- Podstawowa seria: numer, powtórzenia, kg, kosz. Bez powielania nazwy, celów, tempa, RIR, back-off i dodatkowych ramek. Parametry i role pozostają w karcie, planie i zapisach.
- Dropset: główna seria z numerem, poniżej wcięte segmenty `+1`, `+2` itd. Własne pola i kosz każdego segmentu, przycisk dodawania segmentu. Usunięcie serii usuwa jej segmenty ze szkicu, nie z historii. Dodatkowe segmenty zachowują kolejność i ID.
- Zweryfikowana, równa para L/P: jeden wspólny wiersz, jak przy zwykłej serii. Zmiana pola aktualizuje wartości **dwóch istniejących rekordów**, bez tworzenia kolejnej pary. Zwykły widok nie ma przełączników rozdzielania/scalania ani dwóch kart stron.
- Dodanie serii L/P dodaje jedną pustą parę z niezależnymi ID. Kosz usuwa całą parę po potwierdzeniu, również pierwszą lub ostatnią. Można pozostawić pusty, odtwarzalny szkic; nie można zapisać go jako wyniku. Po restarcie nie wracają usunięte serie. Dotyczy to także starego edytora prostych serii.
- Grupy zachowują członków i przepisane rundy. Można ponownie dodać usuniętą przepisaną rundę; przycisk nie tworzy nieobsługiwanych dodatkowych rund/referencji.

Kontrolki mają co najmniej 44 px wysokości, pola 16 px tekstu. Sprawdzono szerokości 360/390/412 px i zrzuty zwykłych L/P oraz dropsetu. Zrzut DOM/headless nie jest odbiorem na Androidzie.

Issue #99 zawiera tekstowy układ `1 [powt.] [kg] [usuń]`; nie zawiera oddzielnego załącznika graficznego. Nie deklarujemy porównania z nieudostępnionym obrazem.

## Strony, konwencja ciężaru i stare dane

Wspólny wiersz jest tylko sterowaniem formularzem. Nie zmienia `performance`, projekcji serii ani obliczeń modelu podczas samego wyświetlania. Oparciem pary są istniejące ID i kontekst set/group/round oraz zasady odtwarzania kolejności z PR #98; nie data, sequence ani podobieństwo wartości. Dodatkowo odrzucono automatyczne parowanie zduplikowanych przepisanych lewych stron.

Zwykły wspólny wpis wymaga:

1. Ustalonej pary dwóch istniejących stron.
2. Równych wartości i pełnej struktury segmentów oraz tych samych metadanych poza identyfikatorami/oznaczeniem strony.
3. Jawnej konwencji `kg` per implement lub wskazania urządzenia, stosowanej osobno do każdego faktycznego rekordu strony.

Tonaż nadal jest sumą rzeczywistych segmentów. Dla trzech par `10 × 24 kg`, z potwierdzonym znaczeniem kg na stronę, sześć rekordów daje **1440 kg**, nie 2880 kg. Nie dodano uniwersalnego mnożnika ×2. Nie podzielono dawnych kg przez dwa. Pojedynczy dawny zapis nie staje się automatycznie dwoma zapisami.

Asymetria, brak strony, nieustalona para, różne metadane/segmenty albo `combined`/nieznana konwencja pokazują **widoczny wyjątek** z rzeczywistymi wartościami L/P i ostrzeżeniem. Szybkie pola są wtedy tylko do odczytu; nie mogą zastąpić wyjątków wspólnym wpisem. Szczegóły pozwalają niezależnie poprawiać rzeczywiste strony. Przy nieustalonej parze zapis jest blokowany do ręcznego uporządkowania; dodanie brakującej strony tworzy tylko puste pola po potwierdzeniu.

Dla asymetrycznej, ustalonej pary z odpowiednią konwencją można jawnie wybrać „Użyj L dla obu” albo „Użyj P dla obu”. Dodatkowe potwierdzenie opisuje zastąpienie wartości. Przy różnej strukturze/metadanych operacja odmawia działania: nie skraca dłuższej sekwencji i nie wybiera zwycięskich metadanych. Anulowanie nie zmienia danych. Równe wartości po ręcznej korekcie można zamknąć przyciskiem „Gotowe”; wraca zwykły wspólny wiersz. Stare `sidePairs.linked` w szkicu nie jest samodzielnym upoważnieniem do nadpisania asymetrii.

`combined` zachowuje dotychczasową semantykę zapisanych rekordów i sumowania. Interfejs nie ustala za użytkownika, czy stare kg oznaczały jedną czy obie strony. Takie dane nadal mają szczegóły stron i wymagają świadomej korekty; nie są automatycznie przeliczane. Różnice samego zapisu tekstowego liczb mogą konserwatywnie pokazać wyjątek, mimo podobnego znaczenia liczbowego.

Dla nowego, opcjonalnie jednostronnego wykonania z odpowiednią konwencją zachowano jawną deklarację wykonania obu stron w zwiniętym „Sposób wykonania”. Nie jest dostępna do powielania istniejącego zatwierdzonego wyniku ani dla kg łącznie/nieznanych. Nie zmienia historii.

## Zachowane mechanizmy

Bez zmian: schemat i protokół IndexedDB v2, CAS, readback, rzeczywisty `strict complete`, walidacja wyników, backupy v1–v6 i Drive. Nie zmieniono `performance.mjs`, statystyk, modelu planów, rotacji ani tonu Matrix poza edytorem serii.

Zachowano szybkie pola, cztery przyciski pod formularzem, własne notatki i źródłowe instrukcje, ostatni wynik, historię, dodawanie/usuwanie i indywidualną korektę rzeczywistych serii. Wspólna zasada skracania identycznych wyników z PR #98 nadal obsługuje karty i historię. Nie zmieniono liczby ani wartości dawnych wyników dla uzyskania skróconego tekstu.

Zakończenie ze szkicami korzysta z dotychczasowego kontrolera: utrwalenie każdego wyniku, potwierdzenie zakończenia sesji, następnie sprzątanie właściwych tokenów. Błędy nie usuwają szkiców. Wewnętrznie rozszerzono wyłącznie odzyskiwanie pustego lokalnego edytora prostych serii; współdzielony walidator dowodów i kodeki v6 pozostały bez zmian.

## Testy

Nowe testy Node obejmują 1/2/3 serie, równe L/P i tonaż 1440 kg, segmenty drop 1/2/3, identyfikatory, usunięcie pierwszej/ostatniej serii, pusty szkic, nieznaną/łączną konwencję, asymetrię, metadane, brak/duplikaty stron, stare pole wspólne po zmianie stanu i rundy grup. Renderowanie ma asercje niezmienności wszystkich źródłowych rekordów.

Testy Chromium korzystają z izolowanych syntetycznych baz, rzeczywistego IndexedDB i kontrolera szkiców. Sprawdzają wspólny wpis oraz sześć rzeczywistych stron, niezależne wyjątki, anulowanie/potwierdzenie korekty, przerwane liczby, usuwanie do zera i restart, elastyczne dropsety, historię, snapshoty, kg łącznie i brak dodatkowego mnożenia, zakończenie ze szkicami offline oraz aktualizację PWA bezpośrednio z PR #98 ze starym asymetrycznym szkicem i niezmienionymi ID.

Dawne testy, które tworzyły asymetrię przez obecnie usunięty zwykły przełącznik, otrzymały jawnie oznaczony syntetyczny stan starego edytora. Dalsza edycja, utrwalanie, restart i wszystkie asercje danych/tonaży pozostają rzeczywiste. Historyczne wydania w testach PWA nadal wykonują swój oryginalny kod.

Wczesne błędy testowe: odczyt alertu przed jego asynchronicznym nadejściem; syntetyczny szkic nieprzekazany do kontrolera trwałych szkiców; fixture planu jednostronnego z celem bez wymaganego `side: each`. Poprawiono synchronizację/przygotowanie danych, bez osłabiania asercji integralności lub walidatora planów.

Lokalny pełny Node: **235/235 PASS**. Po dodaniu dwóch kolejnych scenariuszy plik Issue #99: **9/9 PASS** (siedem było już w pełnym przebiegu). Build produkcyjny i zgodność hashy workera: PASS; bez wdrożenia.

Pełny lokalny Chromium/PWA: **227 scenariuszy, 4 początkowe niepowodzenia**. Dwa dotyczyły dawnych interakcji niezależnych L/P (statystyki 550 kg i wznowienie po zabiciu renderera); po zmianie przygotowania starego szkicu oba testy przeszły, bez zmiany asercji danych i tonażu. Trzeci test porównywał prawdziwy `Event.timeStamp` z zaokrąglanym zegarem Playwright: różnica 1 ms naruszała kolejność. Test używa teraz rzeczywistego zegara, z tymi samymi asercjami kolejności, opóźnienia publikacji i `strict`; **3/3 PASS** razem z testami kontrolera workera.

Czwarty przypadek: kontroler workera w teście podglądu v4 nie przejął strony w 30 s; osobne uruchomienie **PASS**. Test wcześniej przeładowuje fixture podczas pierwszej instalacji. `serviceWorker.ready` potwierdza aktywną rejestrację, nie kontrolę już załadowanego dokumentu. Przygotowanie testu wykonuje teraz kontrolowaną nawigację po `ready`, a następnie nadal wymaga rzeczywistego kontrolera przed przejściem offline. Bez zwiększania timeoutu, zmiany workera produkcyjnego lub asercji niezmienności/odtwarzania. Nie przedstawiamy tego jako naprawy aplikacji; dokładnego przebiegu pojedynczej utraconej kontroli nie zarejestrowano. Nowe testy pustego edytora legacy, konwencji kg łącznie i aktualizacji bezpośrednio z PR #98 przeszły osobno. Końcowy komplet z rozszerzonymi testami mobilnymi wykonuje wymagany workflow PR; jego wynik i dokładny commit podano w PR. Nie przedstawiamy początkowego przebiegu 227 jako PASS. Końcowe lokalne testy nowego edytora (w tym 360/390/412 px) i pełne trzy scenariusze lokalnych kopii v4: **9/9 PASS**, również po doprecyzowaniu kontrolowanej nawigacji.

## Pomiary przed/po

Chromium **154.0.8037.57**, Linux, 390 px, CPU ×4, izolowane syntetyczne profile. Baza przed: `42fc101`; po: hashe końcowych plików w [pełnych próbkach](performance/compact-editor-99.json). Wszystkie zmierzone pliki produkcyjne porównano z końcowym drzewem — zgodne. **n=3 na wariant, p95 jest maksimum**, łącznie 36 prób. Uruchomiono szeregowo po zakończeniu lokalnych testów. Bez odrzucania wolniejszych prób.

Każda para wariantów korzysta z identycznych fixture 4 sesji lub 40 sesji V2 + raw 4 MiB i zachowanych checkpointów (plik fixture około 50 MiB). Zegarem trwałości jest `Event.timeStamp` natywnego zdarzenia `complete` transakcji `strict`, z walidacją/CAS/readback w tej samej ścieżce. Obserwatory działają tylko w niezmiennych artefaktach benchmarku; nie dodano ich do aplikacji. Toast nie jest zegarem trwałości.

| Baza / serie | Przed: mediana / p95 (ms) | Po: mediana / p95 (ms) |
| --- | --- | --- |
| 4 sesje / zwykłe | 281.1 / 293.7 | 259.8 / 332.3 |
| 4 sesje / drop | 213.3 / 213.3 | 272.0 / 278.4 |
| 4 sesje / L/P | 269.5 / 420.9 | 251.9 / 288.3 |
| 40 sesji + raw / zwykłe | 342.4 / 439.6 | 270.9 / 285.1 |
| 40 sesji + raw / drop | 337.2 / 362.0 | 322.6 / 397.7 |
| 40 sesji + raw / L/P | 352.2 / 395.4 | 371.4 / 506.1 |

Nie ma równomiernego przyspieszenia zapisu: mały drop i duże L/P są w tej próbie wolniejsze, inne warianty szybsze. Maksymalne p95 po zmianie to **506,1 ms**; mała próba nie rozstrzyga regresji kilkudziesięciu ms ani celu na Androidzie. Zachowano także surowe markery etapów. Przykładowo najwolniejsze duże L/P ma 52,6 ms do wejścia do API, 351,0 ms przygotowania przed transakcją i 102,5 ms od otwarcia transakcji do native complete. Nie zmieniono protokołu ani nie obchodzono zabezpieczeń dla uzyskania lepszego wyniku.

| Edytor: 3 serie/pary | Wysokość szczegółów przed → po | Pola przed → po | Elementy DOM przed → po |
| --- | --- | --- | --- |
| Zwykłe | 218.0 → 206.0 px | 6 → 6 | 19 → 25 |
| Dropset (2 segmenty) | 687.8 → 494.0 px | 12 → 12 | 46 → 49 |
| L/P | 1265.6 → 206.0 px | 12 → 6 | 73 → 28 |

L/P skrócono z około 1266 do 206 px bez usunięcia któregokolwiek z sześciu rekordów stron. Przy zwykłych/drop ikonki SVG zwiększają liczbę elementów DOM mimo zmniejszenia wysokości. Otwarcie edytora do gotowego DOM (mediana/p95) wynosi po zmianie:

- zwykłe: 5.1/5.5 ms (przed 5.0/8.7 ms).
- drop: 5.2/6.0 ms (przed 5.6/5.8 ms).
- L/P: 6.1/6.3 ms (przed 4.8/6.5 ms).

To gotowość DOM, nie fizyczny paint/wyświetlacz. Wszystkie próby potwierdzają poprawne 720 kg dla trzech zwykłych serii oraz 1440 kg dla sześciu segmentów drop lub trzech par L/P; brak dodatkowego mnożenia. Orakle potwierdzają niezmienione dawne wyniki, snapshoty, plan i wszystkie archiwa oraz usunięcie właściwego szkicu dopiero po zatwierdzeniu.

Odczytany heap z fixture i kopiami do orakli: mała baza przed **46,3–47,7 MiB**, po **46,2–47,3 MiB**; duża przed **508,0–552,3 MiB**, po **262,3–548,7 MiB**. Nie jest to peak RAM/RSS ani koszt samej aplikacji. Duży zakres zależy m.in. od GC i zachowanych pełnych kopii porównawczych; nie deklarujemy zmniejszenia pamięci aplikacji na tej podstawie. Pełny odczyt archiwów/orakle są poza zegarem zapisu.

Odtworzenie: `python scripts/measure_compact_editor.py --fixtures <katalog syntetycznych fixture protokołu v2> --output <nowy katalog> --repeats 3 --cpu 4`. Użyto istniejących fixture A–E `small` i `history40-raw4`, bez ponownego generowania zakończonych pomiarów. SHA-256 fixture są w JSON. Można je wygenerować w izolowanym profilu istniejącymi helperami `artifact` / `fixture(..., version=2)` w `scripts/measure_incremental_write.py`, odpowiednio 4/40 sesji i 0/4 MiB raw. Nie używać profilu użytkownika. Nie uruchamiać pomiarów równocześnie z testami.

## Ograniczenia i odbiór telefonu

Brak fizycznego testu Pixel 9, konta Google Drive i natywnej klawiatury Androida. Segmenty drop można dodawać dla serii z istniejącą definicją drop w planie; dodatkowa seria bez referencji do przepisanego celu pozostaje zwykłą serią, zgodnie z dotychczasowym walidatorem. Nie wymyślamy nowych definicji drop/rund w danych. Wspólna edycja świadomie nie rozstrzyga nieznanych konwencji. Nie przebudowano protokołu wielu kart ani mechanizmu zapisu. To zmiana sterowania, nie migracja danych.

Po przeglądzie i wdrożeniu przez właściciela: sprawdzić release, 1/2/3 serie, pierwszy/ostatni kosz, segmenty dropsetu, trzy pary L/P i tonaż, odtworzenie szkicu po zamknięciu offline, widoczny stary asymetryczny wynik i anulowanie jego korekty, zapis/zakończenie, historię/statystyki. Nie resetować danych. Zmierzyć większą próbę zapisu; syntetyczne p95 z małej próby nie jest p95 urządzenia.
