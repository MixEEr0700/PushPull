# Issue #54 — rozmiar kopii i archiwa ratunkowe

Stan analizy: 24.10.2026, `main` `2df50f6` po PR #53. **Raport i pomiary, bez zmiany kodu aplikacji, formatu kopii, migracji ani kasowania archiwów.** Profile wyłącznie syntetyczne, bez konta Google i danych właściciela. Issues #50/#51 poza zakresem.

Decyzja do zatwierdzenia: oddzielić bieżący dziennik od archiwów ratunkowych, zachować stare archiwa jako niezmienne bajty, a nowe preimage opisywać przez referencje. To wymaga nowego kontraktu kopii i semantyki preimage, więc **nie zostało zaimplementowane**. Pomiary kompresji nie są nowym eksporterem/importerem.

## 1. Co jest dziś przechowywane

| Warstwa / miejsce | Zawartość i znaczenie |
| --- | --- |
| `indexeddb.js`, tabele dziennika i `meta.state` | Bieżące plany/katalog, sesje, serie, wyniki, notatki i technika; checksum `data + catalog`, rewizja i kontrola transakcyjna. |
| `meta.training-model-v1` | Source-backed model v3: projekcja dziennika oraz `payload.legacySources[0].raw`, czyli pełny v2 z danymi, katalogiem **i archiwami**. Sesje/wyniki/snapshoty mają też reprezentację modelową. To nie są dodatkowe treningi. |
| IndexedDB `backups` | Rekordy `id`, `kind`, `createdAt`, `raw`, możliwe rozszerzenia i `sourceId`. `raw` to tekst lub `null`, nie zawsze poprawna kopia treningowa. |
| Lokalne archiwa | `migration-original:*` (`migration`), klucze localStorage `*_backup_*` (`legacy-backup`), `model-migration:*` (`before-model-migration`), `idb:*` / `recovery-records:*` (`before-import`), `legacy-conflict:*`. Każdy ma inny cel odzyskiwania. |
| `pushpull-idb-recovery` | Surowy stan niezweryfikowanej/uszkodzonej bazy, potencjalnie rekordy, model i wcześniejsze archiwa. Nie wolno odrzucić go tylko dlatego, że nie jest poprawnym v1/v2/v3. |
| Szkice / ustawienia Drive | Oddzielne rekordy `meta` oraz lokalne bufory szkiców; nie należą do kopii treningowej v3. Muszą pozostać lokalnie podczas restore. |
| Drive | Osobny ręcznie tworzony plik: v3 jako **tekst** w polu `backup`, ponownie escapowany. SHA-256 całego body; upload → GET → walidacja. Starsze pliki pozostają. |

Ścieżka: `exportModelBackup` → `snapshot(true)` → `createLegacyModel(JSON.stringify(source))` → `exportBackup` → `makeNode` → multipart POST → `readNode`. Eksport sam nie dopisuje archiwum. Na dysku ten sam materiał istnieje również w `backups` i w źródle modelu; niniejszy etap nie zmienia tego mechanizmu.

Odczyt i przywrócenie: v1 dostarcza dziennik, katalog powstaje przez istniejący adapter; v2 dostarcza dziennik/katalog/archiwa; v3 przechodzi pełną walidację i kontrolę zgodności odtworzonego source-backed modelu (`parseModelBackup`). Inne przyszłe v3 nie są automatycznie spłaszczane. Import scala **archiwa**, ale zastępuje bieżący dziennik; nie scala historii treningowej.

## 2. Mechanizm wzrostu

W `save()` każde przywrócenie (także `backupBefore`) tworzy `before-import.raw = JSON.stringify(expectedModel.document)`. Ten model zawiera wcześniejsze archiwa. Importowane archiwa zostają dodane do istniejących; ten sam ID i identyczny rekord są już deduplikowane, a kolizja ID z różną treścią dostaje nowe ID i `sourceId`. Następny `modelSource.archives` obejmuje wszystkie zachowane rekordy, łącznie z nowym preimage. Przy kolejnym restore cały poprzedni model trafia do następnego preimage.

Zatem archiwów na najwyższym poziomie przybywa liniowo, ale ich tekst ma wielokrotnie zagnieżdżone kopie wcześniejszych archiwów. Każda warstwa kodowania podwaja wcześniejsze backslashe i dodaje escapowanie cudzysłowów. Jest to **wielokrotny, obserwowany wykładniczy rozrost**, nawet bez jednego nowego wyniku. Nie jest to duplikowanie rekordów sesji ani efekt samej zmiany V2→V3.

