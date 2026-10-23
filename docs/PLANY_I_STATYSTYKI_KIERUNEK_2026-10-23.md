# PushPull — zatwierdzony kierunek: plany i statystyki (23.10.2026)

**Status: zatwierdzona decyzja właściciela, uzupełnienie nadrzędnego `PushPull_PLAN_PROJEKTU_v1.md`.** W razie rozbieżności chronić niezmienione reguły specyfikacji głównej: Matrix v0.3 szlif 3, offline-first, nienaruszalność historii, wersji sesji, szkiców, stabilnych ID i danych. Szczegóły wdrażania: [Issue #30](https://github.com/MixEEr0700/PushPull/issues/30).

## Cel
Jeden stały dziennik z wieloma wersjami planów. Każdy nowy plan jest **danymi** dostarczonymi jako zatwierdzony plik, a nie okazją do przebudowy kodu czy interfejsu. Zmiana planu nigdy nie przenosi ani nie nadpisuje historii.

## Proces przygotowania i wdrażania planu
1. Właściciel przekazuje źródłowy plan (DOCX, PDF, tekst). ChatGPT analizuje wszystkie jednostki, ćwiczenia, warianty, kolejność, liczby serii, rep range, RIR, tempo, back-offy, dropsety, strony L/P, pary A/B, konwencje kg oraz instrukcje. Nie zgaduje braków.
2. ChatGPT dostarcza **czytelny szkic do korekt** i spis niejednoznaczności, w tym decyzję, czy serie łączone są oddzielnymi kartami i jak liczyć tonaz oraz historię. Uzgodnienia przed jakimkolwiek wdrożeniem.
3. Właściciel zatwierdza szkic; powstaje wersjonowany plik danych (np. `PushPull_Plan_V3.json`) zgodny z walidowanym formatem importu. Import nowych typów ćwiczeń niewspieranych przez model może nadal wymagać osobnego rozwoju kodu.
4. W aplikacji **Plany treningowe → Importuj nowy plan**: walidacja schematu i integralności, pokazanie dodanych/zmienionych/usuniętych pozycji i odrębna, świadoma **Aktywacja dla przyszłych treningów**.
5. Rozpoczęta sesja i historia pozostają pod swoimi snapshotami; stare plany można przeglądać. Nigdy nie przenosić wyników przez samą zgodność nazw ćwiczeń.

## Jeden ekran „Plany treningowe”
- Lista z oznaczeniem **Aktualny plan**, wersja/nazwa/data aktywacji; **Poprzednie plany**, także sesje historycznego szkieletu (z opisem pochodzenia / „nieprzypisane”, jeżeli identyfikacja jest niemożliwa).
- Podgląd planu: jednostki, kolejność, ćwiczenia, warianty, serie, zakresy powtórzeń, tempo, RIR, back-off/drop, strony i instrukcje.
- **Dodaj / importuj plan**, podgląd zmian, **Aktywuj dla przyszłych sesji**. Sam import nie aktywuje.
- Zastąpić osobny stały interfejs „Podgląd V2”/„Aktywuj V2” wspólną listą. Aktywny V2 nadal jest zwykłą pozycją listy, bez ponownej aktywacji ani nowych wpisów aktywacji. Nie zmieniać przy tej kosmetyce aktywnego V2 właściciela.

## Statystyki ogólne — tygodniowe, per plan
- Oddzielny moduł **Statystyki ogólne** z selektorem wersji planu; domyślnie aktywny plan, archiwalne dostępne z wyboru. Bez niejawnego mieszania V2 z V3.
- Tygodnie ISO **poniedziałek–niedziela w strefie Europe/Warsaw**, według daty sesji, **bez sztywnego grafiku ani założenia 4 treningów/tydzień**.
- Dla danego planu: liczba zakończonych treningów; suma realnego tonażu kg × reps z zapisanych serii i prawidłową konwencją jednostronności; liczba wykonanych serii; suma powtórzeń; wartości i sensowne zmiany tygodniowe, wykres i tabela. Wyraźnie oznaczać częściowy tydzień, zero i brak danych. Nie podwajać dropsetów, par A/B ani rezultatów przy agregacji.
- **Wzrost tonażu nie jest sam w sobie dowodem progresu siły**; prezentować objętość razem z frekwencją/liczbą serii.
- Statystyki pojedynczych ćwiczeń pozostają: tonaż, ciężar, powtórzenia, tempo progresji, wykresy, notatki techniczne i historię zmian. Tożsamość ćwiczenia i cała historia nie są zerowane; wyniki można **filtrować** do konkretnego planu bez duplikowania rekordów. Nie łączyć nieporównywalnych wariantów po samej nazwie.

## Ochrona danych i kolejność
- Nigdy nie kasować ani nie migrować historycznych sesji, wyników, szkiców, ID, snapshotów czy wersji planu bez walidacji i zabezpieczenia.
- Zachować zatwierdzony Matrix i działający lokalny zapis, eksport/import, ręczne kopie Drive. Zmiany na telefonie tylko po testach i z potwierdzeniem.
- **Najpierw** zweryfikować i rozwiązać konflikt istniejącego PR #24 (import planów V3+), następnie ukończyć poprawkę formularzy L/P z Issue #29, **potem** wdrożyć jeden ekran Plany treningowe i statystyki tygodniowe Issue #30. Bez implementowania importu od zera ani dublowania prac.
- Każdy PR raportuje: co zmieniono, co zachowano, testy i wynik, ograniczenia. Weryfikacja na fizycznym Androidzie przed ogłoszeniem funkcji jako potwierdzonej produkcyjnie.

## Zatwierdzone doprecyzowanie: powrót do wcześniejszego planu i ciągłość statystyk (23.10.2026)

**Ta decyzja zastępuje wcześniejszą sugestię rozpoczynania statystyk „od zera” przy ponownej aktywacji planu.**

- Ponowna aktywacja **dokładnie tej samej wersji planu** zachowuje i kontynuuje jego historię oraz statystyki. V2 → V3 → V2 oznacza: wspólne dane statystyczne V2 z pierwszego i drugiego okresu używania. Nie usuwać, nie resetować ani nie przenosić wyników.
- Przy przełączeniu planu **nowy okres używania** oraz nowy cykl rotacji zaczynający się od pierwszej jednostki, ale **bez resetu statystyk**. Okresy aktywacji są osobno wymienione w historii z wiarygodnymi datami.
- Na wykresie/statystykach V2 zachować rzeczywistą oś czasu z przerwą (np. sześć miesięcy treningów V3). Nie zagęszczać jej i nie łączyć przez brakujące tygodnie w sposób sugerujący ciągłe treningi V2. Brakujące tygodnie pozostają bez ćwiczeń V2; nie interpolować wyników.
- Wracający użytkownik widzi ostatnie zachowane wyniki danego ćwiczenia w kompatybilnym kontekście; może rozpocząć niższym ciężarem, a taka sesja trafia do dalszej wspólnej historii V2. Nie szukać rekordu ani nie podmieniać ostatniej rzeczywistej obserwacji najlepszą.
- Przełącznik pokazuje wyłącznie **kompletne, zachowane, walidowalne wersje**, nie wymagając ponownego importu. Nie przedstawiać niepełnego historycznego szkieletu jako pełnej V1. Jeśli brak innych aktywowalnych planów, uczciwie wyjaśnić przyczynę.
- Potwierdzenie zmiany: „Rozpoczniesz nowy okres używania planu i wrócisz do pierwszej jednostki. Poprzednie wyniki i statystyki tej wersji pozostają dostępne i będą kontynuowane”.
- Nie zmieniać wyglądu Matrix, nawigacji, historii, snapshotów, szkiców, konwencji kg ani ręcznych kopii. Pełne kryteria odbioru i status w [Issue #34](https://github.com/MixEEr0700/PushPull/issues/34).
