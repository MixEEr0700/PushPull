# Issue #82 B — izolowany writer i konwersja

Zależność: PR #83 (A). Ten etap nadal nie podłącza UI ani nie otwiera produkcyjnej
bazy w wersji 2. Nowy backend jest testowany wyłącznie na nazwanych bazach
syntetycznych. `indexeddb.js` otrzymuje tylko read-only oracle `verifyEvidence`,
korzystający z tych samych pełnych validatorów, co dotychczasowy start v1.

`prepareConversion` przed upgrade odłącza i weryfikuje pełne źródło, tabele,
digest i model v1. Buduje protokół 2 i sprawdza dokładną materializację.
Krótki `connectV2` tworzy osobne stores i marker pending; nie wykonuje crypto w
versionchange. `activateConversion` przyjmuje wyłącznie wydany prywatnie token.
W transakcji strict sprawdza ponownie wszystkie tabele i metadane v1 (w tym
szkice), zapisuje checkpoint, odczytuje zapis i dopiero aktywuje nowy root.
Każdy błąd/abort/quota pozostawia checkpoint v1. Wznowienie używa aktualnego
odczytu; nigdy automatycznie nie odtwarza starszego stanu. Stary kod otwierający
DB z version 1 otrzyma VersionError. Nie ma resetu ani downgrade DB.

Checkpoint zachowuje dokładne rekordy v1 z SHA-256 oraz zobowiązaniem do pełnego
źródła według dotychczasowej kanonizacji v1. Audyt ponownie sprawdza również
validator v1 checkpointu. `training-model-v1` pozostaje oryginalnym checkpointem,
nie otrzymuje pozornej aktualnej rewizji. Mały root v2 obejmuje też jawne
`modelEnabled`, aby zachować różnicę między legacy a włączonym bridge modelem.
`legacyRef` wskazuje zweryfikowaną niezmienną wartość localStorage służącą do
wykrywania zapisu starego klienta. Root zawiera tylko hash, nie wielki raw.

`saveResult` odłącza i waliduje cały wpis przed await. Używa oryginalnego
snapshotu, dotychczasowego validatora legacy oraz współdzielonego `projectEntry`
używanego również przez pełne backupy. Sprawdza serie, load convention, wariant,
strony, dropy, powiązania i globalną unikalność ID wyników. Niezmieniony model i
historia mają dowód pełnej walidacji z odczytu; nie są ponownie budowane.

CAS obejmuje cały mały root, epoch/revision, hash poprzedniego wyniku,
wymagane rekordy i treści obiektów, marker protokołu oraz ścieżki indeksu.
Crypto odbywa się przed transakcją. Transakcja ponownie porównuje wszystkie
oczekiwane treści, używa add dla obiektów, zapisuje wynik i korzeń, wykonuje
pełny readback zmienionych/wymaganych obiektów i indeksu. Publikacja w pamięci
i mały ack następują wyłącznie po natywnym `strict complete`.

Zapis wyniku nie czyta ani nie serializuje archiwów. Ich zmiana poza protokołem
jest wykrywana podczas pełnego odczytu/audytu/eksportu, nie w operacji, która
tego archiwum nie czyta. Pozostają stare niezmienne obiekty i węzły; nie ma GC
usuwającego dane. Narzut przestrzeni i pełny audyt przy starcie wymagają osobnych
pomiarów. Nie deklarujemy szybkości Androida ani zakończenia etapu C.

Testy Chromium obejmują rzeczywiste strict transakcje, restart, CAS dwóch
klientów, błędne wejście/nieznane pola, Unicode/lone surrogate, zachowanie
checkpointu, przerwanie podczas przygotowania i transakcji, quota, uszkodzony
readback, nowy wynik/korektę bez czytania raw, nieukończoną konwersję, jej
wznowienie i odmowę starego writera. Kompletna regresja jest wymagana w CI PR.

Weryfikacja lokalna: Node 197/197 PASS; Chromium writer/conversion 11/11 PASS;
kontrola hashy produkcyjnego builda PASS. Logi powtórzone po wznowieniu, ponieważ
poprzedni /tmp nie przetrwał przerwania. Przypadki testowe obejmują również
zamknięcie strony w aktywnej transakcji, blokującego starego klienta i quota
w versionchange. Pełna regresja uruchamiana jest w GitHub Actions tego PR.