To nie dowodzi przyczyny pięciominutowego oczekiwania na fizycznym Androidzie po PR #53. Nie mamy pomiarów jego bazy, procesu i żądań. Koszty eksportu, walidacji, hashowania, multipart oraz pobrania są odrębnymi etapami; poprawka #53 usunęła tylko nadmiarowe końcowe porównanie.

## 3. Pomiary syntetyczne

Jednostki w tabelach: bajty, sekundy; MB oznacza 1 000 000 B. Środowisko: Chromium 154.0.8037.57 / Linux x86_64, Playwright 1.62.0, Python 3.12.14, Node 24.19.0. Skrypt używa rzeczywistego IndexedDB, eksportera i importera projektu, a nie symulacji ich algorytmów. Gzip: Python/stdlib, poziom domyślny 9, `mtime=0`; czas zależy od urządzenia. Nie jest to pomiar kompresji na Androidzie.

Wszystkie bajty po gzip/gunzip identyczne; każda operacja restore zachowała pełne `data`, lokalny sentinel szkicu i wszystkie wcześniejsze rekordy archiwów (łącznie z raw i metadanymi).

| Profil | Restore | Archiwa | v3 B | Opakowanie Drive B* | Gzip B | Eksport ms | Następny restore ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| minimal | 0 | 1 | 52 426 | 68 006 | 3 498 | 23 | 74 |
| minimal | 1 | 2 | 138 322 | 211 846 | 7 107 | 53 | 107 |
| minimal | 2 | 3 | 483 946 | 847 190 | 17 219 | 65 | 244 |
| minimal | 3 | 4 | 2 044 354 | 3 856 198 | 47 503 | 222 | 852 |
| minimal | 4 | 5 | 9 510 970 | 18 565 814 | 140 481 | 919 | 4268 |
| minimal | 5 | 6 | 46 173 202 | 91 443 046 | 419 345 | 5276 | — |
| v2 | 0 | 2 | 378 081 | 459 545 | 23 763 | 169 | 288 |
| v2 | 1 | 3 | 922 745 | 1 308 661 | 50 015 | 171 | 483 |
| v2 | 2 | 4 | 2 925 429 | 4 833 605 | 114 459 | 327 | 1342 |
| v2 | 3 | 5 | 11 497 577 | 21 017 053 | 297 395 | 1081 | 4280 |
| v2 | 4 | 6 | 51 475 773 | 99 051 749 | 844 868 | 5480 | — |

*Rozmiar opakowania oszacowany przez dokładne zewnętrzne kodowanie tego tekstu z polami istniejącego protokołu; obejmuje stałe ID/hash/czas o tej samej długości, bez nagłówków multipart. Nie jest to upload na prawdziwe Google. Rozmiary rzeczywistego POST podaje osobno próba limitu V8.

Profil minimalny to fabryczny szkielet bez treningów, po przygotowaniu modelu i pierwszym commicie. Profil V2 to jawna aktywacja fabrycznej wersji w nowym profilu testowym. Inny ownerId i czas powodują drobne różnice względem #52. Ani jedna sesja nie przybywa między restore. W minimalnym `data` pozostaje 5 359 B, w V2 105 488 B.

Kontrprzykład około 10 miesięcy: co 2,5 dnia, 60 sesji V2, następnie jawna syntetyczna aktywacja TEST V3 i 60 sesji V3. Daty 01.01–25.10.2026; wyniki wyłącznie syntetyczne, bez interpretowania ciężarów właściciela. Użyto istniejących `startSession`, `newPerformance`, `recordEntry`, `advance`, `stagePlan` i `stageActivation`. Występują back-off, dropset, strony i człony grup. Nie wykonano restore; punkty 60/120 zapisano przez istniejący commit.

| Sesje | Wyniki | Snapshoty | Aktywacje | Archiwa | Data B | v3 B | Gzip B | Eksport ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0 | 1 | 2 | 105488 | 378081 | 23764 | 141 |
| 60 | 525 | 60 | 1 | 2 | 6873339 | 21208561 | 1322257 | 28492 |
| 120 | 705 | 120 | 2 | 2 | 7742528 | 24276861 | 1426681 | 34821 |

