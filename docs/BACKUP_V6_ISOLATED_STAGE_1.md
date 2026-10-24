# Issue #68 — izolowany format v6, etap 1

Podstawa: zatwierdzony raport PR #69, commit `29834d9`, `docs/DRAFT_BACKUP_ISSUE_68_PROPOSAL.md`. Raport pozostaje w osobnym otwartym PR; ten etap startuje z main `15ec032` i nie scala ani nie modyfikuje PR #69. Kierunek v6 zatwierdzono w rozmowie. Kod produkcyjny, schemat v5, IndexedDB, Drive, Matrix i aplikacja nie są zmieniane.

## API i zakres

Nowy `model/backup-v6.mjs`:

```js
const result = await exportBackupV6({history, evidence, capture, createdAt}, {signal, limits});
const stage = await decodeBackup(result.text, {signal, limits});
```

`history` jest pełnym istniejącym dokumentem v5, nie snapshotem v2 i nie rekonstrukcją archiwów. Jest zachowywany bez zmian wartości i weryfikowany istniejącym dekoderem. Nie gwarantujemy zachowania whitespace oryginalnego tekstu kontenera v5: historia jest osadzonym obiektem JSON zgodnie z zatwierdzonym projektem; wszystkie raw/code units wewnątrz pozostają dokładne. Writer nie czyta storage, nie pobiera plików, nie wysyła danych i nie zbiera kart. Dostaje już odłączalne wejścia od wywołującego.

`decodeBackup` deleguje formaty v1–v5 do istniejącego czytnika, z jego dotychczasowymi ograniczeniami (w tym obsługiwane source-backed v3). Dla v6 zwraca zamrożony staging: historyDocument, history (wynik dekodera v5), draftEvidence, classification, capture, createdAt, formatVersion i draftCoverage. Brak API przywracania lub zapisu. Nie dodano modułu do UI/allowlisty/precache PWA — pozostaje izolowany.

## Kontrakt

Top-level dokładnie `{format,version:6,createdAt,history,capture,drafts,integrity}`, zgodny z raportem. Capture ma dokładnie version=1, bezpieczną nieujemną historyRevision, ISO UTC startedAt/completedAt, consistency='observed-stable' oraz scope='observed-origin'. Czytnik odrzuca fikcyjne complete-device. Te metadane są deklaracją wywołującego, nie dowodem pozyskania wszystkich kart. Nie ma pola complete ani gwarancji kompletnego przechwycenia.

Drafts to descriptor `pushpull-drafts` v1 z encoding=json-string-utf8, compression=gzip, oboma rozmiarami, oboma SHA-256 oraz kanonicznym base64 data. Po dekompresji: kanoniczny token JSON-string, którego string jest tekstem `pushpull-draft-evidence` v1 z obowiązkowym sources[]. Jawne sources:[] oznacza pusty zaobserwowany zbiór, nie pełny pusty stan urządzenia. Brak sekcji/listy albo nieznany typ źródła jest błędem struktury.

Obsługiwane źródła:

- idb-meta: storageKey prefiksu workout-draft: oraz value z pełnym rekordem;
- local-buffer: storageKey prefiksu pushpull_workout_draft_v1: i dokładny raw string (także uszkodzony JSON);
- editor-memory: record, binding, durableToken i parent, bez pobierania DOM.

Kopiuje się wszystkie wersje, metadane i kolejność źródeł, także duplikaty i konflikty. Odczyt LS nie normalizuje Unicode, whitespace, NUL ani samotnych surogatów. Wartości niedokończone pozostają stringami, nie są przeliczane na zatwierdzone wyniki. Operacje zapisu przyjmują przenośne JSON — cykle, Date/Blob, gettery/undefined nie są cicho zamieniane.

Klasyfikacja nie jest sterowaniem przywracaniem. `candidate` oznacza jedynie poprawność strukturalną rekordu i jego własnych powiązań, NIE zgodność z historią ani zgodę na resume. Sprawdza się key/id, token, sequence, datę, typ value, komplet context, zgodność session/exercise, binding pamięci i kształt parent. Semantyczne dopasowanie do sesji/modelu/baseline historii i protokół odzyskiwania pozostają kolejnym etapem. Uszkodzone źródło o poprawnym transporcie pozostaje w staging jako quarantine, nie jest usuwane. Różne poprawne rekordy jednego ID oznaczają conflict dla wszystkich tych źródeł, niezależnie od daty/sequence. Żaden zwycięzca nie jest wybierany. Wszystkie dowody są zachowane również w kwarantannie.

## Integralność i granice

