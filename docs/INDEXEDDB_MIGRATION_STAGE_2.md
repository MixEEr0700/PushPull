# Etap 2 — IndexedDB i odzyskiwanie danych

Punkt wyjścia: `origin/main` po scaleniu PR #1, commit `99902a22c820d228b2e6cd3cf0fb49371b1bf3ce`. Parametry demonstracyjnego V2, stabilne ID ćwiczeń, CSS, karty i moduł statystyk pozostają zachowane. Nie wdrożono Drive ani publikacji aplikacji.

## Baza i model źródłowy

Nazwa bazy: `pushpull`, wersja schematu IndexedDB: **1**. Wersja starego dokumentu danych pozostaje **v1**; pełny format eksportu ma **version: 2**, ponieważ obejmuje także wersje planów i archiwalne kopie. Są to trzy odrębne numery wersji.

| Object store | Zawartość |
| --- | --- |
| `meta` | Rekord `state`: pozostałe pola dokumentu v1, kolejność planów/wersji, obecność opcjonalnej historii zmian, liczby rekordów, rewizja, odcisk SHA-256 danych i katalogu, dokładny tekst źródłowego localStorage, znacznik zweryfikowanej migracji. |
| `plans` | Cztery plany treningów PUSH A, PULL A, PUSH B, PULL B, etykieta niezweryfikowanego V2 i identyfikator bieżącej wersji. |
| `planVersions` | Niezmieniane wcześniejsze snapshoty parametrów ćwiczeń: ID, nazwy, kolejność, serie, zakresy, tempo, RIR i inne oryginalne pola parametrów. Bez notatek i obliczonego tonażu. |
| `exercises` | Oryginalne ID ćwiczenia, plan, pozycja oraz bieżące parametry. Nie generujemy nowych ID istniejących ćwiczeń. |
| `sessions` | Oryginalny ID, pozycja w dokumencie, cały rekord sesji v1 oraz odniesienie do wersji planu i pochodzenie tego odniesienia. |
| `entries` | Oryginalny ID wyniku, pozycja i wszystkie pola v1 poza tablicą serii; rozróżnienie brakującego `series`, `null` i tablicy. |
| `sets` | Pojedyncze serie z oryginalnymi wartościami ciężaru i powtórzeń oraz dodatkowymi polami, ID wpisu i kolejnością. Klucz techniczny: JSON `[entryId, position]`. |
| `notes` | Dokładny tekst istniejącej notatki ćwiczenia, z pochodzeniem `legacy-shared`. Nie zgadujemy, które fragmenty są od trenera, a które od użytkownika. |
| `changes` | Znaczniki zmian techniki/parametrów z oryginalną datą, opisem, ćwiczeniem i kolejnością. |
| `backups` | Dokładne źródło migracji, wcześniejsze kopie localStorage, pełne snapshoty przed importem i zapisy starszej wersji przy konflikcie. Każda kopia ma ID, rodzaj, datę i surową treść. |

Tonaż, statystyki i wykresy są obliczane z danych źródłowych. Nie zapisujemy ich jako drugiego źródła prawdy. Starszych wyników bez tablicy serii nie mnożymy ani nie uzupełniamy.

Stare v1 nie przechowywało historycznych wersji planów. Migracja zapisuje dostępny bieżący snapshot i oznacza odniesienia historycznych sesji jako `legacy-current-only`; **nie twierdzi**, że zna parametry obowiązujące w dniu starego treningu. Nowe sesje otrzymują `session-start`. Kolejne snapshoty zachowują poprzednie wersje. Nie wprowadzono edytora planów ani nowych funkcji treningowych.

## Protokół migracji

1. Odczytaj dokładny tekst `pushpull_skeleton_v1`. Brak klucza jest czymś innym niż pusty ciąg, `null` w JSON, błąd dostępu lub nieobsługiwana wersja.
2. Otwórz IndexedDB i odczytaj ją w spójnej transakcji. Istniejąca zweryfikowana baza jest nadrzędna — nie odtwarzaj jej ze starego localStorage przy każdym uruchomieniu.
3. Jeżeli nie ma jeszcze bazy i znacznika wcześniejszego użycia, zwaliduj v1 przez walidator etapu 1. Nowy użytkownik bez klucza otrzymuje zweryfikowany pusty stan, bez tworzenia pustego klucza historii w localStorage.
4. Przygotuj rekordy źródłowe i SHA-256 kanonicznego dokumentu wraz z katalogiem wersji. Nie zmieniaj źródła.
5. W **jednej transakcji readwrite ze strict durability**, obejmującej wszystkie magazyny, sprawdź oczekiwaną rewizję i aktualność źródła. Zapisz oryginalny tekst oraz wcześniejsze kopie, rekordy źródłowe i niepotwierdzone metadane.
6. Jeszcze wewnątrz tej samej transakcji odczytaj zapisane rekordy i kopie. Porównaj liczby, wartości, identyfikatory i relacje. Odtwórz v1 oraz katalog z rekordów i porównaj je ze źródłem. Sprawdź też zgodność rekordów z ponowną normalizacją, aby wykryć osierocone serie/notatki i niespójne klucze.
7. Dopiero po porównaniu zapisz `verified: true` i `migration.complete: true`. Udostępnij dane aplikacji dopiero po **`transaction.oncomplete`**, nie po sukcesie pojedynczego `put`/`add`.
8. Zapisz osobny znacznik `pushpull_indexeddb_owner = pushpull:1`. **Nie usuwaj i nie nadpisuj** `pushpull_skeleton_v1` ani dotychczasowych kluczy kopii.