Archiwa pozostają na poziomie 2 / 53 890 B raw. Zwiększa się rzeczywista historia i jej projekcje/snapshoty, a nie rekurencja preimage. Mniejszy przyrost po przejściu na TEST V3 wynika z mniejszych syntetycznych jednostek; nie jest to uniwersalny model tempa wzrostu. Już 60 sesji kosztowało ok. 28,5 s eksportu na tym CPU — sam rozdział archiwów nie rozwiąże każdego kosztu bieżącej historii.

Gzip pełnego V2 po 4 restore: 1 416 ms kompresji / 101 ms dekompresji w Python; minimalny po 5 restore: 984 / 105 ms. To pomiary desktopowej biblioteki, nie obietnica czasu w Chrome/Android. W checkpointach eksportu minimalnego po 5 restore sterta miała 748 MB; V2 po 4 restore 592 MB. Najwyższy zanotowany RSS własnych rendererów V2: ok. 1,46 GB, bez ustalenia rzeczywistego maksimum.

Próba opaque (1 restore): 7→8 archiwów, 139 369→486 904 B v3. Zachowano `raw:null`, uszkodzone `{broken`, nieznany JSON version 99 z whitespace/Unicode, tekst niebędący JSON, samotny surogat U+D800 oraz `sourceId` i dodatkowe pola. Gzip odtworzył wszystkie bajty. Nie znaczy to, że te opaque treści są poprawnymi planami/kopiami do aktywacji.

Wartości sterty to checkpoint `performance.memory.usedJSHeapSize` po eksporcie; RSS to suma własnych rendererów po operacji, obejmuje współdzielone strony i GC. **Nie są ciągłym pomiarem szczytu ani limitem pamięci Androida.** Pomiary dużych scenariuszy wykonywano kolejno. Przesłanie artefaktu do lokalnego HTTP jest dodatkowym kosztem narzędzia, poza zmierzonym czasem eksportu; surowe pliki nie są przesyłane przez DevTools.

### Deduplikacja i kompresja — co faktycznie udowodniono

W syntetycznych ciągach przywróceń wszystkie bezpośrednie `raw` były różne: suma rozmiarów unikalnych `raw` równała się sumie wszystkich `raw`. Sama deduplikacja SHA-256 nie usuwa osadzonych w nich potomków. Skrypt inwentaryzuje rozpoznane v2/v3 wewnątrz, ale nie traktuje sum unikalnych blobów jako rozmiaru kompletnego, spłaszczonego backupu — rodzice nadal zawierają dzieci; brakuje także manifestów i metadanych.

Dla każdego wygenerowanego pliku wykonano gzip → gunzip i porównanie **wszystkich oryginalnych bajtów**, nie tylko liczby treningów. Zachowano także checksumy istniejącego v3. Udowodniono bezstratność tego eksperymentu kompresji, **nie całej przyszłej migracji archiwów**. Dotyczy to konkretnych próbek; nie wdrożono obsługi `.gz` w aplikacji.

## 4. Porównanie rozwiązań

