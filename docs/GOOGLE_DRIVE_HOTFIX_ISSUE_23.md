# Issue #23 — hotfix powracającego konfliktu Drive

Aktualny tryb Drive: [ręczne kopie, decyzja Issue #26](GOOGLE_DRIVE_MANUAL_BACKUP_ISSUE_26.md). Opisy automatycznej synchronizacji poniżej są historyczne.


Punkt wyjścia: `main` `ade2a2c`, po PR #19. Osobna gałąź `fix/issue-23-drive-conflict`, bez zmian i bez scalania otwartego PR #24 (import planów). Najnowsze zlecenie właściciela nadaje temu blockerowi pierwszeństwo. Nie odczytywano danych telefonu ani prywatnego Drive właściciela.

## Przyczyna odtworzona w testach

Dotychczasowe siedem testów modułu przechodziło, ponieważ symulator zawsze natychmiast zwracał pełną, aktualną listę plików. Dwa nowe przypadki nie przechodziły przed poprawką:

1. Lista pokazuje głowę `H`, której przodkiem jest `R`. Po zatwierdzeniu lokalnej wersji kolejny odczyt listy zwraca starszy, ale wewnętrznie spójny graf z głową `R`. Ścisłe `heads === base` rozpoznaje to jako konflikt. To samo mogło zablokować ponowną weryfikację listy pomiędzy przyciskiem „Pokaż kopie” i `keepLocal`. Brak wpisu w wyniku wyszukiwania nie dowodzi odrzucenia zapisu przez Google.
2. `keepLocal` ustawiał bazę i kasował `outbox`. Tracił UUID i stan wcześniej utrwalonej operacji, która mogła już dotrzeć do Google. Nie zapisywał odrębnej trwałej decyzji użytkownika; kolejne uruchomienie `work` ponownie stosowało ten sam warunek konfliktu. Nowy test dwóch urządzeń wymaga zachowania pierwotnego UUID i dopiero potem nowej kopii najnowszego stanu telefonu.

Dodatkowo kod ignorował identyfikator pliku zwrócony przez POST i wymagał natychmiastowej obecności pliku na liście przed jego odczytem. To uzależniało potwierdzenie od świeżości wyszukiwania, zamiast od dostępnego odczytu konkretnego zapisanego pliku.

**Granica diagnozy:** odtworzono deterministyczne usterki implementacji i przebieg odpowiadający zgłoszeniu. Nie mamy telemetrii odpowiedzi Google z telefonu właściciela, więc nie twierdzimy, że potwierdziliśmy dokładnie ten sam rozkład odpowiedzi na fizycznym Androidzie. Do dalszego rozróżnienia przypadków służy nowa diagnostyka.

## Naprawione przejścia

1. **Lista / wybór:** `listCopies` pamięta obejrzane głowy i ich graf w kontekście konta oraz klienta OAuth. `keepLocal` nadal odrzuca nową, niezatwierdzoną głowę. Starszy podzbiór uprzednio obejrzanego grafu nie unieważnia wyboru użytkownika.
2. **Trwała decyzja:** w istniejącym `drive-sync-v1` zapisuje się `resolution` z własnym ID oraz zaakceptowanymi głowami. Zbiór `covered` identyfikuje znanych przodków zaakceptowanych/potwierdzonych baz. Nie jest zasilany dowolną niezatwierdzoną gałęzią.
3. **Stary outbox:** pozostaje z niezmiennym UUID, rodzicami i zawartością. Najpierw kończymy tę operację. Może utworzyć oddzielną, zachowaną gałąź. Jej potwierdzenie nie usuwa późniejszej decyzji `resolution`.
4. **Nowy outbox:** powstaje pełny eksport aktualnej, stabilnej rewizji lokalnego dziennika. Jego rodzicami są zaakceptowane bazy oraz dokończona poprzednia operacja. Nie cofamy rodziców do starszej odpowiedzi listowania. Decyzja jest wiązana przez ID, aby wcześniejszy upload nie skonsumował kolejnego zatwierdzenia.
5. **Upload:** tak jak wcześniej UUID i cały dokument są zapisane w IndexedDB przed POST. Dodatkowo utrwalamy zwrócony `fileId`. Po przerwaniu odczytu ponowienie wykorzystuje ten plik; po niejednoznacznej odpowiedzi POST nadal rozpoznajemy istniejący UUID na liście.
6. **Potwierdzenie:** GET konkretnego pliku, kontrola SHA-256, formatu, relacji i dokładnej zgodności z outboxem. Samo 200 POST, autoryzacja albo timestamp nie oznaczają sukcesu. Dopiero potwierdzona kopia aktualizuje `ackRevision` i czas sukcesu; nowsza rewizja lub nierozstrzygnięta decyzja nadal oznaczają oczekiwanie.
7. **Nowa obca gałąź:** nadal konflikt wymagający świeżego obejrzenia/wyboru. Nie scalamy wyników automatycznie i nie zastępujemy danych lokalnych przez kliknięcie „Zachowaj lokalne”. Brak lub opóźnienie wyników wyszukiwania nie usuwa dowodu wcześniejszego potwierdzenia; po ujawnieniu nowej obcej głowy będzie ona ponownie rozpoznana.

Format plików Drive `pushpull-drive-backup` v1 i zakres OAuth są bez zmian. Dodatkowe pola dotyczą wyłącznie metadanych istniejącej kolejki; wcześniejsze stany bez tych pól są obsługiwane. Nie zmieniono schematu IndexedDB, magazynu treningów ani modułów modelu, statystyk, szkiców i backupów. Nie ma operacji PATCH/DELETE na kopiach. Nie zmieniono parametrów ani aktywacji V2.

## Diagnostyka

W **Dane → Google Drive → Diagnostyka Drive**:

- `phase`: ostatni etap (`list`, `resolution`, `enqueue`, `upload`, `verify`, `synced`, `conflict`, `auth`, `offline`, `error`);
- `revision` i `ackRevision`: bieżąca rewizja lokalna i ostatnia potwierdzona;
- `headCount`, `baseCount`, `heads`, `base`: liczby i skrócone UUID głów/bazy;
- `covered`: liczba znanych elementów objętych bazą;
- `outbox`: skrócony UUID, rewizja i `uploadReceipt` (czy jest identyfikator z POST; **nie** potwierdzenie odczytu);
- `resolution`: czy pozostaje trwała decyzja do wykonania.

Diagnostyka aktualizuje się bez przeładowywania formularzy. Nie zawiera tokenów, adresów konta, wyników ani treści treningów. Etykieta konfliktu odróżnia przywrócenie kopii od dopisania nowej lokalnej wersji do Drive. Matrix, karty i CSS są zachowane.

## Testy

Przed poprawką: dotychczasowe 7/7 testów Drive PASS, dwie nowe reprodukcje FAIL (fałszywy konflikt i utrata outboxu). Po poprawce:

- Node: cały istniejący zestaw oraz trzy nowe przypadki Drive (stara/pusta lista, dwa urządzenia + restart + zmiana głów między listą i wyborem, przerwany read-back po POST + restart bez ponownego uploadu).
- Chromium: dwa izolowane profile, rzeczywiste IndexedDB, istniejący adapter OAuth/HTTP z symulowanym Google. Lokalny wynik i szkic → konflikt → ręczny wybór → upload z wstrzymaną odpowiedzią → starsza lista → bezpośredni odczyt nowego pliku → `Zsynchronizowano` → pełna zawartość zgodna z telefonem → następny zatwierdzony wynik. Starsze pliki i historia drugiego urządzenia pozostają. Nie ma cichego merge.
- Istniejąca regresja lokalnego zapisu przed odpowiedzią Google, 401/500, offline, natywnych struktur V2, szkiców A/B, kalendarza/statystyk, JSON v3, migracji, Matrix i aktualizacji PWA. Zastąpiono kruche oczekiwanie 150 ms na upload oczekiwaniem na rzeczywiste żądanie, pozostawiając kontrolę lokalnego zapisu przy wstrzymanej odpowiedzi.
- Syntax, świeżość workera, lokalny build i `git diff --check`. Nowy worker jest potrzebny do dostarczenia poprawionych skryptów offline; jego mechanizm aktualizacji jest bez zmian.

Wykonano lokalnie: **83/83 testy Node PASS**, **70/70 testów Chromium PASS** (pełna regresja), `node --check app.js`, `node --check model/drive-sync.mjs`, `python3 scripts/build_release.py --check`, lokalny build wydania oraz `git diff --check` — PASS. Wyniki GitHub Actions dla końcowego commitu znajdują się w PR. Testy używają wyłącznie syntetycznych danych i kont symulowanych.

## Ograniczenia i odbiór

- Fizyczny Android i prawdziwe konto Google: **niewykonane** w tym środowisku. Po zatwierdzeniu hotfixu potrzebny jest odbiór syntetyczny na urządzeniu: zapis lokalny, konflikt dwóch profili, wybór lokalnej wersji, potwierdzony GET najnowszego JSON, kontrola wszystkich sesji/serii/snapshotów, kolejne zmiany, restart/offline i retry. Sam widok starszej lokalnej kopii sprzed importu nie potwierdza aktualnego stanu telefonu.
- Szkice pozostają lokalne zgodnie z dotychczasową zasadą; synchronizacja kopii zatwierdzonych danych ich nie usuwa ani nie przenosi na drugie urządzenie.
- Nie zmieniamy OAuth: GIS SPA token flow, `drive.appdata`, token tylko w pamięci, bez client secret i bez backendu. Po zimnym starcie/wygaśnięciu może być potrzebny przycisk **Połącz / odnów Google**. `prompt:''` korzysta z istniejącej sesji Google, ale popup, zgoda i brak interakcji nie są gwarantowane. Nie zapisujemy trwałego tokena i nie obiecujemy bezobsługowego odnowienia.
- Ten PR naprawia pilny blocker `keepLocal → outbox → upload → potwierdzenie`. Szersze rozpoznawanie identycznych modeli, automatyczne pobieranie na nieedytującym urządzeniu i ewentualny merge rozbieżnych wyników z Issue #23 pozostają osobną pracą. Obecna jawna ścieżka to podgląd/chronione przywrócenie albo nowa wersja lokalna z zachowaniem pozostałych kopii. Sam identyczny plan nie jest dowodem identycznej historii.
- Nie wykonano ręcznego wdrożenia ani żadnej operacji na rzeczywistych danych. Przed odbiorem na telefonie zachowaj aktualny pełny eksport JSON poza telefonem; aktualizacja i rozstrzygnięcie konfliktu nie wymagają usuwania pamięci aplikacji.
