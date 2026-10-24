# Issue #68 — raport i propozycja kontraktu do zatwierdzenia

Baza analizy: `main` `15ec03277dde2cc32e43f8543d82be1260ffe7a0`, po PR #67. Przeczytano plan nadrzędny, Issue #68, kod zapisu/szkiców i eksportu/podglądu v5. **Nie zmieniono kodu produkcyjnego ani kontraktu v5.** Nowy format i przyszłe API opisane poniżej są projektem, nie implementacją.

## 1. Fakty z aktualnego kodu

### Oficjalny trening a niezatwierdzony formularz

`indexeddb.js` utrwala oficjalne dane: sesje, aktywne `activeId`, także `status:'active'`, zatwierdzone wyniki, katalog i model/snapshoty. Eksport v5 obejmuje ten logiczny snapshot oraz wszystkie przekazane archiwa. Rozpoczęta sesja i już zapisane wyniki NIE znikają z kopii tylko dlatego, że sesja nie jest zakończona.

Brakuje **niezatwierdzonych zmian formularzy**: nowych kg/reps/serii, poprawek zatwierdzonego wyniku, struktur L/P/dropów/grup, stanów edytora, szkiców innych sesji i kart. Nie są zatwierdzonymi wynikami i nie wolno dodawać ich do statystyk. Nie wszystkie lokalne zmiany aplikacji są szkicami treningu: np. otwarta karta, data nowej sesji przed jej rozpoczęciem czy niezatwierdzony formularz ustawień nie należą do obecnego kontraktu szkiców. Nie obiecywać backupu dowolnego stanu DOM.

### Schemat szkicu i dwa trwałe źródła

`model/workout-drafts.mjs:capture` tworzy rekord:

```text
key: "workout-draft:" + id
id, version: 1, token, sequence
sessionId, exerciseId
context, baseline, kind, value, updatedAt
```

- `id`: niezależna gałąź edycji. Nowa karta/strona lub edycja bez jawnego wznowienia tworzy nowe ID; nie ma jednego wspólnego szkicu na ćwiczenie.
- `token`: nowy losowy identyfikator każdej wersji; służy do CAS. To NIE token OAuth, NIE checksum i NIE globalna rewizja.
- `sequence`: rośnie wewnątrz danej aktywnej gałęzi, nie daje globalnego porządku różnych kart/ID. `updatedAt` jest czasem ściennym, nie rozstrzyga konfliktów.
- `context` z `app.js:bindingFor`: sessionId, exerciseId, sessionType, status, snapshotId, planVersionId, positionId, variantId i legacyDefinition (id/name/sets/target/tempo/rir dla legacy).
- `baseline`: cały zatwierdzony wynik wyjściowy lub null. Przy wznowieniu sprawdzana jest dokładna zgodność context i baseline; późniejszy zapis oficjalny używa `assertCurrent`.
- `kind:'legacy'`, `value`: kg/reps jako stringi, tablica series oraz stan open/custom. `kind:'v2'`, `value`: performance z ID wierszy/segmentów, L/P, parametrami oraz open/custom/sidePairs. `editorValueValid` sprawdza kształt, nie poprawność liczbową zatwierdzonego wyniku. Pusty string lub np. `1,` to prawidłowa treść niedokończonej edycji.

IndexedDB: istniejąca baza `pushpull`, store `meta`, klucze `workout-draft:<id>`. `readDrafts()` czyta te rekordy; `writeDraft(record,expectedToken)` sprawdza klucz, porównuje token poprzednika, zapisuje i weryfikuje odczyt w transakcji. `removeDraft` sprawdza token/sequence, aby nie usunąć nowszej wersji. Nie jest to walidator całego przyszłego importu szkiców.

