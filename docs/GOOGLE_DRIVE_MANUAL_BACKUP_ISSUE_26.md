# Issue #26 — ręczne kopie teraz, bezobsługowa synchronizacja osobno

Decyzja właściciela z 23.10.2026 zastępuje obecną automatykę z Issue #16/#23. Punktem wyjścia jest `main` `e93a4a5`, po PR #25. Nie zmieniamy planu, nie aktywujemy V2 i nie wykonujemy operacji na koncie ani danych właściciela.

## Cztery operacje w Dane

1. **Zapisz kopię na Google Drive** — pełny eksport bieżących zatwierdzonych danych (v3, gdy działa model; w przeciwnym razie v2). Każde kliknięcie tworzy osobny niezmienny plik w dotychczasowym `appDataFolder`; stare pliki pozostają. Brak analizy konfliktów i wykonywania starego outboxu. Sukces dopiero po GET konkretnego pliku oraz sprawdzeniu SHA-256, pełnego formatu/relacji JSON i zgodności z wysłaną treścią. Jeśli podczas uploadu zmieniono trening, komunikat przypomina o nowej lokalnej zmianie.
2. **Pobierz kopię na telefon** — istniejący pełny eksport JSON, działa offline.
3. **Pobierz kopię z Drive** — pobiera sprawdzony treningowy JSON na telefon. Nie importuje go ani nie zmienia bazy, aktywnego planu lub szkiców. Kolejność plików wynika z daty utworzenia nadanej przez Drive, nie z zegara telefonu wewnątrz kopii. Uwzględniamy relacje dawnych kopii, żeby ponowiony zapis przodka nie wygrał z potomkiem. Przy niezależnych historiach urządzeń, nierozstrzygającej dacie lub pominięciu wadliwych kopii pojawia się prosty wybór: data, liczba sesji i wyników. Data uploadu nie dowodzi kompletności historii. Nie wybieramy historii automatycznie przy rozbieżności i nie pokazujemy UUID, drzewa gałęzi ani diagnostyki. Bezpośrednio przed pobraniem wyboru pliki są ponownie odczytywane i walidowane.
4. **Importuj kopię z telefonu** — dotychczasowa walidacja v1/v2/v3, potwierdzenie zastąpienia i transakcyjna kopia lokalnych danych przed importem. Anulowanie lub błąd nie zmienia bazy. Import nie usuwa rekordów szkiców; niezgodny szkic pozostaje do zabezpieczenia/odzyskania i nie nadpisze nowych wyników. Przed importem oczekujemy na zakończenie kolejki lokalnego szkicu.

**Połącz Google** jest widoczne, gdy dostęp jest potrzebny. Client ID i odłączenie konta są w **Opcjach zaawansowanych Google**. Nie ma przycisków synchronizacji/retry/rozstrzygania ani panelu diagnostycznego. Google nie jest potrzebne do treningu.

## Aktualizacja z konfliktem i starą kolejką

- Ten sam IndexedDB i klucz `drive-sync-v1`, bez zmiany schematu. Dopisujemy `mode: manual` i losowy identyfikator instalacji do rozróżnienia źródeł kopii; `enabled` staje się `false`. Całe dotychczasowe konta, baza, outbox, decyzje i potwierdzenia pozostają, ale są nieaktywne. Nie usuwamy oryginalnego localStorage, backupów ani rekordów treningowych.
- Przejście korzysta z istniejącej blokady `pushpull-drive-sync`: czeka na operację już trwającą, następnie wyłącza dawną automatykę. Zapis metadanych nie pozwala później ponownie ustawić `enabled: true` po przejściu w tryb ręczny; porównanie tokena nadal chroni przed nieaktualnym zapisem ustawień.
- Z kodu aplikacji usunięto wyzwalanie po commitach, imporcie, powrocie online i widoczności. Moduł nie ma timerów ani wykonywania outboxu. Nazwa pliku modułu została zachowana dla zgodności zasobów PWA; stara nazwa eksportu i pasywne `localChanged/retryNow` nie wysyłają danych.
- Worker nadal instaluje kompletny, zweryfikowany pakiet i czeka na zamknięcie wszystkich starych okien, bez wymuszonego przeładowania niezapisanego formularza. Nowy pakiet nie działa równolegle ze starym sterowanym przez poprzedni worker. **Aby aktualizacja weszła w życie, zamknij wszystkie okna PWA/karty i otwórz aplikację ponownie.** Samo wdrożenie nowych plików nie zatrzyma starego kodu działającego w otwartym oknie; żądania wysłanego przed aktualizacją nie można cofnąć. Testujemy tę granicę, bez obietnicy zatrzymywania przeglądarkowego procesu na odległość.
- Ręczny upload nigdy nie używa starego snapshotu oczekującego w outboxie. Zapisuje spójny bieżący eksport. Nie zmienia lokalnej historii, nie wykonuje PATCH/DELETE w Drive. Błąd lub przerwanie POST może pozostawić dodatkowy plik; ponowne ręczne kliknięcie zapisuje kolejną aktualną kopię, bez duplikowania wyników w dzienniku.

