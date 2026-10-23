# Plany treningowe i statystyki tygodniowe — Issue #30

Realizacja [zatwierdzonego kierunku](PLANY_I_STATYSTYKI_KIERUNEK_2026-10-23.md), na bazie main `133bbd7`. Nowy ekran **Dane → Plany treningowe** zastępuje osobne kontrolki V2. Dolna nawigacja, karty treningowe, CSS Matrix, ćwiczenia, konwencje tonażu i lokalny zapis pozostają zachowane. Nie jest wykonywana migracja ani automatyczna aktywacja planu.

## Plany

- Aktualny plan, nazwa, numer wersji i faktycznie zachowana data aktywacji (brak daty nie jest uzupełniany dzisiejszą).
- Poprzednie wersje i zapisane/dostępne plany. Podgląd pokazuje jednostki, kolejność, wariant/sprzęt, cele każdej serii, back-off, segmenty dropsetu, strony, konwencje ciężaru, przerwy, grupy/rundy i instrukcje trenera ze źródłami. Nieokreślone parametry pozostają nieokreślone.
- **Importuj nowy plan** wykorzystuje parser, walidację, porównanie i zapis PR #24. Format pliku nie zmienia się: [instrukcja importu](PLAN_IMPORT_ISSUE_21.md). Sam import nie aktywuje planu.
- **Aktywuj dla przyszłych treningów** wymaga potwierdzenia, pobiera kopię i wykorzystuje istniejący zapis z kopią poprzedniego stanu. Bieżąca sesja, szkice i snapshoty pozostają przy swoim planie. Aktywny plan nie oferuje ponownej aktywacji; jest też kontrola w handlerze i idempotencja aktywacji importowanych wersji.
- V2 pozostaje na liście jak inne wersje; samo otwarcie ekranu ani aktualizacja aplikacji nie dopisują aktywacji. Eksport zapisanych planów V3+ jest zachowany.

## Wiarygodne przypisanie historii

Kolejność odczytu: zgodny snapshot sesji → jawne powiązanie starego katalogu `session-start` z wersją `recorded` → zapisane ID szkieletu → **Nieprzypisane / historyczne**. Wersje starego katalogu pokazujemy jako zapisany szkielet jednostki, nie zatwierdzony plan trenera. `legacy-current-only` z dawnej migracji nie dowodzi przeszłych parametrów i nie przypisuje starych treningów do V2. Parametry historycznego podglądu pochodzą z zachowanej wersji/snapshotu, nigdy z obecnego planu zamiast utraconej wersji.

To jedynie indeks odczytu. Wirtualne klucze widoków `@source`, `@unassigned`, `@legacy:…` nie są identyfikatorami zapisywanymi w bazie. Nie zmieniamy sesji, wyników, ID, notatek, instrukcji, znaczników, szkiców i snapshotów.

## Statystyki ogólne

**Dane → Statystyki ogólne** domyślnie wybiera aktywny plan. Można wybrać archiwalny plan lub nieprzypisane dane, zakres dat oraz tonaż/serie/powtórzenia/treningi; dostępne są wykres i tabela. Zakres początkowy to ostatnie 12 tygodni kalendarzowych do dziś. Dzień bieżący wyznacza `Europe/Warsaw`; zapisane daty sesji są datami kalendarzowymi, bez ponownej konwersji przez UTC. Tygodnie ISO: poniedziałek–niedziela, także na przełomie lat i zmianie czasu. Liczy się aktualna data sesji, nie data importu lub aktywacji.

### Jawna konwencja liczenia

- Tylko zakończone sesje: trening liczony raz. Szkice i sesje w toku nie wchodzą do zestawienia, nawet jeśli mają zatwierdzone wyniki części ćwiczeń.
- Tonaż = suma zapisanych `kg × powtórzenia`, każdy segment/strona dokładnie raz. Dla nowych wyników odczytujemy strukturalne wykonanie; spłaszczona projekcja nie jest dodawana drugi raz. Dla starszych — faktycznie zachowaną listę serii. Brak konwersji ciężarów i automatycznego ×2.
- **Jedna seria wykonania to jeden zapisany wiersz wyniku.** L i P liczone osobno; back-off jako osobny wiersz. Dropset z dowolną liczbą segmentów jest jedną serią danego wykonania/strony, a wszystkie segmenty zwiększają tonaż i powtórzenia. Osobne ćwiczenia A/B/C liczone raz każde. Jest to konwencja objętości wykonania, nie liczba wspólnych celów L/P w planie; opis widoczny w aplikacji.
- Starszy skrót kg/powtórzenia bez listy serii nie dowodzi liczby wykonanych serii. Nie mnożymy go przez plan. Brakujące metryki oznaczamy `≥`/„Brak pełnych danych”; zachowane podsumowanie pozostaje w historii ćwiczenia. Nieokreślona konwencja kg jest jawnie oznaczona, nie zgadywana.
- Zero oznacza brak zapisów w tygodniu; nie jest imputacją aktywności. Puste zakończone sesje mają znaną frekwencję, lecz niepełną objętość. Błędne daty są pomijane z ostrzeżeniem.
- Tydzień bieżący, przyszły lub obcięty zakresem jest częściowy. Zmiany liczymy tylko pomiędzy sąsiednimi pełnymi tygodniami z kompletną daną metryką. Przy zerowej bazie pokazujemy różnicę bez procentu. Wzrost objętości sam nie dowodzi wzrostu siły.

Agregaty są obliczane przy odczycie, nie zapisywane do IndexedDB. Korekta historycznej daty lub serii jest od razu uwzględniona. Statystyki pojedynczego ćwiczenia pozostają; gdy ten sam wariant ma wyniki wielu planów, dodatkowy filtr pozwala wybrać plan. Nadal obowiązuje dotychczasowa izolacja wariantów i konwencji ciężaru, historia nie jest zerowana ani przenoszona po nazwie.

## Weryfikacja i ograniczenia

Nowe testy obejmują ISO/Warsaw/DST, luki tygodniowe i brakujące dane, L/P/drop/back-off/A/B, rozdzielenie wersji, korekty historyczne, niezmienność snapshotów, import i aktywację tylko dla przyszłych sesji, restart szkicu, odtworzenie JSON i ręczny Drive z symulowanym Google oraz aktualizację z `133bbd7` i działanie offline. Wykonywana jest też pełna dotychczasowa regresja Node/Chromium, w tym wzorzec mobilny Matrix.

Nie wykonywano testów na fizycznym Androidzie ani rzeczywistym koncie Google. Nie wprowadzono nowego planu użytkownika ani jego danych do testów. Same statystyki nie naprawiają brakujących dawnych serii lub nieznanej wersji; pokazują te ograniczenia. Zwykłe ryzyko usunięcia/wyczyszczenia danych przeglądarki pozostaje — ręczne kopie JSON/Drive nadal są potrzebne; szkice pozostają lokalnie zgodnie z dotychczasowym mechanizmem.

Pełne kopie obejmują zachowane archiwa. W syntetycznym scenariuszu kilku kolejnych zapisów/aktywacji kopia osiągnęła ok. 27 MB; walidacja i odtwarzanie wymagają wtedy więcej czasu. Nie zmieniano formatu archiwów ani nie usuwano kopii, aby zmniejszyć ich rozmiar. Wydajność dużych archiwów na fizycznym telefonie pozostaje do sprawdzenia.

Końcowe wyniki regresji i CI są w raporcie PR.
