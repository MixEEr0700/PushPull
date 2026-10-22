# Krok C — minimalny zapis modelu i droga do telefonu

Baza: `main` po PR #7, `e6235acb2deca97fe932e833b156a3fdf01da7b8`. Zakres zlecony osobno: C, bez aktywacji nowego V2, zmiany Matrix, publikacji i synchronizacji. Niniejszy dokument aktualizuje kolejność prac; rozbudowana propozycja A–H pozostaje zapisem historycznym, nie obowiązkiem budowania dodatkowej infrastruktury.

## Co działa

`PushPullDB.open()` nadal otwiera bazę `pushpull`, schema 1. Nowy model to **jeden dodatkowy rekord** `meta['training-model-v1']`, zawierający rewizję źródła i pełny, walidowany dokument kopii v3. Bez nowej bazy, wersji IDB, tabel, indeksów, stagingu czy frameworka. Dla obecnej aplikacji czytającej pełny dziennik nie ma jeszcze potrzeby indeksowania pojedynczych nowych encji.

Nowe API istniejącego backendu:

- `prepareModel({backupText, ownerId})`: jawne przygotowanie modelu z pełnej bieżącej kopii v2. Bez wywołania tej metody uruchomienie/aktualizacja PWA **nie migruje danych do nowego modelu**. `app.js` jej nie wywołuje. Testy używają wyłącznie syntetycznych baz.
- `model`: odłączony payload modelu po migracji, do późniejszego podłączenia treningu.
- `exportModelBackup()`: pełny JSON v3 z modelami i bieżącymi archiwami, przy wykorzystaniu istniejącego modułu kroku B. Nie publikuje ani nie pobiera niczego automatycznie.

Przykład **wyłącznie dla profilu testowego**:

```js
const db = await PushPullDB.open(testFresh);
try {
  if (db.error) throw db.error;
  const backupText = JSON.stringify(db.export());
  // W późniejszym uruchomieniu na własnych danych najpierw zachować kopię poza origin.
  await db.prepareModel({backupText, ownerId: stableLocalOwnerId});
  const newCopy = await db.exportModelBackup();
  // newCopy można odtworzyć w pamięci przez previewBackup/restoreBackup z kroku B.
} finally { db.close(); }
```

API nie potrafi sprawdzić, czy plik został rzeczywiście zachowany poza przeglądarką. Nie uruchomiono go na danych użytkownika. Osobnego zatwierdzenia nadal wymaga rzeczywista migracja/wdrożenie.

## Co przenosi migracja

`model/legacy-model.mjs` używa kontraktów A i kopii B. Zachowuje ID ćwiczeń, całe wspólne notatki jako `legacy-shared`, pełne sesje i wyniki (w tym wszystkie serie i pola dodatkowe). Nowy model oznacza tożsamości jako `unresolved`: znamy legacy ID i nazwę, nie potwierdzamy automatycznie sprzętu/wykonania. Rewizja notatki 1 jest techniczną rewizją importu, bez wymyślonej daty lub autora.

Historyczne sesje mają `snapshotId:null`, wyniki `binding:'uninterpreted'`. Oryginalny istniejący link katalogu pozostaje w `legacyPlanLink`, z jego rzeczywistym provenance. **Nie tworzymy nowych historycznych PlanVersion, wariantów, snapshotów, celów, grup, stron ani interpretacji ciężarów.** Ich kolekcje nowego modelu są puste, dopóki nie powstaną jawnie w kolejnym funkcjonalnym etapie. Istniejące faktyczne katalogi i wersje, parametry, `initialKg`, znaczniki techniki i nieznane pola pozostają w pełnym źródle v2 w `legacySources`, bez zmiany oryginału.

Migracja nie wykonuje clear/delete/put na oryginalnych plans/planVersions/exercises/sessions/entries/sets/notes/changes ani na localStorage. Dopisuje tylko rekord modelu i dokładną kopię wejściową do istniejącego `backups` (deterministyczne ID `model-migration:<revision>`).

## Atomowość i wykorzystanie istniejącego zapisu

Przed zapisem: walidacja v3 oraz porównanie całej dostarczonej kopii z bieżącym źródłem. W jednej krótkiej istniejącej transakcji: kontrola rewizji, kompletne odczytanie/weryfikacja źródłowych rekordów, dopisanie kopii i modelu, porównanie odczytu z oczekiwanym. Hash i budowanie dokumentu wykonują się przed transakcją. Sukces i model w pamięci publikowane są dopiero po `oncomplete`. Abort, quota, uszkodzony odczyt lub zamknięcie karty wycofują oba dodatki. Retry odczytuje już zapisany model zamiast dopisywać rekordy/kopie.

