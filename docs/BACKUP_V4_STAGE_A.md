# Backup v4 — etap A, Issue #56

Baza: `main` `4ce8a7f`, po analizie #54/PR #55. Wdrożono **izolowany odczyt i walidację do pamięci staging**, bez zapisu v4, podłączenia do przywracania, IndexedDB, Drive czy aktywacji planu. Nie jest to gotowy produkcyjny system kopii v4.

## Zaimplementowane

`model/backup-v4.mjs` eksportuje `decodeBackup(text, {limits, signal})` i zamrożone `V4_LIMITS`. Przyjmuje tekst jednego samodzielnego pliku JSON; nie pobiera niczego z sieci, nie czyta/zapisuje storage i nie wywołuje callbacków zapisu. Po pełnej weryfikacji zwraca jeden głęboko zamrożony wynik:

```js
const staging = await decodeBackup(text, {signal: controller.signal});
// staging.formatVersion, staging.live.{formatVersion,raw,document,data,catalog}
// staging.archives: wszystkie oryginalne rekordy archiwów z raw
// Tylko inspekcja. Brak API commit/restore i brak podłączenia do aplikacji.
```

Nie zwraca częściowo odczytanych danych w razie błędu/abort. „Atomowość staging” oznacza jedną kompletną wartość albo odrzucony Promise, **nie nową transakcję IndexedDB**. Anulowanie sprawdzane jest pomiędzy etapami i odczytami strumienia; nie może natychmiast przerwać synchronicznych istniejących walidatorów ani trwającego wywołania crypto. Nie zastępuje ochrony rewizji/przedprzywróceniowej kopii w przyszłym integratorze.

## Kontrakt jednego pliku JSON v4

Top-level ma dokładnie pola:

```text
format: "pushpull-backup"
version: 4
createdAt: pełny ISO UTC z milisekundami
metadata: obiekt zachowywany bez normalizacji
live: { formatVersion: 1|2|3, blobId: "sha256:<hex>" }
archives: [ { metadata: <cały rekord archiwum poza raw>, blobId: <id|null> } ]
blobs: [ { id, encoding, compression, storedBytes, decodedBytes,
           storedSha256, decodedSha256, data } ]
integrity: { algorithm: "SHA-256", digest: <hex> }
```

- `live` wskazuje dokładny tekst kopii bieżącej bazy **bez osadzonych archiwów**. W etapie A są to istniejące v1/v2 albo obsługiwane przez dziennik source-backed v3; dane i model walidują dotychczasowe czytniki. Dla v3 zachowana jest także kontrola zgodności pełnej projekcji z źródłem, aktywnym planem, snapshotami i relacjami. Nierozpoznane przyszłe/generic v3 są odrzucane, nigdy spłaszczane do części historii. To to samo ograniczenie co produkcyjny importer dziennika.
- W `archives` kolejność jest istotna. Zachowane są `id`, `kind`, `createdAt`, `sourceId` i wszystkie inne pola rekordu. Wymagane: niepuste unikalne ID, tekst kind i poprawna data createdAt. `raw` nie może wystąpić w metadata jako drugie, konkurencyjne źródło. `blobId:null` oznacza oryginalne `raw:null`, inne wskazania odtwarzają string. Null, pusty tekst i brak referencji nie są utożsamiane.
- Bloby mają `encoding:"json-string-utf8"`: zawartość po dekompresji to UTF-8 z **`JSON.stringify(oryginalnyString)`**, nie `TextEncoder(oryginalnyString)`. Dotyczy zarówno tekstu live, jak i raw archiwum. Po fatalnym dekodowaniu UTF-8 odczytujemy pojedynczy kanoniczny token JSON-string. Zachowuje to dokładne jednostki kodowe JS, w tym U+D800/U+DFFF, znaki NUL, whitespace, cudzysłowy, backslashe i Unicode. Dla poprawnego Unicode zachowany tekst ma też te same bajty UTF-8. Żadnych normalizacji Unicode ani parse/re-serialize wnętrza starego raw.
- `compression` to wyłącznie `gzip` lub `none`; `data` to kanoniczny base64 standardowy, z wymaganym paddingiem, bez whitespace. Brak ZIP, ścieżek plików, URL, zewnętrznych zasobów i rekurencyjnych odwołań blob→blob. Wszystkie wskazane bloby muszą istnieć w tym pliku, każdy blob musi być użyty. Brakujące, nadmiarowe lub powtórzone ID są błędem.
- `storedBytes` / `storedSha256` dotyczą bajtów po base64, przed dekompresją; `decodedBytes` / `decodedSha256` dotyczą bajtów tokena UTF-8 po dekompresji. `id` musi równać się `sha256:` + `decodedSha256`. Dwa wpisy archiwum mogą wskazywać ten sam blob, ale pozostają dwoma niezależnymi wpisami. Dekoder nie usuwa zdarzeń i nie zmienia ich ID.
- Checksum manifestu obejmuje kanoniczny JSON całego dokumentu **bez `data` w descriptorach blobów**, z `integrity:{algorithm:"SHA-256"}` (bez digest). Kanonizacja to istniejące `canonical` z `backup-json.mjs`. Chroni to metadane, kolejność archiwów i blobów, wszystkie bindingi, wersje, rozmiary i obie checksumy. Bajty data mają własną kontrolę SHA-256. Nie jest to podpis tożsamości/autentyczności; osoba mogąca przepisać cały plik może też policzyć nowe checksumy.
- Nieznane pola strukturalne/algorytmy są odrzucane. Rozszerzenia można zachować w metadata i metadanych archiwum. Klucze typu `__proto__` w tych danych pozostają danymi, bez scalania ich z obiektami globalnymi/prototypami.

