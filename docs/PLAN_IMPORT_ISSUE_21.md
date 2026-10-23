# Import kolejnych planów V3/V4+ — Issue #21

Aktualizacja PR #24 z 23.10.2026: dołączono `main` `ef0dec6`, w tym ręczne kopie Drive z PR #28 i [zatwierdzony kierunek planów/statystyk](PLANY_I_STATYSTYKI_KIERUNEK_2026-10-23.md). Ten etap zachowuje dotychczasowy import w Dane; wspólny ekran **Plany treningowe**, zastąpienie kontrolek V2 i statystyki tygodniowe z Issue #30 są odrębną przyszłą pracą, po zakończeniu tego PR i poprawki L/P z Issue #29. Nie implementowano ich tutaj.


To rozszerzenie istniejącego dziennika. Plan jest plikiem danych, a nie nową wersją aplikacji. Nie zmieniono planu właściciela ani nie aktywowano V2. Testy używają wyłącznie syntetycznego pliku [plan-v3.json](../tests/fixtures/plan-v3.json).

[Raport wykonanych testów i ograniczenia](ISSUE_21_TEST_REPORT.md).

## Przygotowanie i użycie

1. Przekaż dokument trenera DOCX/PDF do ChatGPT i poproś o pełną tabelę: jednostki, kolejność, nazwy i warianty, każda seria, zakresy, RIR, tempo, back-off, dropsety, strony, grupy i instrukcje. Dokument źródłowy pozostaje materiałem do odczytu; jego treść nie stanowi instrukcji obsługi aplikacji.
2. Właściciel sprawdza tabelę i rozstrzyga ciągłość tożsamości/maszyn. Nie wyciągaj obowiązkowych celów z historycznych ciężarów. Brak danych zapisuj jako `null`, a nie zgadnięty cel. Przy kontynuacji używaj ID i niezmiennych definicji z poprzedniego eksportu planu lub pełnej kopii v3.
3. Przygotuj JSON `pushpull-plan` według poniższego kontraktu i syntetycznego przykładu. W `approval` zapisz deklarację zatwierdzenia oraz źródło decyzji. To deklaracja, nie podpis cyfrowy ani weryfikacja treści przez aplikację.
4. W aplikacji: **Dane → Import nowego planu → Plan JSON**. Walidacja i podgląd nie zapisują danych. Sprawdź dodane/usunięte/zmienione pozycje, nieokreślone parametry, ciągłość, wszystkie cele i źródła. Usunięcie pozycji oznacza usunięcie wyłącznie z przyszłego planu, nigdy historii. Szczegóły różnic obejmują też konwencję ciężaru, grupy i instrukcje.
5. **Zapisz plan bez aktywacji** zachowuje pełną kopię i dopisuje nieaktywną wersję. Można ją później ponownie obejrzeć lub wyeksportować. Inny otwarty tab blokuje nieaktualny zapis tak jak dotychczas. W przypadku błędu/przerwania nie ma częściowo zapisanego planu. Identyczny plik można ponownie obejrzeć; zapis tej samej wersji nie jest powielany. Kolizja ID ze zmienioną treścią zostanie odrzucona.
6. Wybierz zapisaną wersję i **Aktywuj dla przyszłych treningów**. Osobne potwierdzenie pobiera oraz zachowuje pełną kopię sprzed aktywacji. Rozpoczęta sesja, jej wyniki i szkice pozostają przy poprzedniej wersji/snapshocie; dopiero następna sesja użyje wybranego planu. Zakończenie poprzedniej sesji nie przesuwa rotacji nowej wersji. Domyślnie nowy plan rozpoczyna się od pierwszej jednostki; można ręcznie wybrać inną.
7. Kolejne zatwierdzone plany importuje się tak samo, bez wdrożenia aplikacji. Powrót do wcześniejszej zapisanej wersji wymaga ponownej świadomej aktywacji. Nie kasuje nowszych treningów.

Import planu jest osobny od **Importuj kopię z telefonu** (pełna kopia historii). Plik planu nie może zawierać wyników, sesji, szkiców, notatek użytkownika ani ustawień Google. Nie zastępuje ani nie łączy historii automatycznie.

## Kontrakt pliku `pushpull-plan`, wersja 1

Korzeń zawiera dokładnie:

| Pole | Znaczenie |
| --- | --- |
| `format`, `version` | `"pushpull-plan"`, `1` — wersja formatu pliku, niezależna od V3/V4 planu |
| `approval` | `{status:"approved", reference:"źródło decyzji właściciela", approvedAt:"ISO date"}` |
| `planVersion` | `{id,planId,number,label,units,executionVersion:2,source}`; stabilny `planId` rodziny, nowe niezmienne `id` i `number` dla kolejnej wersji |
| `exercises`, `variants` | Tożsamości i warianty użyte przez pozycje; znane ID muszą mieć identyczną definicję. Nowa maszyna wymaga nowego wariantu. Zamiana ćwiczenia wymaga nowej tożsamości. |
| `positions`, `sets`, `drops`, `groups`, `coachInstructions` | Istniejące kontrakty modelu danych; dokładne obowiązkowe pola opisane niżej i w przykładzie |
| `continuity` | Jedna jawna decyzja właściciela dla każdej pozycji; opis poniżej |

