# Aneks v1 — etap 4: Aplikacja Treningowa

21.10.2026. Uzupełnia [historyczny plan v1](../PushPull_PLAN_PROJEKTU_v1.md), którego treści nie zmieniamy. Nazwa produktu: **Aplikacja Treningowa**; repozytorium nadal `MixEEr0700/PushPull`. Zatwierdzony Matrix v0.3 — szlif 3 pozostaje wzorcem. Plan V2 nadal demonstracyjny do weryfikacji z trenerem.

Etapy 1–3 dostarczyły ochronę danych, transakcyjne IndexedDB, kopie i przygotowanie PWA bez publikacji. Etap 4 wdraża nazwę i dokumentuje [architekturę docelową](TARGET_ARCHITECTURE_STAGE_4.md). Nie wdraża modelu docelowego ani integracji.

## Kolejność kolejnych osobno zatwierdzanych etapów

| Etap | Zakres | Warunek odbioru |
| --- | --- | --- |
| 5 | Potwierdzenie V2, fizyczny Android i wybór stabilnego HTTPS niezależnego od PC | Checklist instalacji/aktualizacji, kopia i odtworzenie na telefonie, osobna zgoda na hosting; brak automatycznej publikacji. |
| 6 | Repozytorium domenowe, owner/profil i wersjonowane programy/jednostki | Bezstratna migracja na kopiach, stare ID i notatki zachowane, testy izolacji i blokady starego kodu; brak Drive. |
| 7 | Import planu i dowolna liczba jednostek, oddzielne instrukcje i notatki | Podgląd i anulowanie, jawne mapowanie ćwiczeń, wersje/snapshoty, historia/statystyki bez regresji; każde konieczne rozszerzenie UI wymaga odrębnej akceptacji. |
| 8 | Ręczny raport dla trenera JSON + CSV, pełny backup oddzielnie | ChatGPT/Excel odczyt, zakres bloku/całości, bezpieczeństwo formuł, brak tokenów i automatycznego wysyłania; odtworzenie pełnej kopii. |
| 9 | Prototyp OAuth i indywidualnego Drive na danych syntetycznych | Weryfikacja zakresów/zgód, konto/profil, wygaśnięcie tokenu, offline i odmowa uprawnień; osobne zatwierdzenie usług. |
| 10 | Synchronizacja produkcyjna i odzyskiwanie | Konflikty dwóch urządzeń i kart, idempotencja, przerwane uploady, quota, usunięte pliki i wielowersyjne odzyskiwanie; żadnego centralnego dostępu trenera. |

## Protokół przyszłej migracji modelu

1. Odczytać i zweryfikować aktualne v1/backup v2 oraz schemat IDB. Wymagać pełnej kopii poza przeglądarką przed akceptacją migracji. Zachować surowe localStorage i archiwa; nie używać ich jako aktualniejszego źródła niż IDB.
2. Utworzyć manifest migracji: wersja źródłowa/docelowa, liczby, hashe, mapa ID i relacji, kopia źródła. Oryginalne ID ćwiczeń/sesji/wyników pozostają bez zmiany; nowe techniczne ID tylko dla nowych encji. Legacy notes bez rozdzielania autorstwa, historyczne parametry z jawnym brakiem wiedzy.
3. Zamknąć inne okna poprzez komunikat/BroadcastChannel; `versionchange` zamyka połączenia, `blocked` zatrzymuje pracę bez resetu. Zabezpieczyć stary kod przez minimalną obsługiwaną wersję schematu i znacznik owner/revision; nie zakładać możliwości zmiany już zcache'owanego kodu.
4. Rozbudowa schematu addytywna, stare store'y pozostają do zweryfikowania. Dla dużych baz staging z zapisywanym postępem, resumable i idempotentne partiami; aplikacja czyta wyłącznie jeden kompletny model. Niedokończony staging nigdy nie jest aktywną pustą historią.
5. Porównać zrekonstruowany dokument/katalog/archiwa, ID, relacje, liczby i hashe z oryginałem; jawnie zachować nieznane pola. Atomowe przełączenie aktywnego modelu i znacznika complete dopiero po weryfikacji. UI sukces dopiero po oncomplete.
6. Każdy błąd, quota, zamknięcie przeglądarki lub brak uprawnień → stara historia/ekran odzyskania i bezpieczne wznowienie, bez kasowania. Nowy model nie zastępuje źródła przed pełną walidacją. Aktualna rewizja sprawdzana w transakcji.
7. Po migracji porównać eksporty, otworzyć ponownie offline i odtworzyć backup w odrębnym profilu/origin. Starego schematu nie usuwać w tej samej wersji. Nie cofać aplikacji do starego kodu ignorującego nową historię.

Macierz testów dla każdego przyszłego etapu: pusta/pełna/duża baza, v1/v2, Unicode i dodatkowe pola, nieznana wersja/uszkodzenie, quota i abort na każdym punkcie, restart i ponowienie, równoległe karty, brak/kolizja owner, import planu bez zmiany historycznej sesji, report round-trip tabel, backup odtwarzalny, offline i update. Przed Drive dodatkowo rozbieżna korekta tej samej serii, duplikat operacji, zmiana konta, brak tokenu i usunięcie pliku. Porównania Matrix nadal z `92390b1`, bez regenerowania wzorców z nowego UI.

Odzyskiwanie obecnej wersji: [procedura etapu 2](INDEXEDDB_MIGRATION_STAGE_2.md). Fizyczny Android i parametry V2 pozostają warunkami gotowości; dokument architektury sam ich nie spełnia.