Czytnik nie wymyśla brakujących planów, wyników, dat ani instrukcji. Nie wylicza nowych tonaży. Samodzielność oznacza, że odczyt nie potrzebuje poprzedniego telefonu/Drive: bieżąca baza i wszystkie wymagane stare raw są w tym jednym pliku. Nie oznacza jeszcze możliwości kliknięcia „Przywróć v4” w obecnej aplikacji.

## Starsze kopie i istniejąca PWA

`decodeBackup` przyjmuje też oryginalne v1/v2/source-backed v3; zachowuje dokładny tekst w `live.raw`, kompletne data/catalog/document i dotychczasowe archiwa. Odczyt ten jest niezależny od v4, bez przepisywania oryginałów. Dla v1 katalog pozostaje `null`: jego ewentualne utworzenie jest zadaniem obecnego adaptera, nie dekodera.

Produkcja nie importuje nowego modułu. Nie dodano go do listy zasobów statycznego wydania ani precache: jest to świadomie izolowany etap. Testy ładują go ze źródeł, następnie sprawdzają działanie bez sieci. Nie deklarujemy jeszcze dostępności dekodera w zainstalowanej PWA offline.

Jedyna zmiana istniejącego czytnika `legacy-backup.mjs`: jawny, czytelny błąd dla `pushpull-backup` z wersją nieobsługiwaną przez ten czytnik. Obecny plik v4 w UI zostaje **odrzucony**, nie zapisuje staging ani bazy i nie jest traktowany jako v3. Istniejący v3 nadal kierowany jest do właściwego czytnika modelu. `sw.js` odświeżony istniejącym generatorem dla zmiany komunikatu. Bez zmian UI/Matrix, Drive/OAuth, schematu IndexedDB i funkcji backup/restore.

## Limity i kontrola uszkodzeń

Domyślne twarde limity: plik 32 MiB, blob zapisany 16 MiB, pojedynczy blob po dekompresji 64 MiB, suma zadeklarowanych rozmiarów unikalnych blobów 128 MiB, 1024 bloby, 10000 wpisów archiwum, zagnieżdżenie JSON 64, 1000000 tokenów, liczba zapisana w maks. 128 znakach. Opcje `limits` mogą je tylko **obniżyć**, nigdy wyłączyć/podnieść. Przekroczenie odrzuca całą kopię, bez ucinania historii czy archiwów. Większa prawidłowa kopia wymaga przyszłej świadomej polityki obsługi, nie resetu danych.

Limity rozmiarów, referencji i manifestu są sprawdzane przed rozpakowywaniem. Base64 ma kontrolę długości, alfabetu/paddingu i bitów końcowych; oba rozmiary i SHA-256 są weryfikowane. Gzip jest czytany strumieniem, z kontrolą faktycznie rozwiniętych bajtów przed ich dołączeniem i anulowaniem po przekroczeniu deklaracji/limitu. Nie ufamy ISIZE gzip ani deklaracjom manifestu. Uszkodzony gzip/CRC, UTF-8, niekompletny JSON, duplicate keys, nieprzenośne liczby i niekanoniczny token są błędem. Kontrola głębokości/tokenów/numerów następuje przed istniejącymi rekurencyjnymi czytnikami, także dla źródła legacy wewnątrz v3. Raw archiwów pozostaje opaque, więc nawet uszkodzona treść jest zachowana jako materiał ratunkowy, bez wykonywania/parsowania jej wnętrza.

**To nie jest stały budżet RAM.** Reader materializuje tekst kontenera, pojedynczy zdekompresowany blob (bufory + wynik), stringi raw, wszystkie końcowe dane staging oraz struktury istniejącego walidatora live v3. Limity nie dowodzą, że każdy dopuszczalny plik zmieści się w słabym Androidzie. Nie zaimplementowano pełnego streaming JSON/parsera modelu, progresywnego staging na dysku ani leniwego IndexedDB. Istniejące walidatory mogą być kosztowne CPU; dekoder nie zapewnia natychmiastowego abort ich synchronicznej pracy. Stare zagnieżdżone raw nadal może być wielkie po rozpakowaniu, a odczyt jego treści do odzyskiwania jest osobnym zadaniem.

