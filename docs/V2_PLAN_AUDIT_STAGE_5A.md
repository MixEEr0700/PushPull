# Etap 5A — audyt V2: inwentaryzacja i blokada porównania źródłowego

**Status: AUDYT CZĘŚCIOWY, DO UZUPEŁNIENIA. V2 NIEZATWIERDZONY.** Baza `4540fa01441766280a80b60bda667e99a78a2711` (main po PR #4), gałąź `feature/stage-5a-v2-audit`. Bez zmian danych aplikacji.

## Dostęp do źródła i granice ustaleń

Wskazany przez właściciela dokument: [v2. PushPull 01.07.2026](https://docs.google.com/document/d/1gc-kRsciOapQRkiUGugmCSVcsEd5G3QpIgjchTRA-zc/edit). Tytuł pochodzi z polecenia właściciela, nie z odczytu dokumentu. Dnia 21.10.2026 zwykłe żądania HTTPS z weryfikacją TLS do `/edit` oraz `/export?format=txt` zwróciły **HTTP 401 Unauthorized**. Nie otrzymano pełnej treści, tabel, przypisów ani komentarzy. Nie konfigurowano OAuth/Drive, nie próbowano obchodzić uprawnień. Dostęp sieciowy środowiska nie oznacza uprawnień do prywatnego dokumentu.

Do ukończenia potrzebny jest **pełny eksport PDF lub DOCX**, obejmujący wszystkie cztery jednostki, tabele, nagłówki, objaśnienia oznaczeń i przypisy. Jeżeli komentarze/sugestie zawierają istotne zalecenia, trzeba dołączyć je osobno z datą i autorstwem; eksport nie musi ich zawierać. Przy skanach potrzebny czytelny obraz każdej strony. Nie ma potrzeby udostępniania całego Dysku ani danych logowania.

Nie wolno rozumieć „brak odczytu” jako „trener nie określił”. W szczególności nie ustalono, czy w oryginale brakuje parametrów Brzucha/Łydki. Nie można potwierdzić nawet liczby ćwiczeń dokumentu ani tego, że odpowiadają wszystkim 34 pozycjom aplikacji. Poniższe tabele obejmują **wszystkie pozycje kodu**, nie potwierdzoną kompletność dokumentu trenera.

Porównujemy demonstracyjny plan inicjalny w `app.js`, nie prywatną IndexedDB z telefonu. Istniejące instalacje mogą mieć inne parametry/notatki w zapisanej bazie; `fresh()` nie nadpisuje ich przy uruchomieniu. Zrzuty testów i fixture'y nie są historią użytkownika. Jeżeli właściciel chce porównać własne zmodyfikowane parametry, wystarczy dodatkowo zestaw samych parametrów ćwiczeń, bez historii ciężarów.

## Jak czytać tabelę wszystkich ćwiczeń

Źródła: **D** = dokument trenera, nieodczytany; **A7/A8/A9/A10** = odpowiedni wiersz `app.js` z deklaracją `raw`, **A11** = tworzenie pól `tempo`, `rir`, `notes`, ID. Repozytorium na bazowym commicie: [app.js](https://github.com/MixEEr0700/PushPull/blob/4540fa01441766280a80b60bda667e99a78a2711/app.js#L6).

Dla każdej pozycji oryginalna nazwa, wariant, kolejność, serie, zakresy, RIR, tempo, back-off/drop/grupowanie i instrukcje są **nieodczytane**. Wartości aktualne: nazwa/ewentualny wariant są jednym tekstem; RIR i tempo obu pól to dosłownie `do uzupełnienia`, `notes=''`; brak osobnej instrukcji trenera. Te wspólne wartości obowiązują **każdy wiersz** tabeli. Wariant zapisany w nazwie nie jest osobnym stabilnym modelem wariantu.

Kolumna kg to wyłącznie `initialKg` z demonstracyjnego kodu, używane jako podpowiedź przy braku poprzedniego wyniku. **Nie jest odczytanym zaleceniem trenera, potwierdzonym ciężarem historycznym ani proponowanym ciężarem nowego planu.** Puste kg oznacza pusty tekst, nie zero. `target` pokazano dosłownie, bez interpretacji znaków `+`, `/`, `drop` i `backoff`.

Statusy: **zgodne** tylko po odczycie i zgodności wszystkich ustalonych pól; **rozbieżne** po konkretnej sprzeczności ze źródłem; **niejednoznaczne** przy braku źródła lub niejasnym znaczeniu; **brak obsługi** dla potwierdzonej luki aplikacji, niezależnie od zgodności nazwy. Obecnie wszystkie porównania źródłowe są niejednoznaczne; luki modelu mają osobną macierz poniżej. Proponowana poprawka „wstrzymać” oznacza brak zgody na wpisanie nowych liczb, a nie zgodność starej wartości.

## PUSH A — 8 pozycji kodu

| Kolejność / ID | Oryginalna wartość | Aktualna nazwa / wariant | Serie | Target | kg demo | Proponowana poprawka | Źródło | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. `PUSH-A-1` | Nieodczytana (wszystkie pola) | Prostowanie ud obunóż | 3 | 8–10 | 105 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 2. `PUSH-A-2` | Nieodczytana (wszystkie pola) | Smith skos 30° | 2 | 5–7 | 80 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 3. `PUSH-A-3` | Nieodczytana (wszystkie pola) | Klatka maszyna | 2 | 5–7 + backoff | 102,5 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 4. `PUSH-A-4` | Nieodczytana (wszystkie pola) | Dipy | 2 | 8–10 | 90 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 5. `PUSH-A-5` | Nieodczytana (wszystkie pola) | Wznosy bok | 3 | 10–12 + drop | 20 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 6. `PUSH-A-6` | Nieodczytana (wszystkie pola) | Bayesian curl | 2 | 6–8 + backoff | 37,5 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 7. `PUSH-A-7` | Nieodczytana (wszystkie pola) | Triceps sznur zza głowy | 3 | 8–10 | 72,5 | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |
| 8. `PUSH-A-8` | Nieodczytana (wszystkie pola) | Brzuch | 3 | wg planu | puste | Wstrzymać; ustalić po eksporcie D | D / A7, A11 | niejednoznaczne |

## PULL A — 8 pozycji kodu

| Kolejność / ID | Oryginalna wartość | Aktualna nazwa / wariant | Serie | Target | kg demo | Proponowana poprawka | Źródło | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. `PULL-A-1` | Nieodczytana (wszystkie pola) | Uginanie ud | 3 | 8–10 | 57,5 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 2. `PULL-A-2` | Nieodczytana (wszystkie pola) | Odwodzenie ud | 2 | 10–12 | 105 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 3. `PULL-A-3` | Nieodczytana (wszystkie pola) | T-bar row | 2 | 5–7 + backoff | 107,5 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 4. `PULL-A-4` | Nieodczytana (wszystkie pola) | Drążek górny | 2 | 8–10 | 92,5 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 5. `PULL-A-5` | Nieodczytana (wszystkie pola) | Wiosłowanie jednorącz | 2 | 10–12 | 42,5 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 6. `PULL-A-6` | Nieodczytana (wszystkie pola) | Odwodzenie linką | 2 | 10–12 | 25 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 7. `PULL-A-7` | Nieodczytana (wszystkie pola) | Biceps sznur | 2 | 6–8 + backoff | 75 | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |
| 8. `PULL-A-8` | Nieodczytana (wszystkie pola) | Łydka | 3 | wg planu | puste | Wstrzymać; ustalić po eksporcie D | D / A8, A11 | niejednoznaczne |

## PUSH B — 9 pozycji kodu

| Kolejność / ID | Oryginalna wartość | Aktualna nazwa / wariant | Serie | Target | kg demo | Proponowana poprawka | Źródło | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. `PUSH-B-1` | Nieodczytana (wszystkie pola) | Prostowanie ud jednonóż | 3 | 10–12 | 105 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 2. `PUSH-B-2` | Nieodczytana (wszystkie pola) | Przywodzenie ud | 2 | 10–12 | 105 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 3. `PUSH-B-3` | Nieodczytana (wszystkie pola) | Butterfly | 2 | 8–10 | 65 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 4. `PUSH-B-4` | Nieodczytana (wszystkie pola) | Smith skos 60/75° | 2 | 5–7 + backoff | 60 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 5. `PUSH-B-5` | Nieodczytana (wszystkie pola) | Skos hantle 30° | 2 | 6–8 | 42,5 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 6. `PUSH-B-6` | Nieodczytana (wszystkie pola) | Biceps supinacja | 2 | 8–10 | 22,5 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 7. `PUSH-B-7` | Nieodczytana (wszystkie pola) | Cross cable triceps | 3 | 8–10 | 32,5 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 8. `PUSH-B-8` | Nieodczytana (wszystkie pola) | Wznosy linka dolna | 2 | 12 / 15–20 | 25 | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |
| 9. `PUSH-B-9` | Nieodczytana (wszystkie pola) | Brzuch | 3 | wg planu | puste | Wstrzymać; ustalić po eksporcie D | D / A9, A11 | niejednoznaczne |

## PULL B — 9 pozycji kodu

| Kolejność / ID | Oryginalna wartość | Aktualna nazwa / wariant | Serie | Target | kg demo | Proponowana poprawka | Źródło | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. `PULL-B-1` | Nieodczytana (wszystkie pola) | Uginanie ud jednonóż | 3 | 8–10 | 57,5 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 2. `PULL-B-2` | Nieodczytana (wszystkie pola) | Odwodzenie ud | 2 | 10–12 | 105 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 3. `PULL-B-3` | Nieodczytana (wszystkie pola) | Wiosłowanie hantlem | 2 | 8–10 | 47,5 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 4. `PULL-B-4` | Nieodczytana (wszystkie pola) | Ściąganie do biodra | 3 | 8–10 | 72,5 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 5. `PULL-B-5` | Nieodczytana (wszystkie pola) | Wiosłowanie maszyna | 2 | 8–10 | 80 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 6. `PULL-B-6` | Nieodczytana (wszystkie pola) | Narciarz + shrugs | 2 | 8–10 | 75 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 7. `PULL-B-7` | Nieodczytana (wszystkie pola) | Odwrotny butterfly | 3 | 12–15 + drop | 35 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 8. `PULL-B-8` | Nieodczytana (wszystkie pola) | Modlitewnik jednorącz | 2 | 8–10 | 17,5 | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |
| 9. `PULL-B-9` | Nieodczytana (wszystkie pola) | Łydka | 3 | wg planu | puste | Wstrzymać; ustalić po eksporcie D | D / A10, A11 | niejednoznaczne |

## Ustalenia możliwe bez dokumentu

- **34 pozycje:** PUSH A 8, PULL A 8, PUSH B 9, PULL B 9. Nie ma potwierdzenia, że taki jest układ oryginału. Wartości RIR/tempo są placeholderami wszystkich 34 pozycji.
- Tekst `+ backoff`: `PUSH-A-3`, `PUSH-A-6`, `PULL-A-3`, `PULL-A-7`, `PUSH-B-4`. Brak informacji strukturalnej, czy podane `sets=2` obejmuje back-off, ile jest serii głównych i jakie są ich zakresy. Nie wolno tego rozstrzygnąć z tekstu.
- Tekst `+ drop`: `PUSH-A-5`, `PULL-B-7`. Nie określa liczby segmentów, redukcji ciężaru, kryterium zakończenia ani tego, czy drop dotyczy każdej serii. Nie jest implementacją dropsetu.
- `PUSH-B-8`: `12 / 15–20` w jednym polu. Nie wiadomo, czy to dwa cele dla kolejnych serii, alternatywy czy zapis historyczny. Nie przypisujemy tego automatycznie do serii 1 i 2.
- `PULL-B-6`: nazwa `Narciarz + shrugs` nie tworzy dwóch powiązanych ćwiczeń. Nie dowodzi, że trener zalecił superserię, ani kolejności/przerw. Rejestrowany jest jeden wynik jednego exerciseId.
- `PUSH-A-8`, `PUSH-B-9` (Brzuch), `PULL-A-8`, `PULL-B-9` (Łydka): kod ma 3 serie i `wg planu`, ale nie ma dostępnego potwierdzenia tych 3 serii ani konkretnego ćwiczenia, zakresu, RIR czy tempa. Nie dopisano żadnego parametru.
- `app.js:28–36`: `exampleDescriptions` to demonstracyjne dopiski, nie zweryfikowane instrukcje trenera. Klucze np. `PUSH A-5` zawierają spację i nie pasują do generowanego `PUSH-A-5`; nowy plan nie dostaje tych dopisków na tej ścieżce. Nie używamy ich jako źródła, nie naprawiamy tego w audycie.

## Macierz rzeczywistych możliwości aplikacji

Ocena obejmuje walidację, zapis, odczyt, edycję i powiązania, a nie samą możliwość zachowania dodatkowego JSON. Dowody odnoszą się do kodu bazowego, nie przyszłej architektury etapu 4.

| Wymaganie | Stan i dowód | Status | Konsekwencja |
| --- | --- | --- | --- |
| Różne wykonane ciężary i powtórzenia w kolejnych seriach | `entries[].series[]` zawiera `kg` i `reps`, normalizowane w `sets` z kolejnością. Ołówek dodaje/usuwa i edytuje serie. `storage.js:46–53`, `indexeddb.js:131–148`, `app.js:40–44,96`. Regresja sprawdza 100×10 + 80×8 = 1640 kg, historię, restart i backup. | zgodne (funkcja zapisu wyników) | Działa zapis liczb wykonanych; to nie potwierdza parametrów V2. |
| Różne zaplanowane zakresy w seriach jednego ćwiczenia | Jedno `ex.target` typu string, jedna liczba `ex.sets`. Brak tablicy przepisanych celów, numerów/typów serii i walidacji min/max. `12 / 15–20` pozostaje etykietą. | brak obsługi | Wynik 12 i 18 można zapisać, ale aplikacja nie wiąże ich z osobnymi celami serii. |
| Back-off | Można ręcznie zapisać lżejszą serię i inny wynik. Brak roli top/backoff, powiązania z serią bazową, celu/procentu redukcji i reguły generowania. | brak obsługi | Nie deklarujemy obsługi planowanego back-off tylko na podstawie różnego kg i napisu w target. |
| Dropset | Płaska lista niezależnych serii, brak parentSetId/segmentów kolejnych redukcji i informacji o jednej serii złożonej. | brak obsługi | Dodanie kolejnych płaskich serii może zachować liczby, ale traci znaczenie segmentów i liczbę serii macierzystych. |
| Superserie / serie łączone | Jeden wpis na parę sessionId+exerciseId, brak groupId, rundy, powiązania ćwiczeń, kolejności wewnątrz rundy i przerw. Dodatkowe wpisy tej samej pary są zabronione przez walidator. | brak obsługi | Ani nazwa ze znakiem `+`, ani notatka nie tworzy grupy treningowej. Osobne wpisy dwóch ćwiczeń nie rejestrują ich powiązania. |
| Instrukcje trenera vs notatki osoby | W UI wspólne `ex.notes`; `notes` w IDB ma `origin: legacy-shared`. Katalog parametrów celowo usuwa `notes`. `app.js:62–65,96`, `indexeddb.js:52,126–128`. | brak obsługi | Zapis użytkownika zastępuje wspólny tekst; brak odrębnego wersjonowanego źródła instrukcji. `description` także nie dowodzi autorstwa. |
| RIR / tempo | Pola tekstowe na całe ćwiczenie, placeholdery w fresh; brak osobnych pól wykonania w edytorze serii i walidacji semantyki. | brak obsługi | Można wyświetlić tekst ćwiczenia, ale nie odtworzyć z niego zarejestrowanego RIR/tempa każdej serii. |
| Historia i wersje | Katalog snapshotów i odwołania sesji istnieją; starsze sesje mają `legacy-current-only`. Widok `historical()` nadal bierze karty z bieżącego `data.exercises[s.type]`. | brak obsługi pełnej prezentacji historycznych zaleceń | Sam katalog nie wystarczy do bezpiecznej zmiany planu. Przyszły widok musi czytać właściwy snapshot, bez zmiany zatwierdzonego układu. |

Nieznane pola JSON bywają zachowane przez `PushPullStorage.validate` i klonowanie w IDB, ale nie oznacza to ich obsługi: `getDraft` i normalizacja formularza serii tworzą nowe obiekty tylko `{kg,reps}`. Włożenie `dropSegments`, `role` czy `supersetId` do pliku nie tworzy funkcji, a edycja może pominąć te dodatki. Nie proponujemy takiego obejścia ani importu sztucznie rozszerzonego planu do aktualnej aplikacji.

## Zalecenia a wyniki i komentarze — protokół po otrzymaniu eksportu

Dla każdego pola zapisać dokładny cytat i lokalizację (strona/tabela/wiersz/kolumna; data/autor komentarza), a obok odrębną interpretację. Zapisać wersję/datę i hash otrzymanego eksportu w metadanych audytu. Prywatnego dokumentu ani historii nie dodawać automatycznie do Git — raport ma zawierać tylko materiał potrzebny do porównania.

Oznaczać kategorię źródła: **zalecenie**, **wynik historyczny**, **komentarz**, **zmiana wariantu**, **nieustalone**. Ciężary z datowanych treningów to wyniki, nie cel obciążenia na przyszłość. Komentarz nie nadpisuje instrukcji bez jasnego zakresu i potwierdzenia. Zmiana maszyny/kąta nie tworzy automatycznie nowego exerciseId. Nieczytelny zapis lub konflikt komentarza i tabeli zostaje niejednoznaczny.

Po odczycie dodać brakujące pozycje oryginału oraz oznaczyć ewentualne nadmiarowe pozycje kodu, bez usuwania rekordów. Dla każdego z wymaganych pól porównać dokładną oryginalną i obecną wartość, zaproponować konkretną poprawkę ze źródłem i wskazać wymagane funkcje modelu. Dopiero pełna tabela jest materiałem do akceptacji parametrów; ten dokument nim jeszcze nie jest.

## Decyzje wymagające właściciela (i ewentualnie trenera)

| ID | Decyzja / brakująca informacja | Co pozostaje wstrzymane |
| --- | --- | --- |
| D1 | Dostarczenie kompletnego eksportu i potwierdzenie, że to obowiązująca wersja `v2. PushPull 01.07.2026`; istotne komentarze i objaśnienia osobno. | Wszystkie źródłowe oceny zgodności i konkretne poprawki liczb. |
| D2 | Czy audyt ma obejmować wyłącznie demonstracyjny plan w repo, czy także późniejsze lokalne zmiany parametrów/maszyn? W drugim przypadku potrzebny zestaw samych parametrów i pochodzenia zmian. | Porównanie z własnym bieżącym planem, którego baza nie jest dostępna w repo. |
| D3 | Po odczycie: które komentarze/historyczne dopiski są aktywnymi zaleceniami, od kiedy i z czyim zatwierdzeniem? Pierwszeństwo sprzecznych zapisów musi potwierdzić właściciel/trener. | Nadpisanie instrukcji i datowanie nowej wersji. |
| D4 | Jeżeli eksport pozostawia niejasność: czy `sets` obejmuje back-off/drop, liczba segmentów, cele, redukcje i przerwy; czy `12 / 15–20` oznacza kolejność czy alternatywę; czy `Narciarz + shrugs` to grupa i w jakiej kolejności/rundach? | Strukturalne przepisanie niejasnych pozycji; nie pytamy o ponowne zatwierdzenie, jeśli eksport jednoznacznie odpowie. |
| D5 | Jeżeli dokument nie określa Brzucha/Łydki: pozostawić jawny brak parametrów czy uzyskać od trenera nowe zalecenie? Konkretne ćwiczenie, serie, zakresy, RIR i tempo wymagają źródła. | Dopisywanie parametrów i używanie demonstracyjnych 3 serii jako zatwierdzonych. |
| D6 | Powiązanie wariantów z dotychczasowym exerciseId w przypadkach niejednoznacznych; rozdzielenie treści `legacy-shared` na instrukcję i własne notatki tylko przez świadome wskazanie autorstwa. | Automatyczne łączenie po nazwie lub zgadywanie autorstwa. |
| D7 | Osobne zatwierdzenie etapu modelu poniżej i ewentualnych koniecznych rozszerzeń wprowadzania danych w zachowanym układzie Matrix. | Implementacja grup/segmentów/celów i migracji; obecny PR to dokumentacja. |
| D8 | Po pełnym audycie i testach: akceptacja tabeli parametrów oraz daty obowiązywania nowej wersji; istniejąca aktywna sesja zachowuje swój snapshot. | Aktywacja poprawionego V2; nic nie działa wstecz na wynikach. |

Lista D4–D6 jest warunkowa: dokument może usunąć część niejasności. Nie przesądzamy, że trener ich nie określił. Nie wymagamy od właściciela ponownego zatwierdzenia samego utworzenia tego audytu/PR, bo zostało zlecone.

## Dalszy etap i wyniki

[MODEL_EXTENSION_STAGE_5B_PROPOSAL.md](MODEL_EXTENSION_STAGE_5B_PROPOSAL.md) opisuje osobny etap modelu i migracji bez utraty historii. [STAGE_5A_TEST_REPORT.md](STAGE_5A_TEST_REPORT.md) podaje rzeczywiście wykonane kontrole i ograniczenia.

**Nie zatwierdzono V2 do codziennego treningu. Nie wykonano pełnego porównania źródłowego z powodu 401.**
