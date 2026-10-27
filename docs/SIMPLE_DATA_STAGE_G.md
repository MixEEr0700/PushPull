# Etap G — prostsze Dane (Issues #27 i #45)

Baza: PR #92 / etap F (`1be8b75`), po `main` `58310ff` i PR #91.
Osobny PR; żadnego scalenia zależności.

## Cztery codzienne działania

1. Zapisz kopię na Google Drive — dotychczasowy ręczny upload i weryfikacja.
2. Pobierz kopię na telefon — dotychczasowy eksport JSON, bez zmiany formatu.
3. Pobierz kopię z Google Drive — lista dat, od najnowszej; jawne pobranie wybranego pliku JSON. Nigdy automatyczne przywrócenie.
4. Importuj kopię z telefonu — istniejąca walidacja → podgląd/porównanie → osobne potwierdzenie zastąpienia z lokalną kopią preimage.

Plany i statystyki ogólne nadal są na głównym panelu; historia/kalendarz w dotychczasowej nawigacji. Informacje i aktualizacje PWA pozostają dostępne. Połącz Google jest widoczne wyłącznie, gdy połączenie jest potrzebne.

Jedne domyślnie zamknięte „Opcje zaawansowane” zawierają OAuth/zmianę konta, szczegółowe komunikaty Drive, techniczne kopie/podglądy v4/v5, kolektor szkiców, zachowane kopie sprzed importu i starszy zapis planu. Stan rozwinięcia jest wyłącznie pamięcią UI, nie zmianą konfiguracji użytkownika; resetuje się po restarcie. Przywracanie bezpośrednio z Drive pozostaje dostępne tutaj, z dotychczasowymi trzema krokami i widocznym anulowaniem. Podgląd oraz główna akcja potwierdzenia są wyprowadzane ponad szczegóły i dostają fokus na telefonie.

## Zachowane bezpieczeństwo i szybkość

Nie zmieniono `model/drive-sync.mjs` ani transportu Google. UI używa istniejącego `download(..., {choose, forRestore:false})`: ten sam digest/walidator, pełna lista poprawnych kopii i dokładny oryginalny JSON. Nie dodano synchronizacji, timerów, merge ani zapisu na Drive bez ręcznego kliknięcia.

Pobieranie pliku ma własny stan UI oraz numer operacji: podwójny klik nie uruchamia dwóch pobrań, anulowanie blokuje dostarczenie spóźnionego wyniku. Biblioteka nie ma sygnału abort dla HTTP; rozpoczęty odczyt może dokończyć się po anulowaniu, bez pobrania pliku ani zapisu do bazy. Trening pozostaje dostępny. Zmiana wyboru kopii niczego nie zapisuje. Plik, który zniknął lub nie przechodzi integralności, nie jest zastępowany inną kopią po cichu.

Samo wejście do Dane oraz pobranie z Drive nie uruchamia `ensureFull()` ani doczytania historii lokalnej. Zapis konfiguracji OAuth również nie potrzebuje historii — usunięto go z ogólnego warunku doczytywania przy submit. Zapis konfiguracji nadal jest oczekiwany w kolejce zdarzeń przed połączeniem. Eksport/upload, operacje pełnych danych i rzeczywiste przywracanie zachowują dotychczasowy audyt i zabezpieczenia PR #91. Bez zmian protokołu IndexedDB v2, CAS, walidacji, readback, `strict complete`, formatów kopii v1–v6 ani mechanizmu ich przywracania. Bez automatycznego usuwania danych.

## Weryfikacja

