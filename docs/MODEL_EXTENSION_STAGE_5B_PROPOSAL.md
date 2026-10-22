# Propozycja osobnego etapu — struktury serii i instrukcji

**Projekt, bez implementacji i bez zmiany aktywnych parametrów V2.** Uzupełnia [architekturę etapu 4](TARGET_ARCHITECTURE_STAGE_4.md) oraz [audyt 5A](V2_PLAN_AUDIT_STAGE_5A.md). D8 właściciela z 22.10.2026 zatwierdza przygotowanie osobnego etapu, **nie implementację**. Nazwa „5B” jest oznaczeniem tego projektu, nie zgodą na kod/migrację ani zmianą harmonogramu wdrożeń. [Decyzje D1–D9](V2_PLAN_AUDIT_STAGE_5A.md#decyzje-właściciela-d1d9) odnotowano; pozostałe otwarte dane O1–O3 są w [projekcie 34 pozycji](V2_NEXT_PLAN_DRAFT_STAGE_5A.md).

## Konkretne wymagania potwierdzone w DOCX

- Pięć ćwiczeń ma **dwie serie główne i dodatkową trzecią back-off**: PUSH-A-3/PULL-A-3/PUSH-B-4 z 8–10 w dodatkowej, PUSH-A-6/PULL-A-7 z 10–12. Nie nadawać im stałego procentu redukcji bez źródła i nie powielać pierwszego celu na trzy serie.
- PUSH-B-8 wymaga jawnych celów seria 1:12 i seria 2:15–20, bez domyślnego oznaczania back-off/drop.
- PUSH-A-5 i PULL-B-7 wymagają drop w każdej serii macierzystej; przykład ciężaru i nieopisany ciąg z C2 nie wyznaczają uniwersalnych kilogramów/segmentów.
- PULL-B-6 wymaga dwóch ćwiczeń z osobnymi wynikami połączonych grupą i 15 s między ćwiczeniami, 2×8–10 dla obu. Nie zachowywać całej historii legacy jako wyniku obu ćwiczeń i nie dzielić jej automatycznie po nazwie.
- Cele „na rękę/na nogę” wymagają strony i jawnej konwencji obciążenia. Stare kg i tonaż bez konwencji zachować dokładnie, bez mnożenia przez 2. Nie wymuszać automatycznego podwojenia wyników na obie strony.
- Brzuch/Łydka w czterech pozycjach nie mają parametrów. W przyszłym modelu potrzebny status `unspecified` i nullable cele, niezależny od starego walidatora wymagającego sets≥1. Zachować źródłowe kodowe wartości jako legacy, nie jako zweryfikowane zalecenie.
- Tempo/RIR z C1, instrukcje techniczne C1/C2, przerwy globalne i wewnątrz grupy wymagają pochodzenia/wersjonowania. RIR i tempo w legendzie są objaśnieniami, nie domyślnymi parametrami.

## Wymagania właściciela D1–D9 dla następnego etapu

- D1: zachować wszystkie 34 pozycje, w tym nieokreślony Brzuch/Łydka. Rozdzielić brak celu od pustej historii; null/status niepełności nie generuje serii, RIR ani tempa. Stare kodowe sets=3 pozostają w źródle legacy, nie stają się zatwierdzonym celem.
- D2: 10 wybranych wariantów to projekt nowej wersji. Trener C1, uwagi C2 i wybór właściciela mają odrębne pochodzenie. Dla istotnie innego wariantu cele wymagają potwierdzenia; nie wystarczy skopiować liczb ze starego planu. Wszystkie dzisiejsze ID legacy i powiązania historyczne pozostają nietknięte.
- D3: lista segmentów drop ma zmienną długość; każdy segment przechowuje własne ciężar/powtórzenia. Nie narzucać procentu, kilogramów, stałej liczby segmentów ani automatycznego dopisania wykonania.
- D4: dwa człony (narciarz/szrugsy), dwie rundy, 8–10 dla obu, 15 s między członkami. Osobny wynik każdego członka w każdej rundzie, bez podmiany na „max”. Przerwa po parze nieokreślona; model grup może obsługiwać inne superserie, ale tego zapisu nie redukować do jednej płaskiej listy pod jednym ćwiczeniem.
- D5: jawny zapis L/P, szybkie kopiowanie przez świadomą akcję z możliwością korekty każdej strony; wspólne wprowadzenie nie oznacza automatycznego dublowania historii. Konwencja obciążenia ma własne pole i stan nieznany dla legacy. Testować różne kg/reps L/P i ochronę indywidualnej korekty przy ponownym kopiowaniu.
- D6: instrukcje trenera wersjonowane ze źródłem; notatki własne edytowalne odrębnie. `legacy-shared` i C2 bez znanego autora/daty zachować bez wymyślania podziału, autora czy daty zdarzenia.
- D7: świadoma aktywacja dopiero w przyszłej operacji; `activatedAt` nie jest datą tego dokumentu ani decyzji D2. Transakcja aktywacji zapisuje nową wersję i znacznik czasu z faktycznej operacji, a interfejs potwierdza ją dopiero po oncomplete. Trwająca sesja i stare sesje zachowują poprzedni snapshot; przyszłe sesje wybierają nową aktywną wersję.
- D8: wyłącznie przygotowanie modelu, migracji i kryteriów odbioru. Implementacja, PR wdrożeniowy i aktywacja wymagają osobnego zlecenia. Ten PR nie uruchamia migracji, hostingu ani Drive.
- D9: dosłowny zapis trenera pozostaje tekstem źródłowym; pola struktur mogą przechować jednoznaczne 15 s, lecz brak automatycznego wymuszania timerów/końca serii i przekształcania nieostrych fragmentów w twardy próg.

## Minimalne rozszerzenie modelu

| Obiekt | Wymagane znaczenie |
| --- | --- |
| Wersja zaleceń ćwiczenia | Powiązana z właściwą tożsamością ćwiczenia i niezmienną planVersionId, z legacyPositionId, lokalizacją źródła i pochodzeniem wyboru właściciela. Nie przepisywać historii do nowej wersji. |
| ExerciseIdentity / VariantVersion / PositionMapping | Istniejące ID i relacje zachowane; realna zamiana ćwiczenia otrzyma odrębną przyszłą tożsamość i mapę „zastępuje pozycję”, nigdy automatyczną równoważność. Wariant opisuje sprzęt/chwyt/stronę/podparcie i kontekst porównywalności, bez wymyślania dawnych dat. |
| Activation / SessionSnapshot | Aktywna wersja i activatedAt zapisane dopiero podczas świadomej przyszłej operacji D7. Nowa aktywacja nie zmienia snapshotu już rozpoczętej ani historycznej sesji. |
| SetPrescription | Stabilne prescriptionId, kolejność, rola `standard/top/backoff` (tylko gdy potwierdzona), min/max powtórzeń, RIR, tempo, opcjonalny związek z bazową serią i jawna reguła redukcji. Null = nieokreślone, nie zero. |
| DropPrescription | Seria macierzysta i elastyczna lista uporządkowanych segmentów. Każdy wykonany segment ma osobne kg/reps. Bez stałego procentu/liczby segmentów; obowiązek drop w każdej serii pochodzi z C1, reguły dodatkowe nie są odgadywane. |
| GroupPrescription | groupId, rodzaj `superset/paired/other`, uporządkowane prescriptionId różnych ćwiczeń, rundy i przerwy tylko jeśli podane. Nie wyprowadzać relacji ze znaku `+` w nazwie. |
| SetPerformance / SegmentPerformance | ID wykonanej serii i segmentu, entryId/sessionId/exerciseId, powiązanie z prescriptionId jeśli znane, kolejność/runda/groupInstanceId, wykonany ciężar/powtórzenia i opcjonalnie RIR/tempo. Zapis liczb oddzielny od celu. |
| Side / LoadConvention | Jawna strona wykonania, jednostka, ciężar jednego przyrządu vs pary i status nieznany dla legacy. Zachować oryginalny wynik oraz semantykę statystyki; zmiana algorytmu wymaga osobnego odbioru. |
| RestPrescription / Completeness | Opcjonalne przerwy między segmentami, członkami grupy, rundami i seriami; null przy braku źródła. Status kompletności zaleceń oddzielny od liczby wykonanych serii. |
| CoachInstruction / UserNote | Pierwsze wersjonowane wraz z planem, drugie własne z niezależną rewizją. Stare `legacy-shared` pozostaje dokładnym osobnym tekstem, bez automatycznego dzielenia. |

Trzymać dotychczasowe ID ćwiczeń, sesji i wyników **w historii legacy**; przy realnej zamianie nowa tożsamość dotyczy wyłącznie przyszłych wykonań. Nie przekierowywać starego ID do nowego ćwiczenia. Dla serii legacy obecnym kluczem jest `[entryId,position]`, nie stabilny UUID. Ewentualne nowe techniczne setId przypisać raz, zapisać w mapie i ponownie używać przy retry; zachować oryginalną pozycję i wartości. Zmiana kolejności lub etykiety nie uzasadnia podmiany historycznego exerciseId. Zmianę maszyny/wykonania ocenić jako wersję wariantu albo realną zmianę tożsamości; w obu przypadkach zachować poprzedni kontekst i nie scalać automatycznie statystyk. Nie tworzyć relacji drop/superset/backoff na podstawie samych ciężarów, liczby powtórzeń lub etykiety tekstowej.

### Przypadek PUSH-A-4 i ochrona porównywalności

PUSH-A-4 pozostaje identyfikatorem dawnych dipów wraz z wynikami, notatkami i snapshotami. D2 wybiera do przyszłej pozycji niepotwierdzoną jeszcze maszynę (neutralny chwyt, wysoko ustawione siedzisko). Projekt przewiduje nowe exerciseIdentityId dopiero po O1 i jawne mapowanie pozycji legacy do pozycji nowego planu; nie nadano faktycznego nowego ID. Mapowanie nie jest migracją wyników dipów ani automatycznym źródłem podpowiedzi kg dla maszyny. Parametry nowej tożsamości wymagają O2a.

Dla jednonóż/obunóż i zmiany maszyny/chwytu/podparcia oznaczać wersję i kontekst porównywalności. Nowy okres nie nadaje wstecz dat dawnym niedatowanym zmianom. W przyszłych statystykach/raportach musi dać się wybrać kontekst; nie przeliczać lub łączyć historycznych kg bez jawnej, osobno testowanej decyzji. D1–D9 nie udzielają zgody na zmianę bieżącego modułu statystyk.

Walidator: min≤max, dodatnie całkowite powtórzenia gdy określone, poprawne jednostki i skończone ciężary, spójne parent/group/round odniesienia w tej samej sesji/właścicielu, brak cykli i osieroconych segmentów. RIR/tempo walidowane według potwierdzonego kontraktu z obsługą jawnych braków. Nietypowy zapis dokumentu ma zachowany oryginał, a nie arbitralną normalizację.

Tonaż pozostaje obliczeniem ze źródła: segmenty wykonania policzone dokładnie raz, seria macierzysta jako kontener nie dodaje tej samej pracy drugi raz. Superseria nie sumuje ponownie rezultatów członków grupy. Starszych wyników bez serii nadal nie mnożyć. Nie zmieniać obecnej metodologii statystyk ani ich wyglądu bez osobnego testu/akceptacji; nowe grupowanie musi mieć testy braku podwójnego naliczania.

Obecny `historical()` renderuje bieżące parametry. Przed aktywacją nowych zaleceń musi korzystać ze snapshotu wskazanego przez katalog sesji, z jawnym pochodzeniem `legacy-current-only` dla starszych rekordów. Nie wolno fabrykować parametrów obowiązujących w nieznanej przeszłości. Rozszerzenia edytora potrzebne do rejestrowania segmentów/grup muszą być osobno zaakceptowane przy zachowaniu Matrix; opis tekstowy nie zastępuje tej funkcji.

## Bezpieczna migracja w osobnym PR

1. Zweryfikować stan v1/pełny backup v2, katalog, archiwa i raw localStorage; zabezpieczyć pełny eksport poza origin przed operacją. Nie używać samego lokalnego archiwum jako jedynej kopii.
2. Osobno wersjonować schemat IDB, format backupu i model zaleceń. Zachować bazę `pushpull`, ID/klucze oraz źródłowe store'y. Rozbudowa addytywna i blokada edycji nieobsługiwanym kodem; `versionchange` zamyka połączenia, `blocked` wymaga zamknięcia innych kart.
3. Zbudować staging z manifestem postępu/hash/licznikami i mapą technicznych ID. Wykonane płaskie serie pozostają legacy-flat z nieustaloną rolą, a nie automatycznie back-off/drop. `target`, `initialKg`, tempo/RIR placeholdery, nieznane pola i notatki zachowane dokładnie w kopii źródła.
4. Nieznane znaczenie starego target i brak historycznej wersji oznaczyć jawnie. Nowy zweryfikowany plan jest nową wersją; data wejścia w życie powstaje dopiero podczas świadomej aktywacji D7, nie z daty dokumentu/decyzji. Mapy odrębnych tożsamości nie przekierowują historycznych wpisów. Aktywna sesja zachowuje swój poprzedni snapshot; stare wyniki nigdy nie stają się nowymi zaleceniami obciążenia.
5. Odczyt kontrolny: pełna rekonstrukcja starego dokumentu, katalogu i archiwów, zgodność ID/liczb/relacji/hash, brak podwójnych serii i zachowanie tekstów. Przełączenie aktywnego modelu oraz complete w jednej transakcji dopiero po weryfikacji. UI potwierdza po oncomplete.
6. Quota, abort, zamknięcie i przerwana zmiana schematu nie aktywują pustego modelu. Idempotentne wznowienie ze źródła/staging, kontrola rewizji i wykrywanie starej aplikacji pozostają obowiązkowe. Bez automatycznego kasowania store'ów/localStorage i bez niezgodnego rollbacku kodu.
7. Pełny eksport nowego formatu musi obejmować grupy, segmenty, instrukcje i ich wersje, źródłowe legacy, mapy i archiwa. Import v1/v2 nadal bezstratny; starszy kod ma odrzucić nowszy format bez czyszczenia historii. Nowy import nie może traktować raportu trenera jako pełnej kopii.

## Testy wymagane przed akceptacją implementacji

- Różne cele dla kolejnych serii, top+back-off, dropset z co najmniej trzema segmentami, grupa co najmniej dwóch exerciseId i kilku rund. Jawne przypadki nieokreślonych celów; żadnych parametrów wymyślonych dla Brzucha/Łydki.
- Wykonanie, korekta historyczna i eksport/import zachowują wszystkie segmenty, relacje i dodatkowe pola po przejściu przez edytor; brak redukcji do `{kg,reps}`.
- Tonaż płaski legacy bez zmian, drop i superseria bez podwójnego liczenia, brakujące wartości sygnalizowane zamiast uzupełniane. Żadnego automatycznego mnożnika 2 dla legacy przy pojawieniu się stron.
- PUSH-A-4: wszystkie stare wyniki pozostają dipami; brak przeniesienia „ostatniego ciężaru” do nowej maszyny. Dla innych wariantów zachowane konteksty sprzętu/chwytu/podparcia, testy braku scalenia nieporównywalnych danych.
- Aktywacja: anulowanie nie zmienia wersji, zatwierdzenie zapisuje activatedAt dopiero w faktycznej operacji; abort/quota nie pokazuje sukcesu. Sesja rozpoczęta przed aktywacją i stare sesje zachowują snapshot.
- D3/D4/D5: dowolna liczba segmentów z różnymi kg/reps, dokładnie dwie rundy osobnych wyników pary z 15 s, brak „max”/przerwy po parze, kopiowanie L→P i P→L z korektą bez nadpisania indywidualnej strony po cichu.
- Nowa wersja zaleceń nie zmienia snapshotu trwającej ani zamkniętej sesji. Instrukcja trenera nie jest nadpisywana przy zapisie notatki osoby.
- Migracja pusta/pełna/duża, nieznane pola, brak serii legacy, Unicode, brak miejsca, abort na każdym punkcie, zamknięcie/retry, konflikt rewizji i stare karty.
- Nowy backup i odtworzenie na odrębnym origin, porównanie całej historii i kopii, offline/restart procesu/aktualizacja PWA. Dotychczasowa regresja i porównania Matrix z `92390b1`.

Ten etap nie wymaga Drive ani hostingu. Niczego z powyższego nie wdrożono w audycie 5A. Szczegółowy model i interakcje muszą uwzględnić odczytany dokument i zatwierdzone decyzje z audytu, zanim powstanie migracja produkcyjna.

## Proponowana kolejność małych PR

**To plan kolejnych prac, a nie utworzone PR ani autoryzacja implementacji.** Litery A–H są robocze; nie rezerwują numerów GitHub. Każdy krok wymaga osobnego zlecenia w ramach D8, pełnej regresji poprzednich funkcji i przeglądu przed scaleniem. Nie łączyć przygotowania nowego schematu z aktywacją poprawionego planu. Cały czas zachować Matrix, ikony, PWA, dane i kopie; żaden krok nie wymaga Drive, OAuth ani hostingu.

| Krok | Mały zakres | Bramka wejścia i oddzielnie weryfikowany wynik |
| --- | --- | --- |
| PR A — kontrakty domenowe | Rozdzielenie ExerciseIdentity, VariantVersion, PlanPosition i map; cele serii/segmentów/grup/stron, pochodzenie, unknown, wersje i snapshoty. Bez zmiany aktywnego planu i bez migracji. | Osobne zlecenie implementacji. Testy ID/relacji, braku automatycznej równoważności dipów i nowej maszyny, jawnych braków Brzucha/Łydki, niezmienności oryginału trenera i źródła wyboru właściciela. O1/O2 mogą pozostać unknown w modelu, nie fikcyjnymi wartościami. |
| PR B — pełna kopia i odtworzenie | Osobno wersjonowany format dla wszystkich nowych encji oraz adaptery bezstratnego odczytu v1/v2. Przed zmianą bazy gotowy eksport/import/odzyskiwanie nowego modelu. | A. Testy round-trip ID, map, wersji, instrukcji/notatek, grup, segmentów, stron i archiwów; błędne/nieznane wersje odrzucone bez zmian. Odtworzenie na odrębnym testowym origin/profilu, nie na jedynej historii. |
| PR C — addytywna migracja IDB | Staging, manifest postępu, idempotencja, readback i atomowe przełączenie modelu, zachowane store'y/raw legacy. Zabezpieczenie starego kodu i wielu kart. Bez nowego planu. | A+B oraz pełny eksport istniejącej historii poza przeglądarką przed migracją. Testy empty/full/duża baza, abort/quota/zamknięcie/retry, hash/liczby/relacje, brak nowej tożsamości dla starych wyników, brak podwojenia stron/tonażu. Sukces dopiero oncomplete. |
| PR D — adapter sesji i snapshotów | Odczyt bieżącej i historycznej sesji z jej własnej wersji, zachowanie legacy-current-only, repozytorium źródła, notatki i wersjonowane instrukcje. Bez aktywacji nowego planu. | C. Historyczne nazwy/cele/ID nie zmieniają się po dodaniu nieaktywnej wersji; stary tekst legacy-shared zachowany; brak wymyślania dawnych dat i autorów. Te same widoki Matrix i wyniki statystyk w regresji. |
| PR E — edytor serii i stron | Osobne cele serii i back-off, L/P, jawna konwencja oraz świadome kopiowanie L↔P z korektą; zachowanie szybkiego zapisu i ołówka. | D. Osobna akceptacja koniecznych kontrolek w Matrix bez zmiany motywu/kart. Testy różnych celów, różnych kg/reps L/P, kopiowania i zachowania korekt, błędu zapisu/draftu, edycji historii i backupu. Żadnego mnożnika 2 dla legacy. |
| PR F — segmenty drop | Dowolna liczba segmentów, oddzielne kg/reps, powiązanie z serią macierzystą i obowiązek drop według źródła. Bez stałych kilogramów/procentów. | E. Testy 1/wielu segmentów, korekty/dodania/usunięcia, pełnego eksportu i odtworzenia, sumowania każdego wykonanego segmentu dokładnie raz, zachowania istniejących płaskich serii i draftów po błędzie. |
| PR G — grupy i rundy | Osobne ćwiczenia/wyniki w grupie, dwie rundy narciarz/szrugsy, 8–10 dla obu, 15 s w środku, brak nieznanej przerwy po parze. Bez wymuszania timerów. | E+F oraz uzgodnione kontrolki. Testy relacji i kolejności, odrębnych wyników każdego ćwiczenia/rundy, korekty, backupu, braku celu „max” i podwójnego tonażu. Jeden wynik legacy pary nie jest kopiowany na obu członków. |
| PR H — wersja planu i świadoma aktywacja | Zaimportowanie sprawdzonej, nieaktywnej wersji z projektem 34 pozycji; podgląd różnic, backup, anulowanie/potwierdzenie, data wyłącznie z rzeczywistej operacji. | A–G, osobna zgoda na aktywację, rozstrzygnięte O1 i O2a–O2e dla konkretnych zmienionych ćwiczeń oraz jawne konwencje O3 przed wpisywaniem nowych wyników. D1 pozostaje odroczone. Testy anulowania/abort/quota, daty i wersji, sesji trwającej przed aktywacją, historycznych snapshotów, nowej sesji po aktywacji, restartu/offline i aktualizacji PWA bez resetu. |

Kopie nowego modelu muszą być gotowe **przed** jego migracją, nie dopiero po zmianie historii. Oddzielny etap edytora nie może niszczyć metadanych podczas ponownego zapisu `{kg,reps}`; zachowanie wszystkich struktur jest bramką następnych kroków. Każdy PR ma sprawdzić niezmienność pozostałych zatwierdzonych funkcji, kompletność eksportu i Matrix; lokalny mobilny viewport nie zastępuje fizycznego telefonu. Publikacja aplikacji i testy telefonu są nadal osobnymi zadaniami, bez domniemanej zgody na hosting.