Nie ma widocznej połowy migracji: anulowanie, błąd zapisu, quota i zamknięcie aktywnej karty wycofują całą transakcję. Po ponownym uruchomieniu migracja może bezpiecznie zacząć od niezmienionego źródła. Jeśli proces zakończy się po commit, lecz przed zapisaniem znacznika localStorage, kolejny start weryfikuje gotową bazę i uzupełnia znacznik. Jeśli zapisu znacznika nie da się wykonać, dane IndexedDB pozostają zachowane, ale uruchomienie jest blokowane do usunięcia przyczyny błędu.

Istniejąca baza jest przy każdym otwarciu sprawdzana przez liczniki, rekonstrukcję, walidację i SHA-256. Niekompletna lub uszkodzona baza wywołuje ekran odzyskiwania, bez automatycznego resetu. Sam znacznik z brakującą bazą również blokuje start: stara kopia localStorage mogłaby nie zawierać nowszych treningów.

## Normalne zapisy, karty i starszy kod

Zapisy aplikacji są asynchroniczne i kolejkują zdarzenia UI. Każdy zapis wszystkich powiązanych danych przechodzi tę samą walidowaną transakcję, odczyt kontrolny i zakończenie `oncomplete`. Nieudany zapis przywraca ostatni zatwierdzony stan pamięci; nie usuwa roboczych serii i nie pokazuje „Wynik zapisany”.

Porównanie **przechwyconej przed operacją** rewizji z rewizją w transakcji zapobiega nadpisaniu nowszego stanu przez inną kartę, a także przez dwie równoczesne operacje jednego backendu. BroadcastChannel informuje pozostałe karty o zmianie; nieaktualna karta wymaga odświeżenia. Rewizja pozostaje zabezpieczeniem także bez BroadcastChannel.

Uaktualniony adapter localStorage odmawia zapisu/importu po stwierdzeniu znacznika IndexedDB. **Nie można retroaktywnie zatrzymać całkowicie starego kodu przechowywanego w cache lub uruchomionego z innego źródła.** Dlatego nowy kod porównuje dokładny tekst starej bazy przy uruchomieniu oraz przed i podczas zapisu; reaguje także na `storage`. Zmiana przez starą aplikację blokuje edycję zamiast po cichu rozdzielać historię. Obie wersje można pobrać. Ich połączenie wymaga świadomego odzyskania, nie automatycznego wyboru „nowszej” kopii.

Nie istnieje wspólna transakcja IndexedDB i localStorage. Zmiana przez całkowicie stary kod tuż po ostatniej kontroli zostanie wykryta przez zdarzenie lub następny start/zapis; nie da się obiecać atomowego wykluczenia takiego starego procesu bez zmiany jego kodu. Nigdy nie należy równocześnie edytować historii w starej i nowej aplikacji.

## Kopie i import

Pełny eksport JSON:

```json
{
  "format": "pushpull-backup",
  "version": 2,
  "data": {"version": 1, "exercises": "…", "sessions": "…", "entries": "…"},
  "catalog": {"plans": [], "planVersions": [], "sessionVersions": {}},
  "archives": []
}
```

Skróty w przykładzie są wyłącznie objaśnieniem; rzeczywisty eksport zawiera pełne obiekty i wszystkie rekordy. `archives` obejmuje zachowane kopie i oryginał migracji, także surowe niepoprawne dane wymagające ręcznego odzyskania. Snapshoty tworzone przed importem nie zagnieżdżają ponownie całego archiwum, co ogranicza narastanie kopii.