localStorage: klucze `pushpull_workout_draft_v1:<id>:<token>`, wartość JSON całego rekordu. Zapis bufora następuje synchronicznie przy capture, przed zakończeniem IndexedDB. Starszy wariant uszkodzonego wpisu jest odczytywany jako `{id,corrupt:true,raw}` z klucza prefix+id. Po udanej transakcji `clearBuffer` usuwa pokryte wersje tego ID o sequence <= zapisanej. Nowsze wersje i inne ID pozostają. Niedostępność obu pamięci może pozostawić ostatnią wersję jedynie w pamięci formularza.

### Pamięć karty, kolejka i zdarzenia

Moduł trzyma `active` (binding, record, durableToken, parent), `restored`, `records`, kolejkę i statusy błędów. Legacy formularze mają dodatkowo `resultDrafts` w app.js; V2 — wewnętrzną mapę edytora i `rich.state()`. Zdarzenia input są obsługiwane synchronicznie; część operacji strukturalnych/change/click korzysta ze wspólnej kolejki `actions`. Tekst, którego przeglądarka nie przekazała jeszcze jako zdarzenie (np. IME/composition), nie musi być w szkicu.

`flush()` zwraca bieżącą kolejkę tylko tej instancji. Nie wymusza capture całego DOM, nie czeka na inne karty, nie gwarantuje braku późniejszego enqueue. Błędy są przechwytywane wewnątrz zapisu; **flush może się spełnić po nieudanym writeDraft**. Trzeba sprawdzać błędy i pokrycie buforem, nie samo zakończenie Promise. `storageError` jest zapamiętywany; nie jest wiarygodnym chwilowym potwierdzeniem kompletności. `reload()` może zwrócić część danych przy `readError`; nie wolno interpretować braku rekordów jako pewnego pustego zbioru.

### Rewizje i kilka kart

Zapis szkicu w `meta` nie zwiększa `meta.state.revision` historii i nie nadaje globalnej rewizji zbioru szkiców. BroadcastChannel obecnie reaguje na zmiany oficjalnych danych/modelu; storageListener historii nie jest koordynatorem bufora szkiców. Sprawdzenie `database.revision` przed/po v5 nie wykrywa samej edycji szkicu.

`reload()` łączy IDB i bufor: wybiera większe sequence dla ID; przy równym sequence i innym tokenie dokłada gałąź pod kluczem pomocniczym. Nie zachowuje wszystkich wersji źródłowych. Test diagnostyczny pokazuje kolejność: IDB a/seq1, bufor b/seq1 potem c/seq2 daje widok c+b; bufor c potem b daje c. To potwierdza, że **widok nie jest kolektorem dowodów do pełnej kopii**. Nie dowodzi usuwania źródłowych zapisów przez reload ani awarii danych konkretnego użytkownika.

## 2. Co obejmuje obecny eksport

| Warstwa | v5 / oficjalny JSON | Pozostaje lokalnie |
|---|---|---|
| Zapisana aktywna sesja, activeId, wyniki zatwierdzone | tak, z historycznym snapshotem | — |
| Plany/model/katalog, historia i archiwa raw | tak, w granicach istniejącego kontraktu | starszy bridge bez trainingJournal ma bezpieczną odmowę v5 |
| `meta` workout-draft, pending localStorage, pamięć edytora | nie | tak, osobny eksport pojedynczego szkicu |
| Tokeny CAS i powiązania szkicu z baseline | nie jako sekcja szkiców | tak |
| Drive/OAuth, ustawienia, kolejki transportu | nie | tak; nie wolno ich dołączać przez zrzut całego meta/localStorage |

`exportLocalV5` pobiera `database.export()` i kontroluje rewizję historii. Nie wywołuje kolektora szkiców. C1 odtwarza tylko zweryfikowany plik do bazy w pamięci i jawnie zwraca `draftsIncluded:false`. Pełny model v3 i starsze pliki JSON też nie są kopią lokalnych formularzy. Opaque archiwum może zawierać dowolny historyczny tekst — nie przeszukujemy jego wnętrza w celu zgadywania, że zastępuje bieżące szkice.

## 3. Warianty kontraktu i rekomendacja