| Rozwiązanie | Kompatybilność i korzyść | Pamięć / wydajność | Ryzyko i ocena |
| --- | --- | --- | --- |
| Deduplikacja dokładnych `raw` po SHA-256 + porównanie bajtów, bez zmiany preimage | Obecne v3 pozostaje czytelne, ale sam eksport z `raw` w rodzicach nadal puchnie. ID/metadata zdarzeń muszą być zachowane nawet przy wspólnym blobie. | Niewielki zysk w zmierzonych próbkach: wszystkie bezpośrednie raw były unikalne. Hashe też kosztują czas. | Niewystarczające samodzielnie; nie mylić identycznych danych treningowych z identycznymi archiwami. |
| Oddzielenie bieżącego źródła i manifestów archiwów; nowe preimage referencyjne | Stare v1/v2/v3 nadal odczytywane. Nowy kontrakt konieczny dla nowego zapisu; stare aplikacje go nie odczytają. | Usuwa rekurencję dla przyszłych operacji, pozwala nie rozwijać starych raw przy zapisie wyniku/eksportowaniu dziennika. | **Rekomendowane**, po akceptacji. Nie zmieniać oryginalnych starych raw. Przeniesienie samych archiwów poza JSON bez przenośnego manifestu byłoby utratą kopii na drugim telefonie. |
| Pełne spłaszczenie wnętrza starych raw przez parse/re-serialize | Nawet pozornie równe obiekty mogą różnić się spacjami, escape, rozszerzeniami i checksum. Uszkodzone/raw przyszłego formatu nie poddają się tej interpretacji. | Może zmniejszyć zagnieżdżenie, ale wymaga kosztownego, głębokiego parsowania. | **Nie rekomendujemy przepisywania historycznych raw**. Bez osobnego dowodu odwracalności ich dokładnych bajtów nie jest to bezstratna migracja. |
| Gzip/strumieniowy kontener dla pełnego starego v3 | Oryginalny v3 po rozpakowaniu identyczny. Potrzebny nowy kontener/decoder i ograniczenie rozmiaru po rozpakowaniu. | Duży zysk plik/sieć; obecny importer nadal rozwija całość. Gzip→base64 w JSON ma dodatkowe ~33% i kolejne ciągi. Sam streaming transportu nie usuwa pełnego `JSON.parse`, projekcji i canonical/hash. | Uzupełnienie rekomendacji, nie samodzielne rozwiązanie RAM. Nie ogłaszać obsługi CompressionStream/ZIP/streaming zanim zostaną wdrożone i przetestowane offline/Android. |

## 5. Konkretna rekomendacja do decyzji właściciela

Proponowany kontrakt następnego etapu (nazwa robocza **v4**, bez implementacji):

1. Jeden przenośny plik zawiera bieżący dziennik/katalog/model z niezmienionymi ID i snapshotami oraz manifest wszystkich zdarzeń archiwum. Ten sam kompletny plik służy JSON/Drive; brak archiwów tylko na telefonie źródłowym. Manifest jawnie wymienia format, wersję, rozmiary, checksumy i wymagane bloby. Dopuszczalny kontener binarny/gzip wymaga osobnej decyzji o nazwie/rozszerzeniu pliku zamiast udawania starego JSON.
2. Każde stare `raw` zachować **dokładnie jako ciąg jednostek kodowych JavaScript**, także null/niepoprawne JSON/nieznany format. Konkretny proponowany zapis bloba: UTF-8 z `JSON.stringify(raw)` z jawnym encoding `json-string-utf8`; dekoder odtwarza dokładnie ten sam string. Nie stosować bezpośrednio `TextEncoder(raw)`: samotny surogat U+D800 zmienia się wtedy w U+FFFD. Dla zwykłego poprawnego Unicode zachowujemy także oryginalne bajty tekstu UTF-8; dla samotnych surogatów obowiązuje tożsamość jednostek kodowych, nie fikcyjny poprawny UTF-8. Bloby mogą być kompresowane i współdzielone tylko przy identyczności bajtów; oddzielny wpis manifestu zachowuje wszystkie ID, kind, createdAt, sourceId, nieznane pola, kolejność i relacje. Null nie jest pustym tekstem. Niczego nie kasować z istniejącego store w pierwszej fazie.
3. Nowe preimage wskazuje niezmienną migawkę bieżącej bazy **bez osadzania raw wcześniejszych archiwów** oraz pełny manifest/referencje osiągalnych archiwów. Gdy te same treści występują ponownie, dane współdzielone, zdarzenia nadal oddzielne. To zmiana semantyki `before-import`, wymagająca zatwierdzenia. Czytnik ratunkowy musi umieć odtworzyć ten preimage jako całość; samo wycięcie `archives` jest zabronione.
4. Stare zagnieżdżone raw pozostają nieprzepisane w kompresowanych blobach. Nie próbować ich automatycznie rozpoznawać/migrować rekurencyjnie. Przy normalnej pracy weryfikować manifest/bloby strumieniowo, nie rozwijać ich jako wielkich stringów. Dekomprimować pojedyncze stare archiwum dopiero przy świadomym odzyskiwaniu; bardzo duży historyczny preimage nadal może wymagać komputera. Ta strategia zatrzymuje przyszły rozrost i kompresuje stare bajty, nie obiecuje taniego otwarcia dowolnego starego archiwum.
5. Zachować czytniki v1/v2/source-backed v3 oraz stare pliki Drive. Nowy eksport oznaczony nową wersją; brak cichej zmiany checksum v3. Nie dokładać referencji do `raw` v3: obecny walidator wymaga samodzielnego źródła i nie rozumie referencji. Starsza aplikacja ma odrzucać nową kopię czytelnie, nigdy otwierać pustej bazy.
6. Przed jakimkolwiek zapisem nowego kontraktu: pełny inventory i byte-exact roundtrip fixture każdego osiągalnego rodzaju archiwum, w tym recovery/unknown, rozszerzenia, kolizje ID, Unicode, whitespace, null, uszkodzone treści. Dowód równości live data/katalog/model/relacji oraz oryginalnych raw (w tym jednostek kodowych) i ich metadanych, kompletności referencji i checksum. Testy uszkodzenia/nieobsługiwanej wersji, bomb dekompresji, limitów rozmiaru, anulowania, quota, dwóch kart, przerwania i wznowienia. Atomowy commit w istniejącym IndexedDB po zweryfikowanym stagingu; dotychczasowy store/oryginały zostają. Kopia przed restore i szkice nadal chronione.