Import przyjmuje stare v1 oraz pełny format 2. Weryfikuje dokument, wersje planów, odwołania sesji i strukturę archiwum. Nieobsługiwane formaty i dodatkowe nierozpoznawane pola kontenera są odrzucane, zamiast znikać podczas odtwarzania. Dodatkowe pola oryginalnych danych v1 są nadal zachowywane.

Po potwierdzeniu użytkownika import w tej samej transakcji zabezpiecza dotychczasową historię i zapisuje nową. Przy konflikcie ze starą aplikacją zabezpiecza także jej aktualny tekst. Archiwalne kopie nie są kasowane; przy kolizji technicznego ID kopii nadawany jest nowy ID z zachowaniem `sourceId`. Nie dotyczy to ID ćwiczeń, sesji ani wyników. Każdy błąd wycofuje import razem z jego zapisami. Anulowanie niczego nie zapisuje.

Eksport v2 nie jest przeznaczony do importu do starej aplikacji v1. Nowa aplikacja zachowuje zgodność odczytu starych kopii; nowy format jest potrzebny do pełnego odtworzenia wersji planów i archiwum.

## Odzyskiwanie — instrukcja dla użytkownika

1. Nie czyść pamięci przeglądarki, nie usuwaj IndexedDB i nie wracaj do starszej aplikacji do dalszej edycji.
2. Jeśli pojawia się ekran odzyskiwania, pobierz dostępną historię IndexedDB oraz oryginalny zapis localStorage. Zachowaj je poza przeglądarką, zanim wybierzesz kopię do importu.
3. W sekcji zachowanych kopii pobierz wybraną kopię sprzed migracji/importu. Możesz też użyć pełnego JSON wyeksportowanego wcześniej na urządzenie.
4. Wczytaj poprawną kopię przez „Wczytaj poprawną kopię JSON” lub import w zakładce Dane. Dopiero po walidacji potwierdź zastąpienie aktywnej historii. Bieżące dane zostaną wcześniej zabezpieczone w transakcji.
5. Przy konflikcie ze starą wersją porównaj obie historie. Import wybranej kopii zachowa obecną bazę i konfliktowy zapis w archiwum, ale **nie połączy automatycznie rozbieżnych treningów**. Jeśli obie zawierają nowe sesje, ich scalenie wymaga osobnego, kontrolowanego zadania na kopiach.
6. Po odtworzeniu sprawdź sesje, daty, notatki i wyniki oraz wykonaj nowy pełny eksport.

Jeśli integralność samej IndexedDB jest uszkodzona, przycisk pobrania bazy udostępnia techniczny dokument `pushpull-idb-recovery` z surowymi rekordami i kopiami. Taki zrzut **nie jest automatycznie importowany jako poprawna historia**. Zachowaj go do ręcznego odzyskania; najpierw spróbuj pobrać zwalidowaną wcześniejszą kopię z listy.

Gdy przeglądarka blokuje IndexedDB, ma brak miejsca lub wymaga zamknięcia innych kart podczas zmiany wersji schematu, usuń przyczynę i ponów uruchomienie. Nie używaj resetu bazy jako naprawy. Jeżeli nie można odczytać magazynów, import nie rozpocznie kasowania danych.

## Offline, aktualizacja i granice gwarancji

Service worker używa `pushpull-v4-indexeddb`, zapisuje `indexeddb.js` i pobiera zasoby wyłącznie z aktualnego cache. Dotychczasowe cache oraz localStorage nie są usuwane. Migracja nie wymaga sieci, gdy nowy komplet zasobów jest już dostępny offline. Test obejmuje rzeczywistą aktualizację workera etapu 1 do etapu 2, błąd migracji i poprawne ponowienie offline.

Lokalna baza i lokalne archiwum nie chronią przed awarią urządzenia ani usunięciem całego magazynu origin. Jeśli jednocześnie znikną IndexedDB, localStorage i znacznik, aplikacja nie może odróżnić tego od nowej instalacji. **Konieczny jest regularny eksport poza przeglądarkę.** Strict durability i transakcje nie są obietnicą odporności na każdy błąd sprzętu.

Zapisy aktualnie rekonstruują i weryfikują cały dokument oraz rekordy źródłowe; jest to koszt proporcjonalny do historii, bez benchmarku dużych baz. Nie wdrożono indeksów analitycznych ani optymalizacji częściowych zapisów. Testowe dane odpowiadają rzeczywistej strukturze v1 z zatwierdzonych źródeł, nie prywatnej historii użytkownika. Nie weryfikowano planu V2 z dokumentem trenera ani instalacji na fizycznym Androidzie.

Instrukcje uruchamiania testów i ich wyniki: [raport etapu 2](STAGE_2_TEST_REPORT.md).