| Wariant | Zgodność | Ocena |
|---|---|---|
| Nowe „opcjonalne” top-level pole w v5 | stary `exact()` je odrzuci; checksum wymaga zmiany | odrzucić jako cichą zmianę v5 |
| Szkice ukryte w metadata albo pseudoarchiwach v5 | stare czytniki mogą zachować dane, ale C1 nie rozpozna gwarancji szkiców/limitu/restore | nie używać do obietnicy pełnej kopii |
| Drugi plik szkiców | nie zmienia v5, ale łatwo zgubić parę lub pomylić bazę | opcja ratunkowa, nie rekomendowany pełny backup |
| Jawny v6 zawierający v5 + sekcję szkiców | nowy reader czyta v1–v6; stare aplikacje jawnie odrzucają v6 | **rekomendacja do zatwierdzenia** |

Nie zmieniać istniejących plików v5, eksportera ani dekodera. Nowy reader v6 deleguje v1–v5 do istniejącego readera; v6.history również waliduje nim. Stare v5 nadal mają status „szkice nieobjęte formatem”, nigdy „0 szkiców potwierdzone”. Starsza aplikacja ma jawnie odrzucić v6, zamiast przywrócić tylko historię i po cichu zgubić szkice. Bez automatycznej konwersji baz i Drive.

## 4. Dokładna propozycja v6 (NIEIMPLEMENTOWANA)

Top-level dokładnie:

```text
{ format:"pushpull-backup", version:6, createdAt:<ISO UTC>,
  history:<pełny niezmieniony dokument v5>,
  capture:{version:1,historyRevision:<safe integer>,startedAt:<ISO UTC>,
           completedAt:<ISO UTC>,consistency:"observed-stable",
           scope:"observed-origin"},
  drafts:{format:"pushpull-drafts",version:1,
          encoding:"json-string-utf8",compression:"gzip",
          storedBytes,decodedBytes,storedSha256,decodedSha256,data:<base64>},
  integrity:{algorithm:"SHA-256",digest:<hex>} }
```

`drafts` zawiera jeden ograniczony blob, po rozpakowaniu kanoniczny token JSON-string-UTF8, jak istniejące bloby, zachowujący również samotne surogaty. String jest tekstem dokumentu:

```text
{ format:"pushpull-draft-evidence",version:1,
  sources:[
    {source:"idb-meta",storageKey:<klucz>,value:<pełny oryginalny rekord>},
    {source:"local-buffer",storageKey:<klucz>,raw:<dokładny oryginalny string>},
    {source:"editor-memory",record:<pełny record>,binding:<binding>,
     durableToken:<token|null>,parent:<pełny parent|null>}
  ] }
```

`sources` jest listą dowodów, a nie automatycznie zredukowanym „najnowszym szkicem”. Zachować wszystkie własne pola rekordów/metadanych, osobne ID i różne treści z tym samym tokenem. Dokładne duplikaty można sklasyfikować jako takie po walidacji, ale nie wycinać źródeł z pliku. IDB nie ma oryginalnego tekstu JSON: gwarancja dotyczy wartości/typów/kluczy rekordu. Dla localStorage gwarantujemy dokładne code units raw. Nie pobierać innych kluczy meta/LS, DOM, sesji logowania, OAuth czy tokenów Drive.

Źródła niepoprawne nie są wyrzucane. Poprawna integralnie sekcja może zawierać uszkodzony JSON bufora jako opaque raw, ale czytnik klasyfikuje go do kwarantanny bez możliwości wznowienia. Klasyfikację można wyliczyć z dowodów; nie ufamy etykiecie statusu zapisanej przez writer. Brak treści/ID/tokenów w logach i komunikatach UI. Tokeny szkiców pozostają częścią chronionej kopii, nie są ujawniane w raporcie.