## Konfiguracja i odzyskanie na telefonie

Użyj tego samego klienta Google Cloud i konta co poprzednio; zmiana projektu może oznaczać inną przestrzeń appData. Dotychczasowy Client ID pozostaje zapisany. Szczegóły tworzenia klienta i origin HTTPS: historyczny [opis konfiguracji](GOOGLE_DRIVE_SYNC_ISSUE_16.md#jednorazowa-konfiguracja-google-cloud--właściciel-wykonuje-świadomie); etykiety przycisków zastępuje powyższa lista. Zakres nadal wyłącznie `drive.appdata`. Token jest tylko w pamięci, bez sekretów i refresh tokenów w JS/bazie/repozytorium.

Na nowym telefonie: skonfiguruj ten sam Client ID → Połącz Google → Pobierz kopię z Drive → sprawdź plik → Importuj kopię z telefonu → potwierdź. Przy rozbieżnych kopiach wybierz świadomie historię. Nie ma automatycznego łączenia wyników dwóch urządzeń. Szkice pozostają na urządzeniu, a nie w kopiach zatwierdzonych wyników. Przed zmianą telefonu zapisz wyniki i pobierz również plik poza aplikację.

## Testy i ograniczenia

Testy Node używają syntetycznej bazy i symulowanego Drive. Chromium używa rzeczywistego IndexedDB, formularzy, szkiców i service workerów; tylko Google OAuth/HTTP jest symulowane. Sprawdzamy m.in. dwa urządzenia, starą kolejkę/konflikt, brak automatycznych POST, bieżącą treść uploadu, weryfikację GET, offline/restart, niezależne szkice A/B, pobranie bez importu, wybór rozbieżnych kopii, uszkodzone pliki oraz anulowany/potwierdzony import z kopią sprzed importu. Test aktualizacji używa rzeczywistego poprzedniego pakietu z `e93a4a5` i tej samej bazy bez czyszczenia pamięci.

Końcowe wyniki lokalne i GitHub Actions są w PR. Istniejące testy dawnej automatyki zastąpiono testami zatwierdzonego ręcznego działania; pozostała regresja jest zachowana.

**Niewykonane:** prawdziwe konto Google, realne limity appData i fizyczny Android. Potrzebny jest odbiór na telefonie: aktualizacja → odzyskanie szkicu → wynik offline → ręczny upload → pobranie pliku i sprawdzenie dzisiejszych danych → kontrolowane odtworzenie na profilu testowym. Brak dostępu lub sieci nigdy nie blokuje lokalnego zapisu. Nie ma gwarancji zachowania danych po usunięciu pamięci/awarii telefonu przed kopią. Pobieranie sprawdza pełne pliki i z czasem może trwać dłużej przy wielu dużych kopiach; retencja nie jest częścią tego PR i żadnej kopii nie usuwamy.

Docelowa prawdziwa automatyczna synchronizacja nie jest zakazana. Faza B wymaga osobnej decyzji i porównania rozwiązań faktycznie bezobsługowych po zimnym starcie/wygaśnięciu tokena (np. backend OAuth offline lub właściwa integracja Androida), wraz z kosztami i utrzymaniem. Nie implementujemy jej w tym PR i nie nazywamy ręcznego odnawiania tokena automatyką.
