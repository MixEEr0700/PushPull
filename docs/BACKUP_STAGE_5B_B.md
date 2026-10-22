# Etap 5B — krok B: pełne kopie i odtwarzanie niezależnego modelu

Stan: 22.10.2026. Baza: scalony PR #6, `063c02b5272ebb4066d498f82faf34e7353b588c`. Implementacja w `model/backup.mjs`, `model/backup-json.mjs` i `model/legacy-backup.mjs`; wyłącznie natywne ES modules, JSON, structuredClone i Web Crypto SHA-256. Brak zależności, I/O, połączeń sieciowych, dostępu do DOM/IndexedDB/localStorage. W przeglądarce Web Crypto wymaga bezpiecznego kontekstu (HTTPS/localhost).

To działający mechanizm biblioteczny tworzenia, eksportu, podglądu i odtworzenia do **odrębnego stanu w pamięci**. Nie jest ładowany przez aplikację ani dołączany do paczki PWA. Istniejący eksport/import aplikacji nadal używa v1/v2; przywracania v3 w produkcyjnej aplikacji jeszcze nie ma. Nie wykonano migracji ani kroków C–H.

## Wersje i kompletność

Nowa kopia: `format: "pushpull-backup"`, **`version: 3`**. To osobna wersja od `schemaVersion:1` modelu i wersji 1 IndexedDB. Starszy kod odrzuca v3 przed zapisem (sprawdzone na rzeczywistych `PushPullStorage` i `PushPullDB.parseBackup`). Nie przemycamy rozszerzonego modelu pod wersją 1/2.

Wszystkie pola są wymagane, także puste tablice:

```js
{
  format: 'pushpull-backup', version: 3,
  createdAt: '2026-10-22T12:00:00.000Z', // jawnie podany czas utworzenia kopii
  metadata: {},                       // dowolne metadane JSON i pochodzenie
  payload: {
    model,                            // cały model kroku A albo null
    sessionSnapshots: [], resultReferences: [],
    sessionRecords: [], resultRecords: [], legacySources: []
  },
  integrity: {algorithm: 'SHA-256', counts: {/* liczby rekordów */}, digest: '…'}
}
```

`model` zachowuje wszystkie tablice z kroku A: exercises, variants, planVersions, positions, sets, drops, groups, coachInstructions, userNotes. Obejmuje konwencje obciążenia, strony, back-off, szablony segmentów, grupy/rundy, powiązania historyczne i nieokreślone parametry. Snapshoty zachowują własne modele historyczne; późniejsza zmiana bieżącego modelu nie jest podstawą do ich przepisania. Weryfikowany jest wspólny owner oraz relacje wewnątrz snapshotu, nie równość historycznych zaleceń z aktualnymi.

`model:null` służy pustemu stanowi lub opakowaniu źródeł legacy bez konwersji. Nie może towarzyszyć nowym sesjom, wynikom, snapshotom ani referencjom. `null` nigdy nie jest wynikiem awaryjnego parsowania.

`counts` zawiera liczbę rekordów każdej z dziewięciu tablic modelu oraz pięciu tablic payload. Walidacja sprawdza wymagane pola, struktury modelu, unikalność ID w kolekcjach, kompletne powiązania sesja ↔ snapshot, wynik ↔ referencja ↔ snapshot/pozycja/cel/grupa/runda/strona oraz referencje sesji w notatkach. Każdy snapshot musi mieć sesję; każdy wynik musi mieć sesję; referencja musi mieć wynik. Historyczny snapshot musi pozostać kompletny niezależnie od bieżącego modelu.

Hash obejmuje cały dokument, również rozszerzenia i metadane, z pominięciem tylko `integrity.digest`. Kanonizacja sortuje klucze obiektów, zachowuje kolejność tablic i wartości JSON. Porządek kluczy i formatowanie tekstu nowej kopii nie są semantyką danych. SHA-256 wykrywa zmianę zawartości; **nie jest podpisem, szyfrowaniem ani dowodem autentyczności**. Liczniki potwierdzają integralność dostarczonego dokumentu, nie dowodzą, że wywołujący przekazał wszystkie dane z zewnętrznego magazynu. Spójny, świadomie zmniejszony graf wymaga porównania z takim magazynem w przyszłym kroku C.

## Pełne rekordy wyników — jawna granica walidacji

