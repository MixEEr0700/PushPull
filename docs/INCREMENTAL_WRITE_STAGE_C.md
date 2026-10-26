# Issue #82 C — Matrix i zapis przyrostowy

Zależności przeglądu: A / PR #83, B / PR #84. Gałąź wywodzi się z aktualnego
`main` `4647511`, po scalonych #79/#81. Nie zmieniono Matrix CSS, ikon, układu
ani kontrolek treningu. Zachowano blokadę/pending z #78.

## Granice zapisu

Istniejące formularze tworzą jeden odłączony wpis. `persistResult` przekazuje
CAS context do `saveResult`; nie publikuje wpisu ani nie zmienia całej historii
przed complete. Po natywnym strict complete stosuje mały ack i potwierdza tylko
pasujący ticket szkicu. Błąd zachowuje poprzedni wynik i szkic. Katalog ma osobny
mały getter; render nie pobiera pełnego eksportu po zmianie rewizji.

Publiczne dane zachowują dotychczasowy kształt. Edytowalny plan/formularze są
odłączone, a modele historycznych snapshotów głęboko zamrożone. Powtarzane
identyczne modele mogą być współdzielone bez możliwości wzajemnej mutacji.
Pełne kopie nadal używają istniejących kodeków v1–v6. Kopia v3 powstaje na żądanie
z pełnego źródła; nie zapisujemy pozornie aktualnego `training-model-v1`.
Eksport pliku wykonuje pełny audyt, również niezmienionych archiwów.

Start/zakończenie sesji, plany, notatki i pełny import są na tym etapie wolniejszymi
operacjami bulk **protokołu 2**. Nie przełączają writera na v1. Zachowują pełną
walidację, CAS, readback i strict complete. Duży stan jest przygotowany przed
udostępnieniem UI, nie dopiero w pierwszym zatwierdzeniu wyniku. Nie twierdzimy,
że wszystkie operacje bulk lub uruchomienie spełniają limit czasu wyniku.

## Aktualizacja, awaria i odzyskiwanie

Przy uruchomieniu v1 przechodzi pełny odczyt, weryfikację i przygotowanie
konwersji przed krótkim versionchange. Oryginalne stores/model pozostają jako
checkpoint. Konwersja ponownie sprawdza dokładne źródło w strict transakcji.
Pending po quota/abort odczytuje aktualne stores v1 i wznawia konwersję; nie
uruchamia starego writera w bazie v2. Konkurujące nowe karty odczytują aktualny
root; nie nadpisują go starszym przygotowaniem. Zmiana localStorage starej
aplikacji nadal blokuje zwykły zapis i pozwala zabezpieczyć obie historie.

Stary JS otwierający DB version 1 po aktualizacji otrzymuje VersionError, bez
resetu. SW weryfikuje wszystkie nowe moduły i czeka na zamknięcie starych
klientów. Nie wymuszamy reload ani nie traktujemy flush jako dowodu trwałości.
Nie potwierdzamy kompletności pamięci nieodpowiadających kart.

Po błędzie odczytu **po** complete nie ma komunikatu sukcesu; aplikacja blokuje
kolejne zapisy i udostępnia zachowaną kopię sprzed operacji. Ponowny start
odczytuje rzeczywisty stan. Przy świadomie potwierdzonym przywróceniu z istniejących
formatów v1–v3 można przenieść uszkodzoną reprezentację v2 do pełnego, hashowanego
checkpointu odzyskiwania i kopii before-import w tej samej transakcji. Dopiero
takie jawne przywrócenie zastępuje uszkodzony zestaw rekordów. Nie ma automatycznego
kasowania, GC, resetu ani migracji danych telefonu w tej sesji. Nie wprowadzono
produkcyjnego restore v4/v6, nowej integracji Drive ani Issue #61.

Cofnięcie samego JS nie obniża DB version. Rollback wymaga zgodnego readera v2
albo jawnego odzyskania pełnej kopii w osobnym profilu. Uszkodzenia niebędące
przenośnym JSON nie są po cichu normalizowane/usuwane przez recovery.

## Weryfikacja i ograniczenia pomiaru

Testy obejmują Node, realny IndexedDB/CAS, strict complete przed publikacją,
quota/abort/przerwanie strony, dwa pierwsze uruchomienia, szkice, native V2
backoff/drop/L-R/grupy, plany, historię, archiwa, eksport i pełne restore,
Google Drive mock, offline i aktualizację starej PWA ze szkicem. Testy zachowanego
schematu v1 używają jawnie poprzedniego wydania jako testu kompatybilności;
pozostałe scenariusze funkcjonalne domyślnie uruchamiają bieżące Matrix/v2.
Nie usunięto ani nie osłabiono asercji danych. Wstrzyknięcia błędów w scenariuszach
v2 wskazują rzeczywiste stores v2. Test zegara dodaje 60 ms **po** complete i
potwierdza, że raportowany czas trwałości ich nie obejmuje.