Po **jawnej migracji profilu testowego** obecny `commit()` utrzymuje źródłową reprezentację i nowy model w tej samej transakcji. Obejmuje szybki zapis z istniejącego formularza, korekty i import. Błąd zapisu modelu wycofuje również zapis starych rekordów; nie pojawia się komunikat sukcesu, draft pozostaje. Przed importem istniejący mechanizm kopii zabezpiecza także dokument v3. Bez migracji pozostaje dotychczasowy zapis. Nowy kod nie zapisuje niezależnie drugiej historii.

Odczyt sprawdza hash oraz równość pełnej projekcji z faktycznie zatwierdzonym źródłem, nie tylko liczniki. Nowa karta przed migracją musi odświeżyć stan przed zapisem; zapis z niezgodnego starego backendu jest wykrywany po rewizji i blokuje otwarcie zamiast zaczynać pustą historię. Nie zmieniamy schematu IDB, więc **stary wdrożony kod nadal może zapisać źródło** — detekcja nie jest fizyczną blokadą starej wersji. Po przyszłej migracji nie wracać do starego wydania; zachować obie kopie przy konflikcie. Automatyczne rozstrzyganie takich konfliktów nie jest częścią C.

## Offline i kopie

Build i wygenerowany worker zawierają pięć modułów A/B/C. Serwer artefaktu podaje `.mjs` jako JavaScript. Zachowano dotychczasowy proces aktualizacji: sprawdzony cały shell, oczekiwanie na zamknięcie starych klientów, brak usuwania IndexedDB/localStorage. Nie zmieniono szablonu workera, manifestu, ID/start_url/scope, CSS, ikon ani `app.js`.

Dotychczasowy przycisk eksportu/importu nadal obsługuje v1/v2. Nowe pełne API v3 jest dostępne programowo; przywracanie v3 pozostaje odtworzeniem odrębnego modelu z kroku B, **nie operacją zastąpienia produkcyjnej bazy przez UI**. W tej wersji nowy model jest wyłącznie wierną projekcją źródła legacy: brak oddzielnie edytowanych planów/nowych wykonań. Przed ich dodaniem trzeba podłączyć pełny eksport/import v3 do istniejących kontrolek oraz rozszerzyć adapter zapisu; nie wolno odbudowywać przyszłych bogatszych danych tylko z v1/v2.

Dokument modelu to kompletna projekcja: zapis ma koszt proporcjonalny do historii, podobnie jak obecny backend. Nie mierzono granic dużych baz; nie dokładamy indeksów/optymalizacji przed realnym pomiarem. Kopie w tej samej przeglądarce nie chronią przed usunięciem profilu. Po późniejszym zatwierdzeniu migracji konieczna kopia poza urządzeniem.

## Najkrótsza ścieżka do normalnego treningu

| Funkcja | Już istnieje | Minimalna brakująca praca |
| --- | --- | --- |
| Plan i ostatnie wyniki | Render kart Matrix, rotacja, podpowiedzi ostatniego wyniku; model wersji i snapshotów A | Podłączyć jawny plan/cele i snapshot przy rozpoczęciu. Zatwierdzić tylko otwarte O1/O2/O3 z audytu; nie wymyślać parametrów nowej maszyny/istotnie zmienionych wariantów. |
| Szybkie kg/reps i serie | Szybki formularz, ołówek, różne wyniki serii i powielanie; kontrakty back-off/drop/grup/stron | Dodać konkretny zapis wykonań i małe kontrolki segmentów, członków/rund i stron w obecnych kartach. Powiązać cele poszczególnych serii. Opis „drop” w starym planie nie oznacza działającego edytora drop. |
| Historia, statystyki i kopie | Kalendarz, korekta, wykresy, tonaż, notatki, v1/v2; v3 A/B/C | Podłączyć wyniki/snapshoty do tych samych widoków i v3 do istniejącego importu/eksportu; każdy segment liczyć raz, starego tonażu nie zmieniać. Nie budować nowego panelu statystyk. |
| Telefon/offline | Manifest, ikony Androida, shell i aktualizacje, gotowy build oraz instrukcja instalacji | Po oddzielnej zgodzie publikacja statycznego artefaktu na stałym HTTPS i krótki test fizycznego telefonu z kopią poza urządzeniem. Nie deklarujemy testu fizycznego Androida. |
| Automatyczna chmura | Przenośny v3, stabilne ID/ownerId, hash, lokalna rewizja | Dopisać niewielką integrację indywidualnego Drive/OAuth, automatyczne wysyłanie po udanym commicie i pobieranie, z zachowaniem obu wersji w konflikcie. Obecnie nie ma żadnej synchronizacji. |