Krok A nie ustalił numerycznego schematu nowego dziennika. Krok B nie wymyśla go ani nie redukuje danych do `{kg,reps}`:

| Rekord | Wymagane pola | Znaczenie |
| --- | --- | --- |
| SessionRecord | `id, snapshotId, payloadVersion, data` | `snapshotId` wskazuje snapshot tej samej sesji lub jest jawnie `null`. |
| ResultRecord | `id, sessionId, binding, payloadVersion, data` | `binding:'snapshot'` wymaga kompletnej referencji; `'uninterpreted'` jej zabrania. |
| LegacySource | `id, formatVersion, semantics, raw` | `formatVersion` 1/2; `semantics:'legacy-unknown'`; pełny oryginalny plik w `raw`. |

`payloadVersion` to jawnie podany dodatni integer albo `null` dla nieznanej wersji. Przyszła dodatnia wersja payload nie jest odrzucana jako nieznana wersja całego backupu. `data` jest wymagane i zachowane w całości jako wartość JSON (także null), bez wybierania znanych pól. Może zawierać segmenty, oddzielne strony, wykonane rundy i członków grup, metadane pochodzenia, technikę i nieznane rozszerzenia.

**Walidacja nie potwierdza sensu ani kompletnych relacji wewnątrz nieznanego `data`**: ID segmentów, liczby powtórzeń, jednostek, zgodności jego własnych pól z referencją czy obliczonego tonażu. Sprawdza jego przenośność JSON, zachowanie i sumę kontrolną oraz opisane wyżej relacje znanej obwiedni. Nowy schemat wyników będzie wymagał osobnego walidatora/etapu; samo zachowanie grup w `data` nie oznacza obsługi ich rejestracji przez UI.

Dodatkowe poprawne pola JSON w obwiedni i rekordach są zachowane. Obowiązuje dotychczasowy kontrakt kroku A dla jego modelu/snapshotów/referencji (w tym odrzucanie kluczy prototypu). W danych opaque i dodatkowych metadanych bezpiecznie zachowywane są również własne klucze `constructor`/`__proto__`, bez przypisywania ich do prototypów.

Zamiast cichej utraty odrzucane są: undefined, funkcje, Date, cykle, symbole, gettery, pola nieenumerowalne, dziurawe/dekorowane tablice, liczby niefinitywne i minus zero. Odczyt tekstu odrzuca zdublowane klucze (także po dekodowaniu escape) oraz literały liczb, które JS zaokrągliłby do innego dziesiętnego zapisu lub zera. Wysokoprecyzyjne wartości należy przechowywać jako tekst; nie są automatycznie konwertowane. Zwykłe liczby i ich równoważne zapisy wykładnicze przechodzą bez zmiany wartości. Odrzucony plik pozostaje nienaruszony.

## API i bezpieczne przerwanie

```js
import {
  createBackup, validateBackup, exportBackup, previewBackup, restoreBackup,
  readLegacyBackup
} from './model/backup.mjs';

const document = await createBackup(completePayload, {
  createdAt: explicitBackupTimestamp, metadata: explicitMetadata
});
const fileText = await exportBackup(document);
// fileText można zapisać jako plik poza przeglądarką; brak automatycznego uploadu.

const preview = await previewBackup(fileText); // wyłącznie odczyt i weryfikacja
// Przerwanie tutaj nie zmienia żadnego stanu.
const result = await restoreBackup(preview);
const separateModel = result.restored.payload.model;
```

`validateBackup(document)` zwraca zweryfikowaną, odłączoną, zamrożoną kopię v3. `exportBackup` ponownie waliduje dokument i zwraca pełny JSON. Argumenty są kopiowane przed oczekiwaniem na hash, aby zmiana wejścia w trakcie operacji nie zmieniła sprawdzanych danych. Błędy są wyjątkami/odrzuconymi Promise, nigdy pustą bazą lub pozornym sukcesem.

`previewBackup` przyjmuje tekst v1/v2/v3 i zwraca niezmienny podgląd z wersją, licznikami i opisem granicy walidacji. Prywatny WeakMap wiąże uchwyt z dokładnym plikiem; sklonowany lub podrobiony podgląd nie pozwala na restore. Podgląd po serializacji trzeba ponownie utworzyć z pliku.

