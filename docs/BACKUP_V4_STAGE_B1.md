# Backup v4 — etap B1, Issue #58

Baza: `main` `54fa9c0`, po PR #57. Gotowy jest **izolowany eksporter z pełną samoweryfikacją**, bez integracji z produkcyjnymi przyciskami, importem, IndexedDB i Drive. Format dekodera etapu A pozostaje niezmieniony. Jeden samodzielny plik JSON przenosi gzip/base64 bloby, manifest i SHA-256; nie jest to nowy zewnętrzny format `.json.gz`.

## API i granica danych

```js
import {exportBackupV4} from './model/backup-v4-export.mjs';
const result = await exportBackupV4(completeV2Snapshot, {
  createdAt: '2026-10-24T12:00:00.000Z', // jawny czas utworzenia kopii
  metadata: {source: 'example'},
  signal: controller.signal,
  limits: {} // te same limity co dekoder; można tylko obniżyć
});
// result.text: kompletny, zweryfikowany tekst JEDNEGO pliku
// result.diagnostics: wyłącznie liczniki/rozmiary, bez treści i identyfikatorów
```

Wejścia:

- Pełny logiczny snapshot **v2**: `{format:'pushpull-backup',version:2,data,catalog,archives}` z zachowaniem nieznanych rozszerzeń. Ten wariant nie wymaga uprzedniego zbudowania olbrzymiego v3 z archiwami. Moduł nie pobiera snapshotu z bazy: caller musi przekazać spójny, kompletny stan. Wszystkie mutowalne data/catalog/metadata są odłączane przed pierwszym await; niezmienne raw strings zachowywane przez referencję, bez klonowania całego archiwum.
- Tekst istniejącej kopii v1/v2/source-backed v3/v4, sprawdzany dekoderem A. W v2/v3 archiwa są odłączane od źródła live, a wszystkie rekordy przenoszone do manifestu. Dla v3 zachowana jest tożsamość właściciela i dotychczasowy createdAt modelu; porównywana jest cała projekcja poza świadomie odłączonym `legacySources.raw` i jego zmienionym digestem. Bieżący tekst źródła może zostać ponownie zapisany jako JSON; **historyczne raw nie są przepisywane**. Nieznane pola źródła pozostają w live.
- Ponowny eksport v4 korzysta z jego istniejącego live i archiwów. Nie dodaje całego poprzedniego pliku jako preimage. Zachowuje metadata kontenera; próba zastąpienia ich inną wartością kończy się błędem. Zmiana zewnętrznego createdAt jest świadomym czasem nowej kopii, nie datą aktywacji planu.

V1 z nieznanym polem `archives` jest odrzucane jako niejednoznaczne zamiast zgadywania, czy jest ono danymi czy archiwum. V2 bez trainingJournal pozostaje live v2 — bez wymyślania właściciela i nowego modelu. Jeżeli istniejący model bridge ma metadane poza takim snapshotem v2, caller musi przekazać pełne v3 albo przyszły jawny adapter B2; moduł nie poznaje ukrytego modelState. Dla natywnego dziennika właściciel, plany i snapshoty są zachowane z trainingJournal, a pełna projekcja live v3 powstaje istniejącym `createLegacyModel`.

To granica danych kopii treningowej, nie zrzut wszystkich rekordów meta przeglądarki. Szkice, bufory formularzy, OAuth i ustawienia Drive pozostają lokalne zgodnie z dotychczasowym kontraktem. Eksporter nie czyta ani nie zmienia ich. Nie generuje nowych ID treningów, ćwiczeń, wyników czy archiwów. Zmieniają się wyłącznie techniczne ID nowych blobów wynikające z SHA-256 ich treści.

## Bezstratność i pamięć

1. Kontrola przenośności JSON zapobiega cichej utracie undefined, getterów, niestandardowych obiektów, cykli i nieprzenośnych liczb. Nie ma normalizacji notatek, techniki, kg, L/P, back-offów, segmentów lub relacji grup.
2. Live zachowuje całe data/catalog/model. Dla istniejącego v3 sprawdzana jest zgodność modelu przed i po odłączeniu archiwów; nowe live używa dotychczasowych checksum i walidacji v3. Produkcyjny eksporter/formater v3 nie jest zmieniony.
3. Każde raw jest kodowane jako kanoniczny `JSON.stringify(string)` UTF-8. Najpierw obliczany jest dokładny rozmiar bez tworzenia całego escapowanego tekstu. Następnie fragmenty po maks. 32768 jednostek kodowych trafiają przez `encodeInto` do jednego bufora o znanym rozmiarze. Granica fragmentu nie rozcina pary surogatów; samotne surogaty pozostają escape. SHA-256 korzysta z WebCrypto, bez nowej własnej implementacji kryptografii.
4. Gzip jest odczytywany strumieniem z kontrolą faktycznej wielkości. Wszystkie bloby są skompresowane. Dokładnie równe stringi współdzielą blob, ale **wpisy archiwów, ID, kolejność i wszystkie metadane pozostają oddzielne**. Null i pusty tekst to różne wartości. Nie parsujemy wnętrza historycznego raw: malformed JSON, future format i recovery pozostają materiałem ratunkowym.
5. Przed klonowaniem sprawdzany jest rozmiar live oraz metadanych archiwów/kontenera. Narastający dolny budżet pliku (metadata + base64) jest kontrolowany przed tworzeniem kolejnych tekstów base64. Przed końcową serializacją sprawdzany jest dokładny rozmiar całego kontenera. SHA manifestu pomija jedynie data blobów zgodnie z A; obie warstwy blobu mają własne SHA-256. Nie ma dwóch dodatkowych pełnych serializacji do porównania wyniku — używamy strukturalnego porównania obiektów i dokładnej równości stringów.
6. **Przed zwróceniem pliku zawsze wykonywany jest `decodeBackup` z tymi samymi limitami**, a następnie porównanie całego live document, data/catalog źródła, wszystkich archiwów/raw/metadata/kolejności i metadata kontenera. Przekroczenie limitów, błąd kompresji, checksum lub cancel nie zwraca częściowego pliku ani sukcesu.