Proponowane dalsze prace po osobnym zatwierdzeniu:

1. **Jeden funkcjonalny etap „trening”**: podłączenie planu/snapshotu i zapisu wykonań oraz edytora celów/back-off/drop/grup/stron do Matrix; równolegle użycie istniejącej historii/statystyk i kontrolek pełnej kopii v3. Można podzielić na dwa małe PR (zapis/edytor oraz odczyt/historia), jeśli ułatwi to przegląd — bez obowiązkowych dodatkowych etapów infrastrukturalnych. Aktywacja poprawionego planu dopiero po potwierdzeniu brakujących parametrów i sprawdzeniu zapisu/odtworzenia.
2. **Telefon**: zatwierdzony, prosty statyczny hosting HTTPS niezależny od komputera, np. Cloudflare Pages, i instalacja/test prawdziwego treningu na Androidzie. Przy dopuszczeniu publicznego frontendu nie trzeba budować kontroli kont ani prywatnego hostingu; repo może pozostać prywatne. Publiczny kod nie obejmuje lokalnej historii. Stały origin zachować — zmiana domeny nie przenosi danych. Niczego teraz nie uruchomiono.
3. **Automatyczny Drive**: jeden plik pełnej kopii na indywidualnym Dysku, po udanym lokalnym zapisie i po powrocie sieci. Owner/ID i pełne źródła już są zachowane. Lokalna rewizja nie jest globalnym zegarem: porównywać hash wspólnej kopii, nie rozstrzygać konfliktem „ostatni zegar wygrywa”; zachować obie wersje do odzyskania. Ustalenie uprawnień OAuth i konfliktów dotyczy tego przyszłego funkcjonalnego PR, bez budowania teraz serwera/kont/journala synchronizacji.

Nie rozpoczęto powyższych prac. Dzisiejsza aplikacja pozwala na podstawowy zapis, historię i statystyki, ale nadal wyświetla dotychczasowy demonstracyjny plan i nie rejestruje pełnych struktur nowego V2 w UI. Nie jest jeszcze gotowa do codziennego używania zgodnie z całym zatwierdzonym planem.

## Weryfikacja tego PR

Wykorzystano istniejące node:test, unittest i Chromium. Sześć testów `test_model_migration.py` pokrywa pełny fixture (34 ćwiczenia, 5 sesji, 5 wpisów, 8 zapisanych serii, notatki/znaczniki i rozszerzenia), pustą historię, dokładny oryginał, przerwanie/quota/readback/retry, zamknięcie, brak duplikacji, aktualny formularz i atomowy rollback, import oraz stare karty/wersje. Jeden test w istniejącym `test_pwa.py` sprawdza model po aktualizacji workera i ponownym otwarciu offline. Dawne testy niezmienności plików zawężono tylko o celowo zmienione backend/build/worker; bramka byte-match UI i 12 porównań Matrix pozostały. Fixture historycznego stage3 przywraca jego rzeczywiste zasoby, bez modułów wtedy nieistniejących. Wyniki końcowe są w treści PR.

Końcowy przebieg lokalny: `node --test tests/*.test.*` **68/68 PASS**, `python3 -m unittest discover -s tests -p 'test_*.py' -v` **50/50 PASS** (43 wcześniejsze + 7 dotyczących nowych ryzyk), bez pominięć. Składnia JS, `git diff --check`, kontrola workera i build `dist/stage5bc-final` — PASS, wydanie `106eee6bcf2edebf782d72fb`, bez wdrożenia. Test aktualizacji po migracji zsynchronizowano z wcześniejszym asynchronicznym sprawdzeniem rejestracji SW; trzy oddzielne powtórzenia po tej korekcie także przeszły. Wynik istniejącego GitHub Actions dla aktualnego SHA jest podany w PR. Nie testowano fizycznego Androida ani rzeczywistej historii użytkownika; nie wykonano rzeczywistej migracji lub publikacji.