`restoreBackup` ponownie weryfikuje plik i zwraca `{formatVersion, restored, raw, previousBackup}`. Dla v3 `restored` jest pełnym dokumentem, dla v1/v2 pełnym historycznym dokumentem. Wynik jest odłączony od źródła i głęboko zamrożony. Faktyczne odtworzenie jest utworzeniem nowego, zwalidowanego stanu w pamięci, bez mutowania modelu wywołującego. Zastąpienie zmiennej w izolowanym narzędziu pozostaje świadomą decyzją jego kodu.

Przy zastępowaniu istniejącego izolowanego stanu należy przekazać **jego pełną kopię jako dokładny tekst**:

```js
const result = await restoreBackup(preview, {
  currentBackup: previousFullBackupText, confirmReplacement: true
});
// result.previousBackup === previousFullBackupText
// Dopiero teraz narzędzie może przypisać result.restored do odrębnego stanu.
```

Bez potwierdzenia lub przy wadliwej poprzedniej kopii operacja kończy się błędem. Nie ma callbacków zapisu, transakcji, automatycznego scalania ani częściowych commitów. Biblioteka nie może wykryć stanu zewnętrznego, którego wywołujący nie przekazał, ani zagwarantować zapisania tekstu na dysku. Produkcyjna migracja/restore będzie musiała zapewnić trwałą kopię, porównanie z magazynem, obsługę braku miejsca, blokady kart i atomowy zapis w osobnym kroku C. Nie wykonano importu na rzeczywistej historii użytkownika.

## Odczyt historyczny v1/v2

`readLegacyBackup(raw)` obsługuje rzeczywisty dokument v1 (`exercises/sessions/entries/changes/nextType/activeId`) oraz pełną kopię v2 (`format/version/data/catalog/archives`). Sprawdza strukturę i podstawowe relacje, w tym katalog i jego bieżące parametry, wersje sesji oraz archiwa. Zwraca `{formatVersion, semantics:'legacy-unknown', raw, original, data, catalog}`. `original` zachowuje wszystkie pola; `raw` zachowuje dokładny tekst, whitespace i teksty archiwalnych kopii. Dla v1 `catalog:null`: nie dopisuje katalogu ani rzekomych snapshotów.

Nie rozdziela starych wspólnych notatek na autorów, nie nadaje nieznanych wersji planów, nie przelicza ciężarów/tonaży/stron i nie przypisuje dipów nowej maszynie. Zapisane surowe archiwa v2 mogą zawierać dawne uszkodzone JSON — walidowany jest rekord archiwum, nie „naprawiana” jego treść. Starsze źródła można opakować w `legacySources` v3 bez konwersji i bez zmiany oryginalnego pliku. Odtworzenie z v3 zachowuje ich exact `raw`; nie scala ich z bieżącym modelem.

Adapter odczytu dopuszcza dodatkowe pola JSON również w obwiedni i katalogu v2, zachowując je w całości. To świadoma zdolność archiwizacji rozszerzeń: dotychczasowy produkcyjny importer ma bardziej restrykcyjną allowlistę tych kontenerów i może tak rozszerzoną kopię odrzucić. Nie obiecujemy zgodności jej zapisu w starszym kodzie. Zwykła v2 w testach powstaje z katalogu rzeczywistego obecnego `parseBackup`, nie z wymyślonego odpowiednika.

## Bez zmian i następny etap

Nie zmieniono `app.js`, `storage.js`, `indexeddb.js`, HTML, CSS, planu, statystyk, ikon, manifestu, service workera ani build/CI. Nie zmieniono nawet kontraktów kroku A. Historia, ID, IndexedDB, klucze localStorage i tożsamość PWA pozostają bez zmian; repo pozostaje prywatne. Nowych modułów nie ma w aktualnym shellu offline, ponieważ nie są częścią aktywnej aplikacji.

B jest podstawą do osobno zleconego kroku C, nie jego początkiem. Nadal potrzebne są: trwały magazyn nowego modelu i migracja z porównaniem pełnej historii, docelowe walidatory wyników oraz późniejsza integracja UI/edytora. O1/O2/O3 z audytu pozostają otwarte; kopia nie potwierdza parametrów przyszłego V2. Wyniki: [raport testów B](STAGE_5B_B_TEST_REPORT.md).