Samo opakowanie eksportu nie wystarczy do ograniczenia RAM aplikacji. Dzisiejszy `load()` pobiera `backups.getAll()`, a `modelState.document` nadal zawiera tekst źródła z archiwami. Po zatwierdzeniu rozwiązania potrzebne będą leniwy odczyt raw archiwów (metadane/referencje do zwykłej pracy), wersjonowany adapter modelu i właściwe checksumy nowego kontraktu. Nie wolno zmienić starego source-backed v3 pod tym samym numerem ani pozostawić w nim wszystkich raw i obiecywać mniejszego RAM tylko dzięki gzip transportu. Wpływ tych przyszłych zmian na otwieranie/zapis/odzyskiwanie bazy wymaga oddzielnych testów przed migracją.

Nie znamy jeszcze minimalnego bezpiecznego progu RAM na Androidzie, kosztu kompresji w przeglądarce ani wystarczającego miejsca na równoległe stare i nowe archiwa. **Nie ma podstaw do wdrożenia migracji teraz.** Do akceptacji: powyższy rozdział danych, referencyjne nowe preimage, jawny nowy kontrakt/kontener i zachowanie starych oryginałów. Dopiero potem niewielka implementacja i odbiór na dwóch profilach oraz fizycznym Androidzie.

## 6. Powtarzanie i wyniki weryfikacji

`tests/backup_size_probe.py` jest opcjonalnym narzędziem diagnostycznym korzystającym z obecnych Playwright i modułów. Nie jest uruchamiane przez unittest, nie ma nowego frameworka/zależności/CI. Wymaga **nowego, nieistniejącego** katalogu wyjściowego; nie przyjmuje profilu/kopii użytkownika. Eksporty w tym katalogu są wyłącznie syntetyczne; nie dodajemy ich do repozytorium.

```sh
python3 tests/backup_size_probe.py --scenario minimal --restores 5 --output /tmp/issue54-minimal-new
python3 tests/backup_size_probe.py --scenario v2 --restores 4 --output /tmp/issue54-v2-new
python3 tests/backup_size_probe.py --scenario history --output /tmp/issue54-history-new
python3 tests/backup_size_probe.py --scenario opaque --restores 1 --output /tmp/issue54-opaque-new
python3 tests/drive_backup_probe.py --restore-cycles 4 --heap-mib 768
```