Domyślne limity A nadal obowiązują: plik 32 MiB, zapisany blob 16 MiB, rozwinięty blob 64 MiB, suma rozwiniętych blobów 128 MiB oraz ograniczenia kolekcji/JSON. Tekst starej kopii >32 MiB jest odrzucany przez reader A; wejście pełnego snapshotu v2 pozwala pominąć ten monolityczny etap, **nie omija jednak limitów wynikowego v4**. Nic nie jest ucinane lub kasowane, żeby zmieścić plik.

Eksporter nie ma dostępu do storage, sieci, download lub DOM. Błąd/abort zachowuje źródło i wcześniejszą kopię. Anulowanie jest sprawdzane pomiędzy etapami i chunkami; nie zatrzyma natychmiast synchronicznego walidatora/modelu lub wywołania SHA. Jest to atomowość wyniku w pamięci, nie nowa transakcja IndexedDB.

**Nie jest to gwarancja niskiego RAM całej aplikacji.** Pozostają snapshoty live, bufor pojedynczego tokena, kopie crypto/Blob, struktury walidatora v3 i samoweryfikacyjny staging. Po wcześniejszym wczytaniu zagnieżdżonego modelState stary storage nadal trzyma duże dane. Nie wdrożono lazy storage, kompresji archiwów w IndexedDB, streamingu parsera JSON ani nowej semantyki preimage. Nadal mogą istnieć prawidłowe źródła, których telefon nie pomieści lub które przekraczają limity — moduł nie usuwa ich, by ukryć problem.

## Diagnostyka bez treści użytkownika

`diagnostics` jest zamrożonym obiektem zawierającym **wyłącznie liczby**: formatVersion, fileBytes, liveCodeUnits, archiveRecords, nullArchives, archiveRawCodeUnits, largestArchiveCodeUnits, uniqueArchiveBlobs, deduplicatedArchiveRecords, archiveEncodedBytes, archiveStoredBytes, totalBlobs, totalDecodedBytes i totalStoredBytes.

Nie zawiera nazw, ID, kind, dat, raw, tokenów ani checksum. Moduł niczego nie loguje. Nie logować `result.text`: to pełna baza użytkownika. ArchiveRawCodeUnits oznacza logiczny rozmiar stringów wszystkich wpisów, a encoded/stored — sumę unikalnych blobów. Jeżeli live i archive wskazują ten sam blob, podzbiory mogą się pokrywać, więc nie należy ich sumować do rozmiaru pliku. Nie analizujemy rekurencyjnie treści starych raw w celu zgadywania ich znaczenia.

## Pomiary syntetyczne

Chromium 154 / Linux x86_64, Playwright 1.62.0, Node 24.19.0. Wyłącznie nowe profile testowe. To nie pomiary fizycznego Androida ani konta Google. Eksport obejmuje kompresję, SHA, pełny odczyt dekoderem i kontrolę równości.

| Stare przywrócenia V2 | Archiwa | v4 B | Raw archiwów, jednostki kodowe | Eksport + weryfikacja ms |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 2 | 35 043 | 53 247 | 179 |
| 1 | 3 | 70 576 | 365 608 | 177 |
| 2 | 4 | 151 262 | 1 218 782 | 202 |
| 3 | 5 | 360 313 | 4 066 938 | 368 |
| 4 | 6 | 933 973 | 15 471 838 | 1 244 |

Losowe ID i czasy preimage mogą nieznacznie zmienić rozmiary między profilami. Każdy punkt wykonał dwa eksporty tego samego snapshotu: pliki były identyczne, rewizja niezmieniona. Dodawane archiwa pochodzą **wyłącznie z istniejącego testowanego importu v3 między punktami**, nie z eksportera. Stary v3 w analogicznym profilu #54 miał po 4 restore ok. 51,5 MB / 99 MB opakowania Drive; tu nie mierzono ani nie zmieniano transportu Drive. Nowa kopia nie usuwa historycznego zagnieżdżenia wewnątrz raw. Restart wykonał dotychczasową weryfikację bazy/modelu i zachował liczniki.