- Node: **212/212 PASS**; składnia, zgodność worker/hash i produkcyjny build PASS.
- 41 różnych scenariuszy Chromium/PWA PASS w ukierunkowanych przebiegach: dotychczasowe ręczne Drive/restore/upgrade, lazy Dane, starszy zapis planu, v4/v5 offline (w tym 65 MiB raw), podgląd w izolacji i kolektor; nowe trzy scenariusze czterech akcji oraz cztery scenariusze notatek F (także kolizja ID ze wpisem sesji), a także rzeczywista aktualizacja PWA z zamkniętymi opcjami i zachowanym szkicem. Dwa testy wymagały jawnego otwarcia nowego nadrzędnego menu; kontrola po aktualizacji PWA została dopasowana do czterech nowych nazw akcji i dostępu do restore w zaawansowanych; ich asercje integralności pozostały.
- Nowe testy porównują **wszystkie rekordy wszystkich store’ów** przed/po: pobranie dokładnie wybranego oryginalnego JSON, lista dat, sam wybór bez zapisu, brak POST, zniknięcie/uszkodzenie pliku, offline, anulowanie spóźnionego GET i podwójny klik. Historia oraz archiwa lokalne pozostają deferred również po konfiguracji i pobraniu z Drive.
- Główne cztery działania i brak poziomego przewijania sprawdzone przy 360/390/412 px; istniejący test prowadzonych kroków restore weryfikuje widoczność głównych akcji na ekranie telefonu. Pełny workflow PR uruchamia Node i całą regresję Chromium/PWA na zamrożonym HEAD.

Wzorzec F w tabeli pochodzi z `dc3766f`, przed końcową poprawką zakresu notatki. G zmierzono po tej poprawce; hashe zmierzonego runtime są zgodne z końcowym kodem. Writery nie uległy zmianie.

Seryjne pomiary syntetyczne, Chromium/Linux CPU ×4, te same zachowane fixture’y. JSON: [simple-data-g.json](performance/simple-data-g.json). Brak równoległych lokalnych testów podczas pomiaru. p95 przy małym n jest maksimum próby, nie statystycznym potwierdzeniem celu na urządzeniu.

| Dane offline (n=5) | F mediana / p95 | G mediana / p95 |
| --- | --- | --- |
| 4 sesje | 33 / 60 ms | 26 / 68 ms |
| 40 sesji + raw 4 MiB | 27 / 58 ms | 26 / 51 ms |
| 400 sesji + raw 4 MiB | 33 / 49 ms | 43 / 48 ms |

We wszystkich wejściach G: **0 żądań IndexedDB**. Nie przywrócono kosztownego `ensureFull()` podczas nawigacji.

| Zapis (n=8) | F strict complete mediana / p95 | G strict complete mediana / p95 | heap zapisu F / G (maks. próbka) |
| --- | --- | --- | --- |
| 4 sesje | 155 / 253 ms | 148 / 237 ms | 12,3 / 12,2 MiB |
| 40 sesji + raw 4 MiB i checkpointy | 182 / 301 ms | 188 / 336 ms | 20,4 / 20,4 MiB |

Nie zaobserwowano wielosekundowej ścieżki zapisu. Wahania rzędu kilkudziesięciu ms przy n=8 nie stanowią dowodu istotnej zmiany wydajności. Protokół zapisu nie był modyfikowany. Heap jest próbkowanym heapem JS, nie całkowitym RAM ani gwarantowanym szczytem. Orakle benchmarku potwierdziły zachowanie źródłowych historii/archiwów.


## Ograniczenia i odbiór

- Brak testu fizycznego Pixela 9; wyniki poniżej są syntetyczne (Chromium/Linux, CPU ×4). Na telefonie należy sprawdzić klawiaturę/wybór pliku, pobranie pliku przez Androida i OAuth oraz rzeczywiste czasy.
- Google OAuth i HTTP w regresji są symulowane; produkcyjne konto/Drive nie zostały zmienione. Dotychczasowy mechanizm listowania weryfikuje kopie zdalne; przy wielu dużych plikach operacja sieciowa może być kosztowna. Nie przebudowano tego protokołu.
- Przeglądarka otrzymuje polecenie pobrania; aplikacja nie potwierdza fizycznego zapisania pliku przez menedżer Androida. Pobranie oraz import to oddzielne czynności.
- Dotychczasowe ograniczenia podglądu v4/v5/v6, odzyskiwania i kompletności szkiców pozostają. Nie dodano produkcyjnego przywracania nowych formatów ani kolejnego etapu v6.