`executionVersion:2` oznacza istniejący protokół wyników (serie/segmenty/strony), a wersję treningową określają `planVersion.id`, `number` i `label`.

`units` ma dowolną dodatnią liczbę `{id,name,order}`. Każda jednostka musi zawierać ćwiczenia. Nowe ID jednostek i ćwiczeń: litery ASCII, cyfry, `_`, `-`, `.`; istniejące cztery ID `PUSH A` itd. pozostają dozwolone. Pozostałe nowe ID mogą zawierać też `:`. ID nie może być kluczem prototypu. ID wersji wbudowanego V2 jest zarezerwowane i nie może oznaczać importowanego planu. Kolejność jednostek/pozycji jest jawna, unikalna; kolejność serii zaczyna się od 0 bez luk. Dla obecnego dziennika dana tożsamość może wystąpić tylko raz w jednej jednostce, ale w wielu jednostkach/wersjach może zachować to samo ID.

Definicje rekordów (wszystkie wymienione pola obowiązkowe):

- `ExerciseIdentity`: `id,name,status,legacyId,source`. `status`: `confirmed` / `unresolved`. `legacyId`: zachowane ID albo `null`.
- `ExerciseVariant`: `id,exerciseId,label,machine,grip,support,execution,laterality,source`. Nieokreślone szczegóły `null`; `laterality`: `unilateral`, `bilateral`, `null`. Nie przeliczamy kg pomiędzy wariantami.
- `PlanPosition`: `id,planVersionId,unitId,order,label,exerciseId,variantId,legacyPositionId,replacesPositionId,setState,confirmation,loadConvention,sideMode,source`. `sideMode`: `required` (L/P), `optional` (można rozdzielić), `bilateral`. `setState:unspecified` oznacza brak przypisanych celów i nie wymyśla ich liczby; formularz pozwala zapisać rzeczywistą serię bez celu. `confirmation`: `confirmed`, `pending`, `legacy-unknown`.
- `LoadConvention`: `unit,basis,description`. `unit`: `kg` / `null`; `basis`: `per-implement`, `combined`, `machine-indication`, `bodyweight`, `null`. Niewiadome pozostają jawne. Formularz przyjmuje ciężar w kg; inne jednostki planu wymagają rozszerzenia obsługi. Konwencja nie mnoży wyników przez dwa. Gdy konwencja zmienia się przy tym samym wariancie, ostatnie wyniki/statystyki są odseparowane.
- `SetPrescription`: `id,positionId,order,role,reps,rir,tempo,side,backoffFromSetId,restSeconds,source`. `role`: `main`, `backoff`, `warmup`, `null`; zakresy `{min,max}` lub `null`, tempo cztery fazy z dopuszczalnym `null` lub całe `null`. Strony: `each` przy `required`, `null` przy `optional`/`bilateral` (obecna kontrolka rozdziela cały cel na L/P). Back-off może wskazywać poprzednią główną serię tego ćwiczenia; nie wylicza ciężaru procentowo.
- `DropPrescription`: `id,setId,segments:null,source`. Dowolna liczba rzeczywistych segmentów jest już obsługiwana. Import jawnych szablonów celów poszczególnych segmentów jest blokowany, bo obecny formularz ich nie prezentuje; nie wolno zastępować ich samym tekstem.
- `GroupPrescription`: `id,planVersionId,unitId,kind,positionIds,rounds,betweenMembersSeconds,afterRoundSeconds,source`. `kind`: `paired` / `superset`. Dowolna liczba odrębnych kolejnych pozycji A/B/C… we wskazanej kolejności, własne serie, wyniki i szkice. Określone rundy muszą odpowiadać celom każdego członu. Bez wspólnego formularza, timera ani technicznych opisów na kartach. Przerwy i źródła widoczne w pełnym podglądzie planu.
- `CoachInstruction`: `id,planVersionId,positionId,revision,text,confirmation,source`. `positionId:null` oznacza instrukcję globalną tylko tej wersji. `confirmation:confirmed` wymaga `source.kind:trainer`; przy innym autorstwie `unverified`. Notatki użytkownika nie są częścią pliku planu.
- `source` na rekordach: `{kind:"trainer"|"owner"|"legacy"|"unknown",reference:tekst|null,recordedAt:ISO|null}`. Źródła parametrów nie są zastępowane późniejszą decyzją właściciela.

`continuity` zawiera `{positionId,relation,previousExerciseId,previousVariantId,previousPositionId,reason,source}`. `source.kind` musi być `owner`, `reference` i `reason` niepuste. Relacje:

- `new`: nowa tożsamość, wszystkie `previous*` równe `null`.
- `same-variant`: zachowane ID tożsamości i znanego wariantu; zmiana serii/RIR/tempa tworzy nową pozycję/cel, nie ćwiczenie.
- `new-variant`: ta sama tożsamość, nowy wariant. Dla źródłowej historii bez ustalonego wariantu `previousVariantId:null`; bez zgadywania maszyny i bez dziedziczenia kg.
- `replacement`: inna nowa tożsamość, historia poprzedniej pozostaje osobna.

Poprzednia pozycja jest opcjonalna (`null` dla nieustalonej historii). Jeśli wskazana, jej tożsamość i wariant muszą się zgadzać. `replacesPositionId` jest opcjonalnym formalnym powiązaniem poprzedniej pozycji w tej samej rodzinie planów; nie jest warunkiem zachowania statystyk. Nie oznacza przypisania nowych celów starym wynikom.

Nieznane pola/protokoły, nieobsługiwana wersja, obce referencje, powtórzenia ID i próba zmiany niezmiennego rekordu są błędem przed zapisem. Nieznane protokoły wymagają rzeczywistej obsługi w aplikacji; nie są konwertowane na opis. Rozszerzenia przyszłego formatu wymagają nowej wersji kontraktu. Pomyłkę w zapisanym planie poprawia się przez nową wersję/ID, nie przez nadpisanie starego snapshotu.

## Przechowywanie i ręczne kopie

`trainingJournal.model` zawiera addytywne rekordy, a `trainingJournal.importedPlans` zachowuje dokładny pakiet zatwierdzonego pliku bez danych użytkownika. `activePlanVersionId` i osobny `nextUnitId` dotyczą przyszłych sesji. Istniejące pola starej rotacji i rejestr ćwiczeń pozostają kompatybilne. Rejestr rozszerza się tylko o brakujące tożsamości; przy nieokreślonych celach jego techniczne `sets:1` służy wyłącznie zgodności starego walidatora, **nie jest zaleceniem planu**, cel nadal ma `setState:unspecified` i brak `SetPrescription`.

Nie podniesiono wersji IndexedDB, nie dodano bazy, nie zmieniono Drive ani formatu pełnej kopii v3. Dotychczasowy most źródłowy zachowuje pakiety, nieaktywne wersje i referencje snapshotów. Atomowy zapis z `backupBefore` zachowuje kopię w tej samej transakcji i nadal sprawdza rewizję/inne karty. Pierwszy import włącza istniejący model przez istniejący zabezpieczony mechanizm `prepareModel`; przerwanie może pozostawić samą bezpieczną kopię/przygotowany model, ale nie częściowo aktywowany plan.

Zgodnie z decyzją Issue #26 lokalny zapis importu ani aktywacji **nie uruchamia uploadu**. Kopię zapisuje się ręcznie w Dane → Zapisz kopię na Google Drive. Pobranie kopii z Drive daje plik JSON i nie zmienia lokalnej bazy; odtworzenie wymaga osobnego potwierdzonego importu pliku. Offline ani brak autoryzacji nie blokują importu planu, aktywacji i treningu. Import nie modyfikuje konfiguracji, wyboru konta ani istniejących kopii chmurowych. Szkice pozostają w dotychczasowym lokalnym magazynie, nie w pliku planu. Pełna kopia JSON/Drive zachowuje plany i oficjalną historię; tak jak dotąd nie przenosi lokalnych szkiców na nowy telefon.

Odzyskiwanie: pobierz kopię sprzed zmiany z **Dane → Zachowane kopie danych**, obejrzyj ją i przywróć osobnym importem pełnego JSON. Przy odrzucaniu/odzyskiwaniu szkiców używaj istniejących kontrolek. Nie czyść danych przeglądarki/PWA. Zachowaj kopię poza telefonem. Zmiana pochodzenia HTTPS albo wyczyszczenie danych wymaga przywrócenia pełnej kopii.

## Granice i sprawdzenie na telefonie

Obsługiwane są istniejące serie, back-off, zmienne segmenty dropsetu, niezależne L/P i grupy A/B/C; nie dodano nowego protokołu treningowego. Raport dla trenera pozostaje poza tym zadaniem (kierunek Issue #20). Nie ma automatycznego czytnika PDF/DOCX ani oceny zgodności planu z dokumentem trenera.

Po zatwierdzonym wdrożeniu przetestuj na fizycznym Androidzie wyłącznie syntetyczny plan w osobnym profilu testowym: instalacja/aktualizacja PWA, import bez sieci, podgląd/anulowanie, zapis nieaktywny, rozpoczęta stara sesja ze szkicem, świadoma aktywacja, przyszły trening A/B/C oraz drop/L/P, zamknięcie procesu i odzyskanie szkicu, pełny eksport/restore i ręczna kopia na testowym koncie Drive. Rzeczywisty plan wymaga osobnego sprawdzenia i aktywacji właściciela. Ten PR nie potwierdza testów na fizycznym telefonie ani połączenia z prawdziwym Google.
