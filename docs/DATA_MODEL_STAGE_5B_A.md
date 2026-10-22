# Etap 5B / PR A — zaimplementowane kontrakty domenowe

Baza: main po PR #5, `012fe5a8d2da4107dea5a01f27c4faffec544430`. Właściciel osobno zlecił implementację **wyłącznie kroku A**. Ograniczenie D8 ze starszych dokumentów pozostaje historycznym opisem zakresu PR #5; kroki B–H nadal nie zostały rozpoczęte.

`model/training-model.mjs` jest niezależnym modułem ES bez zależności. Nie jest importowany przez aplikację, HTML ani worker, nie znajduje się w liście zasobów paczki PWA. Nie odczytuje magazynów, nie generuje ID/czasu, nie aktywuje planu, nie zmienia danych ani nie liczy tonażu. Używa zwykłych rekordów JSON i funkcji walidujących, bez frameworka/ORM.

## Kontrakty i zakres

Wszystkie encje mają dostarczone przez wywołującego `id` i `source={kind, reference, recordedAt}`. Źródło rozróżnia trener/właściciel/legacy/nieznane; `recordedAt:null` pozostaje brakiem wiedzy. Brakujące wymagane pole jest błędem — jawne `null` nie jest zamieniane w domyślną liczbę. Zakresy mają `min/max`, tempo cztery uporządkowane fazy, także z indywidualnym `null`.

| Kontrakt / funkcja | Zaimplementowane znaczenie |
| --- | --- |
| ExerciseIdentity | ID, nazwa, status confirmed/unresolved, legacyId. Gdy legacyId jest znane, musi pozostać równe ID; brak automatycznego nadania nowego ID staremu ćwiczeniu. |
| ExerciseVariant | Własne ID, exerciseId, etykieta, maszyna, chwyt, podparcie, wykonanie i lateralność. Null dla nieznanego modelu urządzenia. Wariant nie jest pozycją planu ani nowym wynikiem. |
| PlanVersion | ID planu/wersji, numer lub null, etykieta i dowolna niepusta lista jednostek z ID/nazwą/kolejnością. Bez ograniczenia do czterech PUSH/PULL, bez stanu aktywacji. |
| PlanPosition | Wersja/jednostka/kolejność, exerciseId i variantId, etykieta snapshotu, legacyPositionId i opcjonalna relacja replacesPositionId do pozycji poprzedniej wersji. Rozróżnienie unspecified/specified celów oraz pending/confirmed/legacy-unknown. |
| SetPrescription | Osobny cel każdej serii: zakres powtórzeń, RIR, tempo, strona, kolejność, rola i ewentualne powiązanie back-off z wcześniejszą główną serią tej samej pozycji. Brak wzoru kg/procentu redukcji. |
| DropPrescription | Powiązanie z serią macierzystą; segments=null oznacza zmienną nieokreśloną listę, a nie brak dropsetu. Dowolna niepusta lista uporządkowanych szablonów segmentów jest opcjonalna; każdy szablon ma własne cele. Nie narzuca stałej liczby segmentów/ciężarów. Rzeczywiste wykonane kg/reps segmentów będzie obsługiwał późniejszy etap wykonania/edytora. |
| GroupPrescription | Uporządkowana grupa odrębnych ćwiczeń w jednej jednostce/wersji, rodzaj paired/superset, liczba rund lub null oraz osobne przerwy wewnątrz/po rundzie. Bez timerów i bez powielania wyników. |
| Side / LoadConvention | LEFT/RIGHT/BILATERAL/EACH (EACH to cel per strona, nie jedna wykonana strona). Jawna jednostka i baza obciążenia, np. kg/per-implement; null/null dla nieznanej konwencji. Brak przeliczeń między stronami/sprzętem. |
| CoachInstruction | Wersjonowany tekst związany z planem/pozycją, jawne źródło i confirmed/unverified. Nieznana uwaga C2 nie może zostać potwierdzona jako autorstwa trenera bez odpowiedniego pochodzenia. |
| UserNote | Odrębny tekst/revision ze wskazaniem ćwiczenia i/lub sesji, origin user/legacy-shared/source-note. Tekst legacy pozostaje cały; żadnego zgadywania autorstwa ani dat. Powiązanie sessionId odwołuje się do przyszłego repozytorium sesji, którego ten moduł nie implementuje. |
| SessionSnapshot | ID snapshotu/sesji, wersja, jednostka, jawny czas rozpoczęcia i samowystarczalna kopia kontraktów danej wersji wraz z potrzebnymi przodkami zastępowanych pozycji. Bez userNotes; instrukcje są oddzielne. |
| ResultReference | Powiązanie resultId z właścicielem, snapshotem, sesją, wersją, pozycją, ćwiczeniem/wariantem, opcjonalną serią, stroną i grupą/rundą. Odrzuca inne exerciseId/variantId/wersję/jednostkę/właściciela. Nie jest konwerterem istniejących wpisów ani nowym formatem backupu. |

`validateModel` weryfikuje również odwołania, zgodność wariantu z ćwiczeniem, jednostki/kolejność/unikalność, cykle zastępowania, back-off i grupy. `createModel` tworzy głęboko odłączoną, zamrożoną kopię poprawnego grafu. Sam `validateModel` niczego nie zmienia i zwraca wejście.