Cały v6 ma SHA-256 kanonicznego dokumentu bez własnego digest, z kompletnym history, capture i drafts.data. History zachowuje własne SHA manifestów i blobów. Draft descriptor ma SHA bajtów zapisanych oraz rozwiniętych, sprawdzane niezależnie; gzip jest odczytywany strumieniem z kontrolą faktycznej liczby bajtów przed dołączeniem, a czytnik sprawdza również CRC, fatalny UTF-8, kanoniczny token/base64 oraz bounded JSON z wykrywaniem duplicate keys. SHA to integralność, nie podpis tożsamości ani szyfrowanie.

Limity z raportu zachowano: cały plik 32 MiB; draft stored/decoded po 4 MiB; pojedyncze źródło po zakodowaniu JSON <=1 MiB; <=1024 źródła i <=256 tożsamości (niepoprawne dowody bez ID także zużywają budżet). Parent ID także liczy się do budżetu tożsamości. Wspólny limit 128 MiB obejmuje live i rozwinięte tokeny logicznych fragmentów historii liczone z powtórzeniami oraz cały draft token. Jest sprawdzany przed dekompresją historii. Istniejący reader v5 dodatkowo weryfikuje swoje własne limity, referencje i sumy. Opcje mogą tylko obniżać limity, nie wyłączać/podnosić.

Writer liczy bajty JSON/tokena przed budowaniem pełnych escapowanych stringów i klonowaniem wejść. Mutowalne wejścia przechwytywane przed pierwszym await. Po kodowaniu zawsze odczytuje całość własnym dekoderem i porównuje historyDocument, capture i WSZYSTKIE evidence, zanim zwróci wynik. Błąd/abort nie zwraca częściowego staging ani kopii. Błędy czytnika nie ujawniają urywków wejścia lub ID.

## Wykonane nowe testy

11 testów Node:

- Pełne źródła IDB/LS/pamięci: konflikty, duplikaty, różne sequence i tokeny, parent/binding, dodatkowe metadata, nieukończone legacy/V2, whitespace/Unicode/NUL/samotny surogat; pełne porównanie bez zwycięzcy.
- Natywne plany V2/TEST V3, aktywna wersja, sesje/wyniki/snapshoty i raw archiwum 65 MiB plus null — historia i dowody identyczne po roundtrip.
- Delegacja v1/v2/v3/v4/v5 z kontrolą data.
- Brakujące/obce źródła, błędne rekordy (także null w wierszach legacy/V2), fałszywe complete-device, nieprzenośne dane; kwarantanna zamiast utraty.
- Usunięta sekcja, zmiana manifestu, ucięty JSON i gzip także po aktualizacji poprawnych checksum, zaniżony decodedBytes po przeliczeniu outer SHA, abort podczas zapisu i odczytu.
- Granice: 256 tożsamości PASS, 257 odmowa; 1024 duplikaty źródeł zachowane, 1025 odmowa. 6 opaque źródeł po 600 000 znaków mieści się w 4 MiB tokena, 7 przekracza budżet i jest odrzucane; raw 1 MiB + narzut przekracza limit pojedynczego źródła. Żadnego przycinania.
- Wspólny budżet history+drafts odrzucany, mimo że historia sama mieści się w limicie; kontrola zmiany wejść podczas await.

Chromium: nowy profil 390×844, po załadowaniu modułów offline, renderer old-space 128 MiB, syntetyczne opaque archiwum 4 MiB + ok. 500 k znaków uszkodzonego raw szkicu. Dokładne odtworzenie raw do kwarantanny, odmowa uciętej kopii, observed-origin. To test kodeka, nie produkcyjnego PWA/collectora ani odbioru fizycznego Androida.

Budżety są zasadnym bezpiecznym punktem startowym dla tych syntetycznych przypadków; nie dowodzą pojemności dla wszystkich rzeczywistych formularzy lub minimalnego RAM urządzenia. Duże baseline/metadata/konflikty zużywają ten sam budżet. Nie podniesiono limitów, aby ukryć odmowę. Nie mierzono ciągłego szczytowego RSS. Abort nie przerywa natychmiast synchronicznego skanera, JSON, structuredClone lub SHA. Pozostają struktury dekodera historii i pełny staging.

Pełna regresja Node i automatyczne CI: końcowe wyniki w PR. Brak ręcznej pełnej regresji Chromium aplikacji, której kodu/zasobów nie zmieniano; nowy test Chromium jest powyżej opisanym testem modułu. Nie deklarujemy pełnego przechwycenia szkiców z rzeczywistych wielu kart.

## Następny krok

Tylko do odczytu kolektor rzeczywistych dowodów oraz protokół snapshotu IDB/LS/pamięci i wielu kart, z jawną obsługą niedostępnych/niereagujących kart. Następnie izolowany podgląd/klasyfikacja zgodności szkiców z historią. Dopiero oddzielnie zatwierdzony projekt produkcyjnego restore z ochroną istniejących szkiców. Ten etap NIE zmienia IndexedDB, Drive, Matrix, historii, planów/wyników, starego v5 ani Issue #61.