Profil około 10 miesięcy V2→TEST V3: **120 sesji, 705 wyników, 120 snapshotów**, dwa archiwa. Eksport v4 **1 961 855 B**, live 17 621 171 jednostek kodowych; **27 336 ms** z samoweryfikacją. Drugi eksport identyczny; restart poprawny. To ta sama metoda generowania historii co #54; poprzedni v3 w takim profilu miał ok. 24,3 MB. Bieżące kosztowne projekcje/walidacje live nadal istnieją.

Kontrolowany przypadek offline z limitem starej generacji V8 **128 MiB**: raw 4 194 304 jednostki kodowe, v4 **19 691 B**, eksport i samoweryfikacja **322 ms**, checkpoint heap **33 751 838 B**, dokładny odczyt raw PASS. To silnie powtarzalne dane, a nie współczynnik kompresji realnej historii; V8 old-space nie jest limitem całego procesu Androida.

W dużych profilach bez limitu checkpoint heap po eksporcie wynosił ok. **0,58 GB** po 4 restore oraz **293 MB** dla 120 sesji. RSS własnych rendererów po drugim eksporcie ok. **1,18 / 1,42 GB**; obejmuje stary model/storage, input i zmienną pracę GC, nie jest izolowanym ani ciągłym szczytem eksportera. We wcześniejszym uruchomieniu checkpointy wyniosły nawet 1,18 GB heap / 1,81 GB RSS po 4 restore i 466 MB / 1,27 GB dla historii. Różnice między próbami zależą także od GC/losowych ID; nie dowodzą proporcji zysku eksportera. **Mały plik wynikowy nie dowodzi małego RAM.** Przed produkcyjną integracją większych baz potrzebne są dalsze decyzje i test urządzenia, nie deklaracja usunięcia awarii #52.

Pięciominutowego oczekiwania właściciela nie odtworzono na jego danych ani koncie. Pomiary pokazują możliwy koszt lokalnych preimage i oddzielny koszt bogatej historii, ale nie rozstrzygają przyczyny jego operacji Google. Transport, autoryzacja i #50/#51 są poza B1.

## Testy i uruchamianie

- Node: pełna równość historycznych i natywnych data/catalog, wszystkich planów/aktywnych sesji/snapshotów/instrukcji/notatek/techniki/serii/L/P/dropów/grup; v1/v2/v3/v4, rozszerzenia, zachowanie metadata i porządek archiwów, duplikaty treści, null, malformed/future/recovery, Unicode, samotne surogaty i para przecinająca granicę chunku. Modyfikacja wejścia podczas await nie zmienia snapshotu eksportu.
- Regresja alokacji: na `0563aea` nowy test wykazuje wykonanie base64 mimo niemożliwego budżetu pliku (FAIL: 1 zamiast 0). Po preflight: PASS, bez base64 i bez klonowania ponadlimitowych metadata/live. Repo nie było cofane; bazę testowano w izolowanym katalogu.
- Cancel/error/limity/nieprawidłowe źródło: brak częściowego wyniku, źródło i wcześniejszy plik bez zmian. Brak możliwości cichego podniesienia limitów. Test statystyk nie wymyśla nowych wyliczeń: pełna równość wszystkich źródłowych wyników i parametrów plus istniejąca regresja statystyk.
- Chromium: eksport i pełny roundtrip offline, trzy identyczne eksporty i rzeczywisty jeden download w harnessie, porównanie wszystkich rekordów bieżącej IndexedDB przed/po; awaria kompresji/abort/limity; sam eksport i samoweryfikacja w ograniczonym rendererze (nie tylko odczyt pliku przygotowanego poza limitem).
- Opcjonalny `tests/backup_v4_export_probe.py` używa istniejącego serwera, generatora historii i Playwright; nie jest nowym frameworkiem/CI. Zawsze tworzy własny tymczasowy profil, nie przyjmuje pliku/profilu użytkownika; wypisuje tylko metryki.

```sh
node --test tests/*.test.*
PYTHONPATH=tests python3 -m unittest -v test_backup_v4_export
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/backup_v4_export_probe.py --scenario restores --restores 4
python3 tests/backup_v4_export_probe.py --scenario history --sessions 120
python3 scripts/build_release.py --check
```

Końcowe liczniki pełnej regresji Node/Chromium i GitHub Actions są w PR.

## Niewdrożone

Bez B2: przycisków/download/importu/Drive w produkcji, zmiany precache/allowlisty i odświeżania SW, nowych uprawnień, automatycznej synchronizacji. Bez migracji IndexedDB, kasowania archiwów, nowych preimage, aktywowania planu lub zmian Matrix. Nie zmieniono istniejącego eksportu/importu v3, Google ani danych właściciela.