- Node: **120/120 PASS**. Zawiera czytniki i checksum v1/v2/v3, odrzucanie nieobsługiwanych/uszkodzonych dokumentów oraz zachowanie rozszerzeń i struktur wyników.
- Chromium, istniejące przypadki: **8/8 PASS**: 5 przypadków `IndexedDBMigration` (abort + retry, quota, zamknięcie procesu w transakcji, pełne wersje/notatki/serie/metadata, błędny katalog/archiwa) oraz 3 `ManualDriveFlow` (dwa profile z przywróceniem V2 + TEST, szkice/preimage/restart offline; nowsza rewizja innej karty; błąd readback po commicie bez komunikatu sukcesu). Początkowy selektor trzech testów miał błędną nazwę klasy, poprawiono go i wykonano rzeczywiste testy; nie był to błąd aplikacji.
- Nowe próby diagnostyczne: minimalny 0–5 restore, V2 0–4 restore, 120 sesji/705 wyników V2→V3 bez restore oraz opaque 0–1 restore — wszystkie zakończone. Razem 16 wyeksportowanych plików; gzip/gunzip byte-exact dla każdego, a przy restore pełne `data`, sentinel szkicu i stare archiwa pozostają identyczne. Sentinel sprawdza storage, nie ergonomię edytora; prawdziwe szkice sprawdzają istniejące testy Drive.
- Istniejący `drive_backup_probe.py`: V2 po 4 restore, `--max-old-space-size=768`: **verified**, 51 483 641 B v3, 99 067 117 B rzeczywistego POST, 33,939 s upload+readback; restart `localUnchanged:true`. To limit **starej generacji V8**, nie całej sterty/renderer RAM. Odczyt sterty przy readback ok. 890 MB, zanotowany RSS ok. 1,84 GB. Nie wyznacza to bezpiecznej konfiguracji telefonu.
- Oddzielny eksperyment Node, `--max-old-space-size=64`: strumieniowy gzip/gunzip pliku V2 51 475 773 B bez JSON.parse, z porównaniem każdego rozpakowanego bajtu ze źródłem: **PASS**. Gzip 839 401 B, 1 530 ms kompresji / 149 ms dekompresji+porównania, maksymalny RSS 47 685 632 B. Inna implementacja zlib niż Python może tworzyć inne, nadal bezstratne bajty gzip. To dowód możliwości przesyłania/kompresji ograniczonymi buforami, **nie test dzisiejszego importera, checksum modelu ani PWA przy 64 MiB**.
- `py_compile`, `git diff --check`, istniejący `build_release.py --check`: PASS. Nie regenerowano SW, bo nie zmieniono żadnego zasobu runtime.
- Pełny lokalny Chromium nie był powtarzany dla dokumentacji; uruchomiono celowane przypadki i osobne duże próby. Wyniki automatycznej pełnej regresji GitHub Actions na gałęzi są podane w PR.

Artyfakty pomiarów zawierają tylko dane syntetyczne. Kod `analyze` jest inwentaryzatorem rozpoznanych v2/v3, nie kompletnym czytnikiem recovery/przyszłych archiwów. Suma `uniqueNestedRawBytes` jest wyłącznie estymatą: dla samotnych surogatów Python używa `surrogatepass`, co nie jest proponowanym kodowaniem nowego backupu. Gzip pełnego eksportu porównuje prawdziwe bajty JSON, gdzie surogat jest poprawnie escapowany.

Dla powtórzenia eksperymentu streaming (po wygenerowaniu V2/04.json):

```sh
node --max-old-space-size=64 --input-type=module - <<'JS'
import {createReadStream,createWriteStream} from 'node:fs';
import {open} from 'node:fs/promises';
import {createGzip,createGunzip} from 'node:zlib';
import {pipeline} from 'node:stream/promises';
const input='/tmp/issue54-v2-new/04.json',out='/tmp/issue54-stream-new.gz';
await pipeline(createReadStream(input),createGzip({level:9}),createWriteStream(out,{flags:'wx'}));
const f=await open(input,'r');let bytes=0;
try {
 for await(const chunk of createReadStream(out).pipe(createGunzip())) {
  const expected=Buffer.alloc(chunk.length);let offset=0;
  while(offset<chunk.length){const r=await f.read(expected,offset,chunk.length-offset,null);if(!r.bytesRead)throw Error('EOF');offset+=r.bytesRead;}
  if(!chunk.equals(expected))throw Error('Different bytes');bytes+=chunk.length;
 }
 if((await f.read(Buffer.alloc(1),0,1,null)).bytesRead)throw Error('Truncated output');
 console.log({bytes,byteExact:true,maxRssBytes:process.resourceUsage().maxRSS*1024});
} finally {await f.close();}
JS
```


Nie zmieniono aplikacji, schematu IndexedDB, formatu kopii, Matrix, planów, historii, wyników, snapshotów, mechanizmu offline, ręcznego Drive ani zabezpieczeń restore. Nie wykonano migracji danych użytkownika, usunięcia archiwów, wdrożenia, aktywacji rzeczywistego planu ani operacji na Google właściciela. Utrzymanie się oczekiwania na fizycznym telefonie po #53 pozostaje otwartą obserwacją #52, nie wynikiem tych testów.