SHA całego manifestu v6 obejmuje kanoniczny dokument bez własnego digest, w tym history, capture, sekcję drafts i jej data. Wewnętrzny v5 zachowuje obie swoje warstwy manifestów i checksum blobów. Draft blob ma obie sumy bajtów zapisanych/rozwiniętych, kontrolę rzeczywistej dekompresji, base64/UTF-8/JSON i długości. **SHA nie jest podpisem tożsamości ani szyfrowaniem**; to integralność, nie dowód autentyczności.

### Proponowane budżety — do akceptacji i walidacji na fixtures

- Cały v6: nie więcej niż obecne 32 MiB, łącznie z opakowaniem. V5.history sam nadal podlega istniejącym limitom.
- Draft blob: <=4 MiB rzeczywiście rozwiniętych bajtów tokena; <=4 MiB zapisanych bajtów. Nie tworzyć wielkiego JSON przed preflight.
- <=256 logicznych tożsamości szkiców i <=1024 źródła; pojedyncze źródło <=1 MiB po kodowaniu. Każda kwarantanna i kopia konfliktowa zużywa ten sam budżet.
- Historyczne tokeny logiczne liczone z powtórzeniami PLUS cały rozwinięty blob szkiców <= obecnego 128 MiB. Dekoder v5 nadal pilnuje limitów fragmentów i swoich unikalnych blobów. Nie zwiększamy limitu live 64 MiB ani budżetów, aby zmieścić nową sekcję.
- JSON nadal ma limit głębokości 64 i tokenów 1 000 000; wrapper/dodatkowa sekcja mogą wymagać osobnych niższych limitów parsera. Żadnych cykli, funkcji, getterów, nieprzenośnych liczb, referencji URL lub nieznanych algorytmów.

To propozycja konserwatywnej polityki, NIE pomierzona granica Androida. Każde przekroczenie oznacza odmowę pełnego eksportu, bez ucinania listy, usuwania archiwów czy szkiców. Opcjonalnie można osobno zaoferować starą kopię v5 opisaną jako NIEZAWIERAJĄCĄ szkiców — bez automatycznego fallbacku i fałszywego sukcesu. Brak gwarancji niskiego RAM: pozostają live/model, staging i dowody; nie powielać 65 MiB raw przez canonicalizację całych archiwów do porównania.

## 5. Proponowany snapshot i jego granice

1. Nowy, tylko do odczytu kolektor dowodów — NIE `savedDrafts.records` — ma zarejestrować wersje pamięci aktywnego edytora, parent/binding i status pokrycia źródeł. Bez confirmed/discard/remove/clearBuffer podczas tworzenia pliku. Nie wymyślać rekordu dla danych, których nigdy nie przechwycono.
2. Capture aktualnego edytora i zakończenie wcześniejszych działań jego karty. Jeśli przyszły krok wybierze flush do IDB, jest to zapis i musi być jawnie częścią zatwierdzonego etapu; sam backup nie może traktować jego zakończenia jako sukcesu trwałości. Rekomendowany kolektor potrafi zachować także stan tylko w pamięci i buforze, zamiast wymuszać trwały zapis jako warunek zachowania wartości.
3. Oficjalne state/model/tabele/archiwa i trwałe szkice powinny zostać odczytane w JEDNEJ readonly transakcji IDB, potem zweryfikowane istniejącymi walidatorami. `database.export()` jest widokiem uchwytu z pamięci i sam nie daje takiego wspólnego snapshotu. Wymagane przyszłe nowe API odczytu, bez zmiany schematu bazy, musi zostać osobno zaimplementowane/testowane po decyzji.
4. localStorage nie uczestniczy w transakcji IDB. Odczytać listę kluczy i dokładne raw przed/po, porównać kompletny wektor dowodów i pamięci edytora (nie tylko revision i timestamps). Jeśli zmieniają się podczas kopiowania — bounded retry albo anulowanie. Brak dostępu do IDB/LS nie znaczy pustej sekcji. Nieznany stan -> nie wydawać kopii oznaczonej jako pełna.
5. Przyszła współpraca kart wymaga protokołu zatrzymania edycji/ACK na czas snapshotu i inwentaryzacji aktywnych edytorów. Obecni writerzy nie biorą wspólnego Web Lock; samo dodanie locka do eksportera niczego nie zabezpieczy. Nie można ufać ACK zamrożonej starej karty lub zakładać, że znamy wszystkie karty z samych odpowiedzi BroadcastChannel.
6. Dwa stabilne odczyty są testem koniecznym, ale NIE dowodem globalnego atomowego punktu w historii IDB+LS+wszystkich kart. Dlatego capture ma `observed-stable/observed-origin`, nie „complete-device”. Dla silniejszej gwarancji trzeba najpierw uzgodnić protokół wszystkich writerów, zachowanie starych kart i granicę „pełnej kopii”. Przy nieznanej/starej/niereagującej karcie rekomendacja: odmowa takiej deklaracji i polecenie zamknięcia pozostałych okien; nie twierdzimy, że technicznie wykryto każdą uśpioną kartę.
7. Po zebraniach walidować odłączone dowody, historia nadal pozostaje dokładnie tym samym logicznym snapshotem. Wygenerować/odczytać v6 w pamięci i porównać wszystkie dane i wszystkie dowody. Dopiero potem download. Późniejsza nowa edycja nie jest częścią wcześniejszego snapshotu; UI musi opisać granicę, nie obiecywać ciągłej synchronizacji. Abort/błąd/brak pamięci: brak częściowego sukcesu, zero kasowania źródeł.

