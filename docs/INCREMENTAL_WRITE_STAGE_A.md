# Issue #82 A — odseparowany protokół 2

Baza: `main` `4647511`, po PR #79/#81. Ten etap nie otwiera ani nie aktualizuje
produkcyjnej bazy, nie zmienia UI, builda, kopii v1–v6 ani istniejącego writera.

Nowy moduł `journal-protocol.mjs` ma jawne stores: `journalObjects`,
`journalMetadata`, `journalSessions`, `journalResults`, `journalSnapshots`,
`journalArchives`, `journalIndex`, `journalState`, `journalCheckpoints`.
Wszystkie mają keyPath `id`. Stan aktywny zawiera protokół, epoch, rewizję,
root indeksu, liczniki i właściciela. Checkpoint i konwersja należą do etapu B.

Obiekty zawierają dokładny `JSON.stringify`, długość UTF-8 i SHA-256 tych bajtów.
Kodowanie JSON zachowuje również lone surrogates. Reader sprawdza długość,
SHA, ścisły JSON i wszystkie nieznane pola. Deskryptory są poza danymi użytkownika;
obiekt użytkownika przypominający referencję nadal jest zwykłą wartością.
Metadane przechowują kolejność pól, kolekcje pozycje, snapshoty wszystkie swoje
pola i osobne referencje do modeli. Deduplikacja dotyczy dokładnych bajtów,
nie podobieństwa ID/planu/czasu. Materializowane modele są głęboko niezmienne.

Korzeń to trwałe drzewo AVL z SHA każdego węzła: klucz store/ID, hash całego
rekordu, dzieci i wysokość. Korekta/nowy wynik zmienia ścieżkę O(log n), nie
hash całego JSON. Pełny audyt sprawdza kolejność, balans, kompletność liści,
treści obiektów i także zachowane stare węzły. Etap B musi ponownie sprawdzić
odczytane referencje/ścieżkę w tej samej transakcji CAS; sam klucz SHA nie wystarczy.

Początkowe limity alokacji: 128 MiB na obiekt, 512 MiB łącznie, 1 mln rekordów.
Można je obniżać; przekroczenie kończy operację błędem. Nie gwarantują dostępnej
pamięci Androida. Duże archiwa mogą wymagać pamięci na JSON i UTF-8 jednocześnie.
Nie ma dekompresji ani zmiany limitów kodeków backupów. Konwersja będzie osobną,
kosztowną operacją; normalny wynik nie będzie przetwarzał archiwów.

Testy obejmują dokładny JSON i v3 wobec obecnego eksportera, legacy i native
V2/V3, 400 logicznych snapshotów, Unicode, raw, metadane, integralność treści,
braki rekordów, indeks, anulowanie, limity oraz zapis/restart w osobnej bazie
Chromium. Syntetyczne dane nie są pomiarem fizycznego Androida.

Następnie B: writer, checkpoint/konwersja i błędy transakcji. Dopiero C podłączy UI.
