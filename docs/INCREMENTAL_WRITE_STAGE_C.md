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

Skrypt `measure_incremental_write.py` używa identycznego, przygotowanego raz
źródłowego fixture v1 dla obu wariantów. Każdy profil jest osobny, syntetyczny;
przeglądarki pracują kolejno. Initial conversion, start procesu i warm restart są
oddzielone od czasu zapisu. Mierzone są nowe wpisy i korekty, pierwsza operacja,
input→native strict complete, reakcja DOM, UI-ready, long tasks i pamięć.
CPU throttle Chromium/Linux nie emuluje Pixel 9 ani jego I/O. Memory high-water
jest próbkowanym JS heap, nie absolutnym peak procesu. Wyniki będą dołączone po
zakończeniu pomiarów; bez fizycznego Androida nie deklarujemy spełnienia celu
p50 < 0,5 s i p95 < 1 s na telefonie.

Limity dotyczą także zachowanych wersji i checkpointów. Writer oblicza ich
budżet przy pełnym odczycie, następnie aktualizuje mały licznik; zwykły wynik
nie serializuje checkpointu ani archiwum do sprawdzenia limitu. Przekroczenie
limitu przyszłego readera odrzuca zapis przed transakcją. Bulk i konwersja
sprawdzają docelowy komplet, zanim aktywują root. Granice nie zostały podniesione.

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
