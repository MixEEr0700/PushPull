# Issue #75 — projekt zapisu przyrostowego po etapie B

Status: **zatwierdzony do implementacji w Issue #82 (25.10.2026)**.
Realizacja do osobnego przeglądu, bez automatycznego scalania: [A / PR #83](INCREMENTAL_WRITE_STAGE_A.md),
[B / PR #84](INCREMENTAL_WRITE_STAGE_B.md), [C / integracja Matrix](INCREMENTAL_WRITE_STAGE_C.md).
Poniższy projekt pozostaje zapisem uzasadnienia i granic zatwierdzonej zmiany;
raporty etapów opisują implementację, weryfikację i ograniczenia.

Poprzedni etap B (PR #81) zachowuje obecny protokół i format bazy. Historia/plany właściciela są
testowe; projekt zakłada możliwość istotnej zmiany architektury. Nadal nie
przewiduje automatycznego usuwania danych ani przebudowy interfejsu Matrix.

## Dlaczego potrzebny jest następny protokół

W etapie B usunięto parsowanie własnego JSON, ponowne walidowanie niezmiennych
snapshotów i ponowne dekodowanie już potwierdzonego zapisu. Pozostają jednak
czynności zależne od całej historii: kodowanie/hash źródła, budowa pełnego
modelu, przepisanie tabel, pełny odczyt oraz zapis/odczyt dużego modelu.
`meta/state.rest.trainingJournal` zawiera wszystkie snapshoty, a
`meta/training-model-v1` cały aktualny backup źródłowy. Różnicowy zapis samych
wierszy wyników nie usuwa tych dwóch dużych rekordów.

Finalny natywny wynik V2 40 + raw 4 MiB po B: mediana 4766 ms, p95
5274 ms, max 5344 ms. Rozłączne etapy są w raporcie etapu B.
Wstępne próby i wcześniejsza seria późnego callbacku nie są dowodem natywnego
strict complete. Kontrola zegara i nowy test opisane są w raporcie. Całość to
Chromium/Linux, nie fizyczny Pixel. Dalsze drobne poprawki obecnej ścieżki nie
usuwają konieczności przetworzenia całego source i dużego rekordu modelu.

## Docelowa granica operacji

Wynik treningowy zapisuje osobne polecenie, np.:

```text
saveResult({sessionId, exerciseId, entry, expectedEntryHash,
            expectedRevision, expectedEpoch, snapshotHash, draftTicket})
```

Polecenie zawiera kompletny pojedynczy wynik, serie, segmenty, strony,
back-offy, notatki i nieznane pola wpisu. Snapshot/plan są referencjami do
niezmiennych obiektów, nie kopią całej historii. Dane są odłączane i w pełni
walidowane przed pierwszym await. Sam hash/ID nie zastępuje walidacji treści.

Obecna metoda `commit(data)` pozostaje dla importu/odtwarzania i rzadkich pełnych
zmian jako kosztowniejsza operacja przebudowy spójnego stanu **nowego** protokołu.
Nie wolno naprzemiennie używać starego writera v1 i nowego writera dla tej samej
rewizji. Kolejne polecenia obejmą start/zakończenie sesji i korektę daty.

Formularze i wygląd Matrix pozostają te same. Handler wyniku przekazuje zmianę
do backendu, zamiast tworzyć cały kandydat historii. UI publikuje wynik i usuwa
wyłącznie pasujący szkic po potwierdzonym strict complete. Błąd/CAS/quota/abort
pozostawia szkic i zatwierdzony poprzedni stan. Blokada/pending z #78 pozostaje.

## Format wewnętrzny bazy: jawny protokół 2

Propozycja: IndexedDB **version 2**, z zachowaniem istniejących stores i danych
v1 jako checkpointu aktualizacji. Nowe stores mają odrębne nazwy; ich końcowy
schemat wymaga przeglądu przed implementacją.

| Store | Zawartość |
|---|---|
| `journalObjects` | Niezmienne modele planów i inne JSON, adresowane SHA-256 dokładnych zakodowanych bajtów |
| `journalSnapshots` | Każdy oryginalny snapshot z własnym ID, sesją, czasem i metadanymi; osobna referencja do modelu |
| `journalSessions` | Rekordy sesji, stabilne ID i własna wersja/hash |
| `journalResults` | Kompletne wyniki wraz z seriami i nieznanymi polami, własna wersja/hash |
| `journalMetadata` | Kolejność, plany/catalog, ustawienia treningowe, notatki, technika i nieznane rozszerzenia |
| `journalState` | Wersja protokołu, epoch, rewizja, liczniki i korzeń integralności |
| `journalCheckpoints` | Oryginalny zweryfikowany stan v1 i informacje o przebiegu konwersji |

Obiekt planu powtarzany w 40 snapshotach można zapisać raz, jeśli **dokładne
bajty są identyczne**. Nie usuwa się żadnego logicznego snapshotu ani jego
metadanych. Obiekty tylko o podobnym ID/nazwie/dacie nie są łączone. Nieznane
pola oraz kolejność tablic i słowników są zachowane. Hash liczony po
`JSON.stringify` chroni także różnice kolejności kluczy; nie normalizujemy raw.
Dla raw używa się kodowania JSON string → UTF-8, zachowującego lone surrogates,
jak w istniejących kodekach. Metadane i referencje wewnętrzne są osobne od
pól użytkownika, aby obiekt wyglądający jak referencja nie zmienił znaczenia.

Wielkie archiwa pozostają niezmienne. Nowy indeks odwołuje się do zachowanych
rekordów/chunków z SHA, długością i kolejnością. Zapis wyniku nie odczytuje,
nie serializuje i nie hashuje ponownie całego archiwum. Duże nowe archiwum lub
checkpoint to osobna operacja, z obsługą przerwania i quota, nie ukryta część
każdego `saveResult`.

Nie wolno zostawić starego `training-model-v1` z podmienioną rewizją, udając,
że przedstawia nową historię. Stary model jest checkpointem; nowy reader
rozpoznaje jawnie protokół 2 i materializuje bieżącą historię z nowego stanu.

## Integralność i CAS

1. Odczytany obiekt niezmienny jest sprawdzany na podstawie pełnych bajtów,
   schematu i SHA. Dopiero taki głęboko niezmienny graf ma dowód do ponownego
   użycia w pamięci. Klucz `sha256:…` sam w sobie nie jest dowodem.
2. Wynik walidowany jest względem oryginalnego snapshotu, planu, wariantu,
   konwencji kg, ról serii, stron, segmentów i powiązań. Nie wybieramy danych
   według daty ani globalnego sequence.
3. W tej samej transakcji readwrite sprawdzane są pełne małe metadane root,
   epoch/rewizja/korzeń, poprzedni wynik oraz wymagane referencje. Zmienione
   metadane przy niezmienionej rewizji również powodują konflikt.
4. Writer stosuje `add` dla nowych obiektów niezmiennych. Istniejącego obiektu
   pod tym hashem nie zastępuje; sprawdza zgodność. Zmiana wyniku tworzy nową
   wersję i aktualizuje referencję w tej samej transakcji.
5. Readback obejmuje wszystkie zmienione rekordy, nowe obiekty, wymagane
   referencje i końcowy root. Sukces dopiero po `durability: strict` i complete.
6. Korzeń opiera się na hashowanych rekordach i indeksach, np. stronach drzewa
   Merkle. Zmiana aktualizuje ograniczoną ścieżkę, zamiast hash całego JSON.
   Sam hash poprzedniego root + numer rewizji nie zapewnia odczytu pełnego stanu.

To nowy kontrakt integralności, wymagający dowodu i testów. Zapis wyniku nie
jest ponownym fizycznym audytem wszystkich niezmienionych archiwów. Zgodność
zapewniają zweryfikowane referencje i niezmienność dozwolonego writera, a pełny
odczyt/audyt oraz eksport ponownie sprawdzają treści. Zmiana archiwum poza
protokołem musi zostać wykryta przy odczycie/audycie; nie wolno obiecywać jej
wykrycia w każdej operacji, która tego archiwum nie czyta. Testy muszą też
obejmować podmianę obiektu bez zmiany hasha/root i uszkodzenia indeksów.

## Odczyt, pamięć i zgodność kopii

Publiczny kształt danych dla UI i eksportu pozostaje zgodny z aktualnym.
Normalny handler wyniku nie może jednak wykonywać `database.value` ani
klonować całej historii po każdym commit. Backend zwraca potwierdzony mały
wynik i nową rewizję. UI aktualizuje odpowiadający mu fragment danych.

Niezmienne modele snapshotów można współdzielić w wewnętrznym odczycie.
Nie wolno oddać ich jako współdzielonych **mutowalnych** modeli wielu sesji.
Granica API zwraca niezmienne snapshoty albo odłączone kopie dla operacji
edycji. Plan bieżący i dane formularza nie dostają referencji pozwalającej
zmienić historyczny snapshot. To wymaga przeglądu adapterów danych, choć
nie zmienia projektu ekranów.

Readerzy i pliki v1–v6 pozostają zachowane. Eksport materializuje pełny stan,
łącznie z wszystkimi snapshotami, archiwami, metadanymi i szkicami w zakresie
obsługiwanym przez daną wersję. Obecnego eksportera v5/v6 nie rozszerza się
przy okazji writera. Aktualny source-backed v3 buduje się na żądanie z pełnej
materializacji, z istniejącym canonical/SHA. Ma przechodzić reader z #79.
Import/restore ma osobną pełną walidację, preimage i atomową zmianę root.
Nie wprowadza się nowego produkcyjnego przywracania v4/v6 ani Google Drive.

## Bezpieczna aktualizacja

- Najpierw odczyt i pełna weryfikacja starego stanu w izolowanych testach.
  Hashowanie/przygotowanie obiektów odbywa się przed transakcją upgrade;
  nie wolno czekać na crypto/sieć wewnątrz `onupgradeneeded`.
- Nowe stores tworzy krótka transakcja versionchange. Zachowuje stare stores
  i checkpoint; nie przerabia wielu MB synchronicznie w upgrade callback.
- Osobna transakcja konwersji sprawdza stare epoch/revision/źródło, zapisuje
  nową reprezentację, porównuje pełny materializowany stan i jego backup
  z oryginałem, wykonuje readback i strict complete. Dopiero wtedy oznacza
  protokół 2 jako aktywny. Nie wystarczy zgodność liczników.
- Jeśli stara karta zapisała wynik w czasie przygotowania, CAS konwersji
  odrzuca przygotowany kandydat. Nowy reader ponownie odczytuje aktualne
  niezmienione stores v1; nie przywraca automatycznie starszego checkpointu.
  Checkpoint musi być związany z ostatnią zweryfikowaną rewizją. Tryb pending
  udostępnia odczyt/eksport i wznowienie konwersji; nie uruchamia starego
  writera na przemian z nowym protokołem.
- Quota/abort/zamknięcie przed complete zachowuje poprzednią pełną historię.
  Po wersji 2 z nieukończoną konwersją nowy reader potrafi odczytać checkpoint
  v1 i wznowić lub bezpiecznie odmówić zapisu. Nie usuwa danych dla odzyskania
  miejsca. `storage.estimate()` jest wskazówką, nie gwarancją przydziału quota.
- `onversionchange` blokuje nowe operacje starych kart i zamyka połączenie.
  Upgrade czeka na wszystkie stare połączenia. Żadnego wymuszonego reloadu
  formularza ani traktowania samego flush/reload jako bezstratnego snapshotu.
  Przed zamknięciem starej karty musi być potwierdzony szkic lub pobrana kopia
  niezapisanej pracy. Brak odpowiedzi karty nie jest dowodem kompletności.
- Kod v1 otwierający bazę v2 dostanie VersionError i ma pozostać fail-closed,
  bez resetu lub inicjalizacji pustej bazy. Instalator SW nadal weryfikuje
  wszystkie pliki i czeka na zamknięcie starych klientów. Najpierw testy
  zgodnego czytnika i aktualizacji, potem publikacja.
- Powrót do binarnego DB v1 nie jest prostym cofnięciem JS: IndexedDB nie
  obniża wersji. Rollback wymaga wydania zgodnego z protokołem 2, odczytującego
  checkpoint/bieżący stan, lub jawnego pełnego eksportu/odzyskania w osobnym
  profilu. Nie przewiduje się automatycznego usunięcia DB v2.

## Etapy wdrożenia i kryteria odbioru

A. Odseparowany protokół, materializer i oracle: identyczna kompletna historia
oraz backup wobec aktualnego readera, także dla nieznanych pól i archiwów.
Bez podłączenia do produkcyjnego zapisu.

B. Writer i konwersja wyłącznie na izolowanych bazach: CAS, quota, abort,
przerwanie każdej fazy, dwa nowe klienty, stary klient, uszkodzone rekordy,
niepełna konwersja i restart; zgodność snapshotów/planów/wyników/szkiców.

C. Podłączenie polecenia zapisu wyniku pod niezmieniony UI, jawna bezpieczna
aktualizacja i testy offline/PWA. Nie przyspieszać, publikując sukces przed
complete lub przenosząc wielosekundową pracę na pierwszy klik po starcie.

Pomiary: pusta/4/40/400 sesji V2, małe/duże ASCII i escaped archiwa; nowe
wyniki i korekty, pierwszy oraz kolejne zapisy, restart/aktualizacja,
kwanty czasu input → strict complete i UI-ready, peak/retained memory.
Na fizycznym Pixel 9 z ustaloną wersją kodu/Chrome/Androida: seria zwykłych
zapisów, mediana/p95/max; warunek odbioru <=1000 ms dla badanych typowych
operacji. Nie jest to gwarancja hard real-time przy dowolnym obciążeniu OS.
Bez tego pomiaru nie deklarować osiągnięcia celu Androida.
