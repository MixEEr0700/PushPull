# Propozycja osobnego etapu — struktury serii i instrukcji

**Projekt, bez implementacji i bez przypisania parametrów V2.** Uzupełnia [architekturę etapu 4](TARGET_ARCHITECTURE_STAGE_4.md) oraz [audyt 5A](V2_PLAN_AUDIT_STAGE_5A.md). Nazwa „5B” oznacza propozycję zakresu do osobnego zatwierdzenia, nie zmianę harmonogramu bez decyzji właściciela. Najpierw uzyskać kompletny dokument i rozstrzygnąć źródłowe znaczenie zaleceń.

## Minimalne rozszerzenie modelu

| Obiekt | Wymagane znaczenie |
| --- | --- |
| Wersja zaleceń ćwiczenia | Powiązana z istniejącym exerciseId i niezmienną planVersionId, z lokalizacją źródła i datą obowiązywania. Nie przepisywać historii do nowej wersji. |
| SetPrescription | Stabilne prescriptionId, kolejność, rola `standard/top/backoff` (tylko gdy potwierdzona), min/max powtórzeń, RIR, tempo, opcjonalny związek z bazową serią i jawna reguła redukcji. Null = nieokreślone, nie zero. |
| DropPrescription | Seria macierzysta z uporządkowanymi segmentami; cel/rule dla segmentu osobno, bez zgadywania procentu redukcji. Traktowanie segmentów i kompletności jako jednej serii określa plan. |
| GroupPrescription | groupId, rodzaj `superset/paired/other`, uporządkowane prescriptionId różnych ćwiczeń, rundy i przerwy tylko jeśli podane. Nie wyprowadzać relacji ze znaku `+` w nazwie. |
| SetPerformance / SegmentPerformance | ID wykonanej serii i segmentu, entryId/sessionId/exerciseId, powiązanie z prescriptionId jeśli znane, kolejność/runda/groupInstanceId, wykonany ciężar/powtórzenia i opcjonalnie RIR/tempo. Zapis liczb oddzielny od celu. |
| CoachInstruction / UserNote | Pierwsze wersjonowane wraz z planem, drugie własne z niezależną rewizją. Stare `legacy-shared` pozostaje dokładnym osobnym tekstem, bez automatycznego dzielenia. |

Trzymać dotychczasowe ID ćwiczeń, sesji i wyników. Dla serii legacy obecnym kluczem jest `[entryId,position]`, nie stabilny UUID. Ewentualne nowe techniczne setId przypisać raz, zapisać w mapie i ponownie używać przy retry; zachować oryginalną pozycję i wartości. Nie zmieniać exerciseId z powodu nowej kolejności/maszyny czy korekty nazwy. Nie tworzyć relacji drop/superset/backoff na podstawie samych ciężarów, liczby powtórzeń lub etykiety tekstowej.

Walidator: min≤max, dodatnie całkowite powtórzenia gdy określone, poprawne jednostki i skończone ciężary, spójne parent/group/round odniesienia w tej samej sesji/właścicielu, brak cykli i osieroconych segmentów. RIR/tempo walidowane według potwierdzonego kontraktu z obsługą jawnych braków. Nietypowy zapis dokumentu ma zachowany oryginał, a nie arbitralną normalizację.

Tonaż pozostaje obliczeniem ze źródła: segmenty wykonania policzone dokładnie raz, seria macierzysta jako kontener nie dodaje tej samej pracy drugi raz. Superseria nie sumuje ponownie rezultatów członków grupy. Starszych wyników bez serii nadal nie mnożyć. Nie zmieniać obecnej metodologii statystyk ani ich wyglądu bez osobnego testu/akceptacji; nowe grupowanie musi mieć testy braku podwójnego naliczania.

Obecny `historical()` renderuje bieżące parametry. Przed aktywacją nowych zaleceń musi korzystać ze snapshotu wskazanego przez katalog sesji, z jawnym pochodzeniem `legacy-current-only` dla starszych rekordów. Nie wolno fabrykować parametrów obowiązujących w nieznanej przeszłości. Rozszerzenia edytora potrzebne do rejestrowania segmentów/grup muszą być osobno zaakceptowane przy zachowaniu Matrix; opis tekstowy nie zastępuje tej funkcji.