Zachowane wyniki lokalne: **202/202 Node PASS**, **164/164 Chromium/PWA PASS**
(1029 s). Pełna seria przeglądarkowa dotyczy `28269e2`; późniejsza zmiana
`22ab1ea` ogranicza rezerwację bufora UTF-8 bez zmiany bajtów/hashów i przeszła
10/10 testów protokołu oraz 1/1 testu natywnego zegara. Build produkcyjny i
kontrola hashów PASS: release `24b263c7aebebbf577f0bdc5`.
Pełne CI finalnego PR sprawdza również tę ostatnią zmianę. Nie powtarzamy
zakończonych pomiarów #79/#81 ani nie przedstawiamy syntetycznej bazy jako
danych z telefonu właściciela.

Skrypt `measure_incremental_write.py` używa identycznego, przygotowanego raz
źródłowego fixture v1 dla obu wariantów. Każdy profil jest osobny, syntetyczny;
przeglądarki pracują kolejno. Initial conversion, start procesu i warm restart są
oddzielone od czasu zapisu. Mierzone są nowe wpisy i korekty, pierwsza operacja,
input→native strict complete, reakcja DOM, UI-ready, long tasks i pamięć.
CPU throttle Chromium/Linux nie emuluje Pixel 9 ani jego I/O. Memory high-water
jest próbkowanym JS heap, nie absolutnym peak procesu. Pełne
[tabele](performance/incremental-write-tables.md) i
[surowe wyniki z SHA/manifests](performance/incremental-write-measurements.json)
dotyczą runtime `c11c9a0` (te same bajty wydania co finalny kod PR).
Bez fizycznego Androida nie deklarujemy spełnienia celu p50 <0,5 s i p95 <1 s
na telefonie.

| Syntetyczna baza | Przed mediana / p95 ms | Po mediana / p95 ms |
|---|---:|---:|
| Pusta V2 | 384 / 428 | 113 / 127 |
| 4 sesje V2 | 917 / 1030 | 124 / 162 |
| 40 sesji V2 | 5813 / 6549 | 156 / 453 |
| 40 + raw ASCII 4 MiB | 6408 / 6780 | 152 / 560 |
| 40 + Unicode 4 MiB | 6152 / 6645 | 167 / 454 |
| 40 + escaped raw 16 MiB | 9609 / 9980 | 166 / 440 |
| 400 + raw ASCII 4 MiB — tylko v2 | brak: limit rekordu v1 | 138 / 417 |
| 400 + escaped raw 16 MiB — tylko v2 | brak: limit rekordu v1 | 138 / 453 |

Po 24 zapisy na wariant, 3 niezależne profile × 8 operacji (4 nowe, 4 korekty
bieżącej sesji). Uwzględniono pierwszy zapis. Łącznie 336 zapisów w 42 profilach;
SHA wcześniejszej historii/snapshotów/archiwów zgadza się w każdym profilu.
p95 jest najbliższą rangą w tej próbie, nie gwarancją dla dowolnego obciążenia.
Serie 400 są na osobnym hoście po wznowieniu środowiska, z identycznymi hashami
runtime, i nie są porównaniem z wcześniejszym hostem ani konwersją dużej v1.

Przy 40 + escaped 16 MiB stara projekcja pełnego modelu zajmowała medianowo
5395 ms, a zapis/porównanie modelu 1113 ms. Po zmianie kontekst/walidacja mają
medianę 6 ms, CAS 49 ms, readback 57 ms. Archiwa nie są przetwarzane ponownie
przy wyniku. To przedziały markerów, obejmujące także oczekiwanie, nie same
czasy CPU; suma median nie musi równać się medianie całej operacji.

**Koszt aktualizacji pozostaje istotny:** dla 40 + raw 4 MiB konwersja ma
medianę 52 s, zimny start 15 s i próbkowany startup heap max 918 MiB. Dla 40 +
escaped 16 MiB odpowiednio 111 s, 32 s i 1779 MiB (CPU×4/Linux). W tej drugiej
próbie save heap max spadł z 786 do 141 MiB, ale nie poprawia to automatycznie
startu ani konwersji. Pełny audyt, bulk oraz pamięć aktualizacji wymagają
osobnego odbioru na Pixelu. Nie przenosimy ich na pierwszy submit ani nie
deklarujemy płynnego uruchamiania dużej v1 na podstawie czasu pojedynczego wyniku.

Dodatkowa [weryfikacja dużych kopii](performance/incremental-large-backups.json)
potwierdziła eksport i pełny odczyt v3 obu baz 400 sesji / 3500 wyników /
400 snapshotów (pliki 141 705 315 i 169 201 307 B). Dane, katalog i archiwa są
zgodne. Próby v5 w obu przypadkach zostały **odrzucone** przez istniejący limit
64 MiB `live-model`, zanim doszło do próbnego odtworzenia. Pełny roundtrip v5
tych dwóch fixture nie jest zaliczony; skrypt zwraca błąd i zachowuje raport.
Nie zwiększono limitu, nie zmieniono formatu v5 i nie pominięto danych.
SHA wszystkich źródłowych rekordów IndexedDB przed/po jest identyczne.
Dotychczasowe mniejsze kopie v1–v6 i ich scenariusze są objęte pełną regresją;
obsługa tak dużej sekcji live v5 wymaga osobnego projektu.