## 6. Walidacja i przyszłe odzyskiwanie (bez implementacji)

- Walidować `key=id`, top-level session/exercise względem context, version, bezpieczne sequence>0, tokeny, daty, kind i komplet struktury value. Nie normalizować kg/reps ani ID; nie używać walidatora zatwierdzonych wyników do odrzucania niedokończonego tekstu.
- Rekord IDB z wartością spoza kontraktu przenośnego JSON (np. cykl, Date/Blob wymagający nowego kodowania) nie daje się bezstratnie zachować przez zwykłe JSON.stringify. W tym projekcie oznacza odmowę pełnego eksportu, nie cichą normalizację lub pozorną kwarantannę JSON. Ewentualne kodowanie takich typów wymaga osobnej decyzji.
- Relacje z przywracaną historią: sesja, ćwiczenie, snapshot, wersja planu, wariant i baseline. Niezgodne szkice do odzyskiwania, nie do automatycznego nadpisania. Szkic może być korektą starej sesji, nie tylko aktywnej; zachować wszystkie sesje i gałęzie.
- Ten sam id/sequence z różnymi tokenami/treścią to konflikt. Token nie potwierdza integralności. Nie wybierać „zwycięzcy” po dacie ani przez globalny max(sequence). Zepsuty rekord zachować jako dowód, ale nigdy nie podawać go bez kontroli do resume.
- Najpierw rozszerzyć C1 o odczyt i odtworzenie w izolowanej pamięci, wraz z porównaniem dowodów. Produkcyjny restore to osobny etap: preimage obejmujący też obecne szkice, obsługa LS poza transakcją, rollback, ochrona rewizji/tokenów oraz brak reanimowania starych writerów z zapisanymi w pliku CAS tokenami.
- Zaimportowane tokeny/ID zachować w dowodach jako provenance, a nowe operacyjne gałęzie tworzyć przez zatwierdzony adapter odzyskiwania z nową tożsamością/CAS i jawnym powiązaniem źródła. Nie zapisywać ślepo całego snapshotu meta ani nie przenosić bufora LS pod aktywne oryginalne klucze. Sam import nie zatwierdza wyników ani nie zmienia tonażu/rotacji.
- Przywrócenie historii i szkiców do IDB oraz LS nie jest jedną obecną transakcją. Jeśli przyszły projekt potrzebuje migracji/nowego indeksu/tombstones/protokołu writerów, najpierw przedstawić konsekwencje właścicielowi. W tym etapie nie zmieniamy storage i nie implementujemy restore.