## Testy i pomiary

`tests/fixtures/backup-v4-fixture.mjs` jest deterministycznym **writerem wyłącznie testowym**, nie modułem eksportu aplikacji. Używa istniejących modeli, CompressionStream i fixture projektu; brak nowego frameworka/zależności. Deterministyczność jest sprawdzana w danym środowisku. Różne implementacje gzip mogą tworzyć inne poprawne compressed bytes — kontrakt wiąże odpowiednie checksumy, nie jedną wersję zlib.

- Node: kompletny syntetyczny dziennik (stare rekordy, 4 jednostki V2 + 2 TEST V3, 6 snapshotów, aktywny TEST V3 i rozpoczęta sesja), wszystkie serie/segmenty/L/P/back-offy/grupy, notatki trenera/użytkownika, technika, aktywacje, ID, pełne data i katalog porównane po roundtrip.
- Archiwa v1/v2/v3, trzy poziomy historycznych preimage, recovery, future/opaque, null/pusty tekst/whitespace/NUL/Unicode/samotne surogaty, dodatkowe metadane, klucze prototype, wspólny blob dla dwóch różnych ID. Wszystkie raw/code units i rekordy zachowane.
- Błędy: checksum manifestu i obu warstw blobu oddzielnie (z prawidłowo przeliczonym manifestem), gzip/CRC, odcięty plik, base64, nieprawdziwy rozmiar, brak/nadmiar blobu, kolizje ID, wersje/encoding, błędy liczb/depth/tokens, bomba dekompresji. Poprzedni staging i źródło bez zmian po porażce/abort.
- Chromium: roundtrip offline z pełnym porównaniem; błędy/abort bez zmian IndexedDB; czytelne odrzucenie przez istniejący UI; większy opaque blob w oddzielnym rendererze z `--max-old-space-size=128`. Brak fake IndexedDB i brak rzeczywistego Google.

W wykonanej próbie Chromium 154 / Linux x86_64 (Playwright 1.62.0): syntetyczny silnie powtarzalny raw miał **4 194 304 jednostki kodowe**; stary v3 **10 528 115 B**, testowy v4 **22 358 B**. Pod limitem starej generacji V8 128 MiB dekodowanie offline i pełna równość raw: PASS, ok. **199 ms**, checkpoint sterty **42 286 779 B**. Obie kopie mają te same data, katalog i model (porównanie pełnego digestu tych struktur); v4 zawiera źródło v3 bez archiwów plus zachowane osobno raw. Odczyt porównawczego starego v3: 606 ms; checkpoint CDP po budowie i odczycie starej kopii 188 361 092 B. Ten checkpoint obejmuje też obiekty generatora i nie jest izolowanym szczytem starego dekodera; nie należy liczyć z niego gwarantowanego współczynnika redukcji RAM. Budowa i odczyt referencyjnego v3 odbywają się poza ograniczonym rendererem; 1045 ms to łączny czas generatora i referencyjnego odczytu, nie benchmark przyszłego eksportera. Nie jest to pomiar szczytu RAM, fizycznego Androida ani reprezentatywny współczynnik kompresji rzeczywistych treningów. Wcześniejsze pomiary #54 pozostają punktem odniesienia dla rekurencyjnych archiwów i 10-miesięcznej historii.

Polecenia:

```sh
node --test tests/*.test.*
PYTHONPATH=tests python3 -m unittest -v test_backup_v4
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_release.py --check
```

Końcowe wyniki pełnej regresji i GitHub Actions są w PR. Nie testowano rzeczywistego konta Google ani fizycznego Androida, nie używano danych właściciela.

## Nadal projekt — następne etapy wymagają osobnej pracy

- Produkcyjny writer v4, pełne porównanie wyniku konwersji ze źródłem, obsługa większych kopii i prezentacja limitów.
- Podłączenie do UI/preview/restore/Drive, potwierdzenie zastąpienia, kopia przed restore, rewizje i transakcyjny commit, zabezpieczenie szkiców; dekoder tego nie realizuje i nie zastępuje istniejących zabezpieczeń.
- Nowa semantyka referencyjnych preimage i przegląd ich odzyskiwania; etap A współdzieli bloby raw, ale nie przepisuje ani nie interpretuje wewnętrznych preimage. Ewentualna zmiana tego kontraktu wymaga jawnego wersjonowania, nie cichego dopisania nieobsługiwanych referencji.
- Lazy storage / zabezpieczona migracja obecnych modelState i `backups.getAll()`, zachowanie oryginałów, wznowienie po awarii; odbiór PWA/offline na dwóch urządzeniach i realnym Androidzie.

Żaden z tych elementów nie jest oznaczony jako działający w produkcji w etapie A. Bez #50/#51, automatycznej synchronizacji, wdrożenia i zmian danych użytkownika.
