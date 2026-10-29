# Issue #110 — opcje zaawansowane Dane

Baza: `main` `4495568`, po PR #108. Główne dwa przyciski oraz ich przepływy pozostały bez zmian. Opcje zaawansowane zawierają grupy **Połączenie Google Drive**, **Zachowane kopie ratunkowe**, **Diagnostyka kopii** i domyślnie zamknięte **Narzędzia techniczne**. Zachowano eksperymentalne funkcje v4/v5, kolektor szkiców, dotychczasowy starszy zapis planu oraz konfigurację i ręczne połączenie/odłączenie Google. Odłączenie i ponowne połączenie pozwala świadomie wybrać konto. Nie dodano automatycznej kopii opisanej w #109.

Otwarcie Dane i grup nie wymaga pełnego odczytu historii. Jawne pokazanie listy kopii wykonuje dotychczasowy pełny audyt IndexedDB v2. Wybór oraz przycisk podglądu czytają wyłącznie wybraną kopię przez `database.readBackup()`, a weryfikacja zawartości korzysta z istniejącego workera importu. Przed opublikowaniem wyniku wykonywany jest istniejący `auditExport()` oraz sprawdzane są rewizja i pierwotny localStorage. Audyt sprawdza także aktualny root IndexedDB, dzięki czemu zapis drugiej karty bez BroadcastChannel unieważnia podgląd. Pokazujemy liczniki z kopii; nie jest to przywrócenie ani porównanie z całą bieżącą historią. Podgląd nie tworzy kandydata głównego importu i nie uruchamia importera.

Anulowanie kończy worker weryfikujący, usuwa wynik i blokuje spóźnione odpowiedzi. Rozpoczęty odczyt lub audyt IndexedDB nie oferuje fizycznego przerwania: może zakończyć się w tle, bez publikacji anulowanego wyniku. Po zmianie wyboru rezultat jest czyszczony, a wybrana pozycja pozostaje wybrana po renderowaniu. Po zmianie rewizji lub lokalnego źródła stary wynik jest ukrywany. Ukończenie podglądu po opuszczeniu Dane nie przebudowuje ekranu treningu. Nieprawidłowe, puste lub nieobsługiwane archiwum nie otrzymuje podglądu; pobranie oryginału nadal jest dostępne.

Backend Drive i kopii, formaty v1–v6, IndexedDB, CAS, preimage, readback, `strict complete`, Matrix, dane i historia są bez zmian. Nie modyfikowano workflow.

## Weryfikacja i ograniczenia

Lokalne testy i pełny przebieg CI są podane w PR. Dedykowane testy korzystają z izolowanych syntetycznych baz oraz rzeczywistego Chromium/IndexedDB: porównanie wszystkich rekordów i localStorage przed/po, odczyt archiwum w wymaganym audycie, brak audytu na samej nawigacji, offline, przerwanie workera i końcowego audytu, zmiana rewizji, osobny uchwyt bez BroadcastChannel, niepoprawne raw, brak importu, nieprzebudowywanie treningu po opuszczeniu ekranu, klawiatura, 360/390/412 px i min. 44 px dla przycisków. Google OAuth/HTTP są symulowane.

Przy dużych archiwach pełny audyt i weryfikacja kopii nadal mogą wymagać znacznego czasu oraz pamięci; nie zmieniono formatu ani limitów i nie deklarujemy responsywności na fizycznym Pixelu 9. Nie testowano rzeczywistego konta Google. Zamknięcie przeglądarki może przerwać odczyt; nie zmienia to istniejącej bazy.