## 7. Scenariusze i kryteria przyszłego odbioru

| Scenariusz | Oczekiwany dowód |
|---|---|
| Legacy, aktywna sesja, niepełne kg/reps i różne serie | sesja/activeId w history; exact value/context/baseline w evidence; brak nowego oficjalnego wyniku |
| V2 L/P/drop/back-off/grupy, TEST V3, korekta dawnej sesji | wszystkie ID, parametry, sidePairs, snapshoty i baseline identyczne po odczycie |
| Pending LS przy blokowanej/nieudanej transakcji; oba storage niedostępne | zachowanie obserwowanego bufora/pamięci; brak fałszywego „0 szkiców” i brak pełnego sukcesu przy nieznanym pokryciu |
| 2 karty, różne ID; równe sequence/różne tokeny; wznowienie parent | wszystkie dowody i gałęzie, brak nadpisania; jawna klasyfikacja konfliktów |
| Edycja podczas hash/kompresji/odczytu; nieodpowiadająca stara karta | bounded retry/odmowa silnej gwarancji; brak udawania atomowości wielu pamięci |
| Ten sam token z różnym payload; uszkodzony JSON; niespójny context | zachowane dowody/kwarantanna; brak automatycznego resume, bez raw w komunikatach |
| >64 MiB archiwum + wiele szkiców, Unicode/NUL/samotne surogaty/null | exact code units i metadata; archiwa liczone logicznie, nie jako fragmenty; wspólny limit 128 MiB |
| Limit pliku/draft blob/tokenów/referencji; bomba dekompresji; zmieniony manifest | pełna odmowa przed ekspozycją staging; brak ucinania danych |
| Abort przed/w trakcie; quota; brak odczytu | żadnego częściowego downloadu/sukcesu, źródła i poprzednia kopia bez zmian |
| Wszystkie wcześniejsze v5 (także bez szkiców), v1–v4 | czytane dotychczasowym readerem; poprawna informacja „szkice nieobjęte formatem” |
| Android PWA 390×844, restart offline, ubity renderer, limit old-space | poprawne recovery zgodne z granicą snapshotu; mierzyć RAM/RSS, nie tylko kompresję; odbiór na prawdziwym urządzeniu |
| UI/Drive/historia/plany/statystyki/szkice przed i po | pełne porównanie store/LS + brak sieciowego uploadu i zmian Matrix; bez Issue #61 |

## 8. Co faktycznie wykonano teraz

`tests/draft-backup-diagnosis.test.mjs`: 5 testów istniejącego modułu z odizolowaną atrapą IDB i localStorage w pamięci Node. Potwierdzają nowszy bufor/gałęzie tokenów, osobne ID kart, zachowanie niepełnych legacy/V2 value, readError i uszkodzony raw, spełnienie flush po błędzie zapisu oraz zależność widoku reload od kolejności. Capture zapisuje wyłącznie do atrap w RAM; nie dotyka prawdziwej IndexedDB/localStorage ani profilu przeglądarki.

Nie wykonano testu prawdziwego urządzenia, danych właściciela ani implementacji scenariuszy v6. Nie deklarujemy sprawdzonego roundtrip v6. Pełna regresja aplikacji nie jest potrzebna do oceny samego niezmienionego kodu produkcyjnego; nowe neutralne testy są uruchamiane osobno. Automatyczne CI PR może dodatkowo uruchomić standardowy zestaw — wynik w Checks, bez przypisywania niewykonanych testów do raportu.

**Decyzja potrzebna przed kolejnym etapem:** akceptacja osobnego v6, schematu evidence/blob, zaproponowanych budżetów i jawnie ograniczonej gwarancji observed-origin; następnie osobny projekt protokołu snapshotu wielu kart i izolowane próby. Brak zgody nie jest powodem zmiany obecnego v5. Ten PR zawiera wyłącznie raport i testy diagnostyczne.