`captureSessionSnapshot` i `createResultReference` to czyste konstruktory; nie uruchamiają treningu ani zapisu. Snapshot zachowuje dane mimo późniejszych zmian wejściowego planu/instrukcji. Zwrócone obiekty są niemutowalne w pamięci; po odczycie JSON należy je ponownie zwalidować/utworzyć przez API. **Trwały zapis snapshotu i obsługa repozytorium sesji nie są wdrożone** — to następne kroki. Nie ma adaptera nadającego nowe zalecenia dawnym sesjom.

## Użycie (tylko model, nie integracja aplikacji)

```js
import {createModel, captureSessionSnapshot, createResultReference, Side}
  from './model/training-model.mjs';

const model = createModel(records); // wymagane tabele/pola pokazane w fixture testu
const snapshot = captureSessionSnapshot(model, {
  id: 'snapshot-id', sessionId: 'session-id', planVersionId: 'v1',
  unitId: 'unit', startedAt: '2026-10-22T10:00:00.000Z'
});
const binding = createResultReference(snapshot, {
  resultId: 'result-id', positionId: 'chest-position', setId: 'main-1',
  side: Side.LEFT, groupId: null, round: null
});
```

Przykładowy czas/ID są danymi ilustracji, nie aktywacją ani przypisaniem do historii. Model główny ma `schemaVersion:1`, `ownerId` i tablice exercises, variants, planVersions, positions, sets, drops, groups, coachInstructions, userNotes. Wersja kontraktu jest niezależna od IDB schema 1, dokumentu v1 i backupu v2. Owner jest zakresem grafu, nie logowaniem ani zabezpieczeniem profilu przeglądarki.

Dodatkowe pola JSON są zachowywane przez `createModel` bez selektywnej normalizacji. Nie-JSON (undefined/NaN/Date/cykle, dziurawe tablice, niejawne gettery, klucze prototypu) jest odrzucane zamiast znikać w przyszłym JSON. Standardowy round-trip JSON jest sprawdzony. To przygotowanie do bezstratnego eksportu/importu, **nie implementacja formatu ani adapterów kroku B**. Snapshot selekcjonuje potrzebne rekordy planu; nie zastępuje pełnej kopii całego modelu i notatek.

## D1–D9 i bezpieczeństwo historii

- D1: unspecified + pusta lista celów pozycji reprezentują Brzuch/Łydkę bez zgadywania liczby serii; same ćwiczenia/pozycje nie znikają.
- D2: 10 wybranych wariantów ma reprezentację kontraktową sprawdzoną fixture testu. Nie dodano produkcyjnego seeda nowego V2. Nowa maszyna PUSH-A-4 ma odrębną tożsamość w przykładzie; legacy dipy i ich powiązania pozostają. Relacja zastąpienia pozycji nie jest równoważnością ćwiczeń; wymagane decyzje O1/O2/O3 nadal aktualne.
- D3/D4: zmienne segmenty drop i odrębne referencje rezultatów członków grupy/rund. Test konkretnej pary: dwie rundy/8–10, 15 s w środku, null po parze; brak „max”.
- D5: osobne referencje L/P i jawna konwencja. Kopiowanie wartości w edytorze nie jest implementowane. Brak mnożnika/konwersji i brak nowego algorytmu tonażu.
- D6: oddzielne rekordy, zachowane legacy-shared i nieznana data/autor.
- D7: jawny session-start snapshot, brak aktywacji/activatedAt/automatycznego datowania.
- D8: wykonano tylko osobno zlecony krok A. Żadnych kroków B–H, migracji, UI, hostingu, Drive/OAuth.
- D9: zachowanie tekstu instrukcji i opcjonalnych konkretnych przerw bez wymuszania timera/końca serii.

Model nie rozpoznaje znaczenia ćwiczeń po nazwach i nie scala ich automatycznie. Przyszły adapter musi poprawnie wskazać tożsamości i tylko jawne nowe sesje; nie wolno użyć konstruktora snapshotu do „naprawienia” nieznanej historycznej wersji. Nie ma tu synchronizacji, indeksów, edycji, wyników numerycznych nowego edytora ani polityki aktywowania draftu.

## Weryfikacja

Istniejący `node:test`, bez nowych zależności lub frameworka:

```sh
node --test tests/*.test.*
python3 scripts/build_release.py --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

12 testów nowego modelu obejmuje typy i relacje (w tym tabelę wadliwych danych), odrębność dipów i maszyny, historyczne ID, back-off/drop/grupy/strony, null, JSON round-trip, snapshot po zmianie planu, notatki oraz 10 wariantów D2. Test izolacji porównuje runtime z bazą i importuje moduł z pułapkami na indexedDB/localStorage/document/fetch. Do istniejącego workflow dopisano wyłącznie wykrywanie plików testów Node, bez nowego joba/usługi.

Wyniki rzeczywiście wykonanych kontroli i ograniczenia: [STAGE_5B_A_TEST_REPORT.md](STAGE_5B_A_TEST_REPORT.md).