Następnie istniejący `importModelBackup` przywrócił **obie** duże kopie v3 do
świeżych izolowanych IndexedDB v2: po 400 sesji, 3500 wyników, 400 snapshotów,
pełna zgodność SHA danych/katalogu i każdego archiwum oraz dodatkowy preimage
bazy docelowej. [Raport odtworzenia](performance/incremental-v3-restores.json)
potwierdza też brak zapisu do źródła. To wykonany import do izolowanej bazy,
bez nowego produkcyjnego restore v5/v6. Pierwsza próba narzędziowa nie dotarła
do importu wskutek limitu 100 MiB wiadomości DevTools; skrypt przekazuje teraz
tekst fragmentami 1 MiB, a metoda aplikacji nadal otrzymuje cały oryginalny plik.
Zakończonych odmów v5 nie powtarzano.

Limity dotyczą także zachowanych wersji i checkpointów. Writer oblicza ich
budżet przy pełnym odczycie, następnie aktualizuje mały licznik; zwykły wynik
nie serializuje checkpointu ani archiwum do sprawdzenia limitu. Przekroczenie
limitu przyszłego readera odrzuca zapis przed transakcją. Bulk i konwersja
sprawdzają docelowy komplet, zanim aktywują root. Granice nie zostały podniesione.

Przeglądarka ma także własne limity rekordu, niezależne od limitu całej bazy.
Diagnostyka 400 sesji odtworzyła abort starego writera: pojedynczy
`training-model-v1` miał 156 140 248 B (raw 4 MiB) lub 181 306 072 B (escaped
16 MiB), przy limicie Chromium 133 169 152 B i dostępnej quota około 10 GiB.
Po obu abortach pozostała poprawna wcześniejsza historia, bez częściowych
400 sesji. Nie istnieje zatem poprawny wspólny fixture v1 dla tego porównania.
Próby 400 sesji używają rzeczywistego bulk API v2 i są osobnymi testami wzrostu,
bez wyników „przed” oraz bez twierdzenia o konwersji tak dużej bazy v1.

Software budget nie gwarantuje przyjęcia pojedynczego rekordu przez każdą
przeglądarkę ani dostępności RAM. Duży checkpoint konwersji również może
natrafić na limit rekordu; błąd transakcji zachowuje poprzednie stores/pending,
bez aktywacji nowego root. Nie dodano fragmentacji checkpointu, podnoszenia
limitów ani automatycznego usuwania archiwów. To ograniczenie aktualizacji
wymagające osobnej oceny przed wdrożeniem na konkretnym urządzeniu.

Czytnik odłącza mutowalne wejście przed await SHA. Tekst JSON na drucie musi
mieć jednoznaczne kodowanie UTF-8: nieescapowane lone surrogates są odrzucane,
ponieważ TextEncoder zastąpiłby je U+FFFD. Same wartości zawierające lone
surrogates pozostają bezstratne dzięki JSON.stringify. Bufor UTF-8 jest
ograniczony i używany ponownie do SHA. Proof cache jest prywatny i dotyczy
wyłącznie całego wcześniej zweryfikowanego, głęboko niezmiennego bundle o tej
samej tożsamości; kopia z tymi samymi hashami nie dziedziczy dowodu. Niższe
limity i anulowanie działają również na ścieżce korzystającej z dowodu.

Zachowane niezmienne wersje zwiększają rozmiar DB. Pełny audyt i konwersja mogą
wymagać znacznej pamięci/czasu oraz dodatkowego miejsca na checkpoint. Nie ma
obietnicy dowolnie dużego stanu na każdym urządzeniu. Ograniczenia pozostawiają
poprzednie dane; nie usuwamy archiwów dla odzyskania miejsca.

## Osobny odbiór Pixel 9

Po przeglądzie i osobnym zatwierdzeniu wdrożenia: zabezpieczyć pełny eksport,
zachować szkic i zamknąć stare klienty bez wymuszonego przeładowania formularza.
Zapisać identyfikator wydania, dokładną wersję Androida/Chrome, rozmiar historii
i archiwów. Wykonać serię nowych wyników i korekt, również pierwszy zapis po
restarcie, obserwując natywne complete za pomocą istniejącego
[`pixel_write_probe.js`](../scripts/pixel_write_probe.js) (obsługuje teraz także
`journalState/active`). Podać n, medianę, p95 i max oddzielnie dla startu i
wyniku. Obserwator nie zapisuje treści formularzy ani wyników do raportu.

Dopiero taki pomiar pozwoli odebrać cel p50 <500 ms i p95 <1000 ms na urządzeniu.
W tej pracy nie wdrażano wydania na telefonie, nie otwierano jego bazy ani nie
potwierdzano kompletności pamięci innych kart. PR-y pozostają do przeglądu;
scalenie i publikacja nie zostały wykonane.