## Bezpieczna migracja w osobnym PR

1. Zweryfikować stan v1/pełny backup v2, katalog, archiwa i raw localStorage; zabezpieczyć pełny eksport poza origin przed operacją. Nie używać samego lokalnego archiwum jako jedynej kopii.
2. Osobno wersjonować schemat IDB, format backupu i model zaleceń. Zachować bazę `pushpull`, ID/klucze oraz źródłowe store'y. Rozbudowa addytywna i blokada edycji nieobsługiwanym kodem; `versionchange` zamyka połączenia, `blocked` wymaga zamknięcia innych kart.
3. Zbudować staging z manifestem postępu/hash/licznikami i mapą technicznych ID. Wykonane płaskie serie pozostają legacy-flat z nieustaloną rolą, a nie automatycznie back-off/drop. `target`, `initialKg`, tempo/RIR placeholdery, nieznane pola i notatki zachowane dokładnie w kopii źródła.
4. Nieznane znaczenie starego target i brak historycznej wersji oznaczyć jawnie. Nowy zweryfikowany plan jest nową wersją od zaakceptowanej daty. Aktywna sesja zachowuje swój poprzedni snapshot; stare wyniki nigdy nie stają się nowymi zaleceniami obciążenia.
5. Odczyt kontrolny: pełna rekonstrukcja starego dokumentu, katalogu i archiwów, zgodność ID/liczb/relacji/hash, brak podwójnych serii i zachowanie tekstów. Przełączenie aktywnego modelu oraz complete w jednej transakcji dopiero po weryfikacji. UI potwierdza po oncomplete.
6. Quota, abort, zamknięcie i przerwana zmiana schematu nie aktywują pustego modelu. Idempotentne wznowienie ze źródła/staging, kontrola rewizji i wykrywanie starej aplikacji pozostają obowiązkowe. Bez automatycznego kasowania store'ów/localStorage i bez niezgodnego rollbacku kodu.
7. Pełny eksport nowego formatu musi obejmować grupy, segmenty, instrukcje i ich wersje, źródłowe legacy, mapy i archiwa. Import v1/v2 nadal bezstratny; starszy kod ma odrzucić nowszy format bez czyszczenia historii. Nowy import nie może traktować raportu trenera jako pełnej kopii.

## Testy wymagane przed akceptacją implementacji

- Różne cele dla kolejnych serii, top+back-off, dropset z co najmniej trzema segmentami, grupa co najmniej dwóch exerciseId i kilku rund. Jawne przypadki nieokreślonych celów; żadnych parametrów wymyślonych dla Brzucha/Łydki.
- Wykonanie, korekta historyczna i eksport/import zachowują wszystkie segmenty, relacje i dodatkowe pola po przejściu przez edytor; brak redukcji do `{kg,reps}`.
- Tonaż płaski legacy bez zmian, drop i superseria bez podwójnego liczenia, brakujące wartości sygnalizowane zamiast uzupełniane.
- Nowa wersja zaleceń nie zmienia snapshotu trwającej ani zamkniętej sesji. Instrukcja trenera nie jest nadpisywana przy zapisie notatki osoby.
- Migracja pusta/pełna/duża, nieznane pola, brak serii legacy, Unicode, brak miejsca, abort na każdym punkcie, zamknięcie/retry, konflikt rewizji i stare karty.
- Nowy backup i odtworzenie na odrębnym origin, porównanie całej historii i kopii, offline/restart procesu/aktualizacja PWA. Dotychczasowa regresja i porównania Matrix z `92390b1`.

Ten etap nie wymaga Drive ani hostingu. Niczego z powyższego nie wdrożono w audycie 5A. Szczegółowy model i interakcje muszą być ocenione po odczytaniu dokumentu, zanim powstanie migracja produkcyjna.
