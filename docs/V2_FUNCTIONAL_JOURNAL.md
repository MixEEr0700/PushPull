# Dziennik V2 — działający przepływ

Aktualizacja Issue #29 (23.10.2026), na `main` po PR #24 (`3c51bc9`): poprawka istniejącego formularza, bez zmiany modelu wyników, danych planu, schematu IndexedDB, statystyk ani Matrix. Import V3+ i ręczne kopie Drive pozostają. Dalszy wspólny ekran planów/statystyki tygodniowe to osobne Issue #30.

- **Ciężar (kg)** i powtórzenia uzupełniają główne segmenty obu stron. Edycja połączonej serii działa lustrzanie w obu kierunkach tylko w tej serii; dodatkowe segmenty dropsetu mają własne wartości i ID. Dodanie/usunięcie segmentu połączonej pary obejmuje obie strony.
- **Razem L/P → Edytuj osobno** rozłącza jedną serię. Powrót **Połącz L → P** przy rozbieżnościach wymaga potwierdzenia zastąpienia prawej strony; inne serie i ich ID pozostają. Szybki globalny wpis również wymaga potwierdzenia zastąpienia ręcznych/osobnych wartości. Dotychczasowe przyciski świadomego kopiowania pozostają.
- Historyczne różniące się L/P oraz stare szkice startują osobno, bez nadpisania. `sidePairs` to wyłącznie stan edytora w istniejącym lokalnym szkicu (`value`), nie nowy rekord wyniku ani snapshot. Odtwarza również świadome rozłączenie równych wartości. Starsze szkice bez tego pola są odczytywane na podstawie stabilnych powiązań serii i wartości; niejednoznaczne pary pozostają osobne. Zapisane wyniki nadal zawierają niezależne strony/segmenty; tonaż liczy dotychczasowy `flatten`, bez dodatkowego mnożnika.
- Opcjonalne **Rozdziel L/P i skopiuj wartości** wymaga świadomego potwierdzenia. Zachowuje obecne wartości i ID pierwszej strony, tworząc osobne ID drugiej; nie przelicza kg i nie zmienia starych wyników przy otwarciu.
- Dla już aktywnego V2 podgląd pokazuje **Podgląd aktywnego V2 / V2 jest aktywny**, bez ponownej aktywacji. Handler i funkcja aktywacji mają ochronę przed powtórzeniem: brak commitu, nowej kopii, zmiany rotacji i dopisania `activations`. Przy aktywnym V3 nie pokazujemy komunikatu o aktywnym V2.

Testy i wyniki lokalne/GitHub Actions są w PR Issue #29: rzeczywiste formularze, korekta historii, tryb osobny po restarcie, opcjonalny drop/back-off, stara asymetryczna instalacja PWA i pełna regresja. Testy używają syntetycznych danych. Fizyczny Android i prawdziwe konto Google pozostają niewykonane. Poniżej zachowano wcześniejszy opis wdrożenia, z aktualnymi zasadami formularza.


Podstawa: main po PR #9 (`71558b6`), projekt 34 pozycji i D1–D9.
Właściciel rozstrzygnął O1–O3 w zleceniu „Dokończenie działającej aplikacji treningowej V2”, 22.10.2026. Historyczny audyt i projekt pozostają zapisem wcześniejszych ustaleń; poniższe decyzje zastępują ich nieaktualny status O1–O3.

## Włączenie przez użytkownika

1. Dane → **Podgląd zatwierdzonego V2**. Podgląd nie zapisuje ani nie aktywuje planu.
2. **Aktywuj V2 dla przyszłych treningów** → osobne potwierdzenie. Pobierana jest kopia dotychczasowych danych; istniejący mechanizm kroku C zabezpiecza przejście do modelu. Jeśli dziennik był już włączony, pobierana jest pełna kopia v3.
3. Rozpoczęte sesje zachowują swój plan. Zakończ bieżącą sesję, wybierz jednostkę i rozpocznij następną, aby użyć V2.
4. Rozwiń kartę → Zapisz wynik. **Ciężar (kg)** i powtórzenia wypełniają główne segmenty obu stron (gdy są L/P). Ołówek rozwija indywidualne cele i wyniki. Szybki wpis po ręcznej korekcie wymaga potwierdzenia.
5. Jednostronne: szybki wpis obejmuje obie strony. Domyślnie równe L/P są połączone dla konkretnej serii; **Edytuj osobno** pozwala zapisać różne wartości, a istniejące asymetrie pozostają rozłączone. Kopiowanie L → P/P → L jest osobną świadomą operacją. Dropsety mają osobne pola segmentów i przyciski +/−. Nie narzucamy liczby segmentów.
6. Narciarz i szrugsy: dwie rundy, dwa osobne formularze/zapisy w jednej karcie. Po zapisaniu pierwszego ćwiczenia ponownie otwórz „Zapisz wynik”, aby zapisać drugie. Robocze wartości drugiego formularza pozostają w pamięci do zapisu. Instrukcja: 15 s między ćwiczeniami; brak timera i wymyślonej przerwy po rundzie.
7. Zakończ trening. Kalendarz → Otwórz → karta → Zapisz wynik pozwala poprawić serie bez nowej sesji. Eksport JSON zapisuje pełną kopię v3, odtwarzaną istniejącym importem.

## Zatwierdzone parametry

- PUSH-A-4: nowy chest press siedząc, chwyt neutralny, wysokie siedzisko, wypychanie uchwytów do przodu; 2×8–10, RIR 0, tempo 3 1 1 1. Nowe ID `PUSH-A-4-CHEST-PRESS`; dipy zachowują `PUSH-A-4` i wyłącznie swoje wyniki.
- PULL-A-1: leżąc jednonóż, 3×8–10 na nogę, RIR 0, tempo 2 1 1 1.
- PUSH-B-1: siedząc obunóż, 3×10–12 łącznie, RIR 0, tempo 2 1 1 1.
- PULL-B-3: hantel, klatka i brzuch podparte 30–45°, do biodra; 2×8–10 na rękę, RIR 0, tempo 2 1 1 1.
- PULL-B-5: górna maszyna, dolny chwyt; 2×8–10, RIR 0, tempo 2 0 1 0.
- Pozostałe cele pochodzą z zatwierdzonego projektu. Pięć back-offów to dodatkowa trzecia seria z własnym zakresem, bez procentu redukcji. PUSH-A-5 i PULL-B-7 mają drop w każdej z trzech serii. Para PULL-B-6: każde ćwiczenie 2×8–10, 15 s między członami.
- Cztery pozycje Brzuch/Łydka nie mają przypisanych celów; edytor umożliwia zapis rzeczywiście wykonanych serii bez dopisywania zaleceń.
- Hantle: jeden hantel; maszyny/wyciągi: wskazanie urządzenia. Gdy sprzęt nie wynika ze źródła, konwencja pozostaje nieokreślona i można ją świadomie wybrać przy zapisie. Żadnych konwersji dawnych kg.

## Dane, notatki i obliczenia

`model/v2-plan-data.mjs` zawiera zatwierdzone parametry; `v2-plan.mjs` buduje wersję `v2-owner-2026-10-22`. Aktywacja jest jawna, zapisywana transakcyjnie razem z modelem. Nie podmieniamy definicji pod istniejącym ID wersji. Każda nowa sesja ma niezmienny snapshot. 34 karty odpowiadają 35 pozycjom modelu: narciarz i szrugsy mają odrębne ID i powiązanie grupy.

Nowy wynik `entry.performance` (version 2) zawiera konwencję obciążenia i `rows`: stabilne ID, setId, side, groupId, round oraz segmenty z własnymi ID, kg i reps. `entry.series` jest zgodną reprezentacją wszystkich wykonanych segmentów dla dotychczasowych statystyk. Przy zapisie walidujemy jej dokładną zgodność z pełnym wynikiem, relacje, strony, rundy, liczby i unikalność ID. Nie można zapisać tylko spłaszczonego wyniku V2. Wyniki struktur są projektowane do istniejących resultRecords/resultReferences kopii v3; oryginalna reprezentacja również pozostaje w pełnej kopii.

Tonaż nowych wyników = suma **każdego faktycznie zapisanego segmentu każdej strony raz**, kg × reps. Bez mnożnika za hantle, wykonanie obunóż lub jednostronność. Grupa ma dwa oddzielne wpisy/statystyki, bez dodatkowego sumowanego wyniku rodzica. Ciężar i powtórzenia w dotychczasowych kafelkach nadal oznaczają pierwszy zapisany segment; tempo progresji pozostaje procentową zmianą tonażu względem poprzedniego zapisu. Dawne obliczenia nie zmieniły się. Statystyki oddzielają kontekst wariantu, a dla nowych wyników także konwencję obciążenia ostatniego zapisu; historia zachowuje wszystkie konteksty z etykietami. Nie ma automatycznego przeliczania ani rozpoznawania nowych maszyn; zmiana sprzętu wymagająca nowego wariantu/planu musi dostać odrębną definicję, nie tylko znacznik techniki.

Instrukcje źródłowe są tylko do odczytu: etykiety C1 (trener), C2/U (historyczne uwagi, autor nieustalony) i D/O (właściciel) pozostają rozróżnione. Cytaty C2 nie zawierają liczbowych historycznych wyników. Własne notatki są oddzielnymi UserNote (`origin:user`). Dawne wspólne notatki pozostają nienaruszone i widoczne osobno; nie przypisujemy im autora. Znaczniki techniki zachowują dotychczasowy zapis.

Nie zmieniono schematu ani wersji IndexedDB, storage.js, indexeddb.js, CSS, ikon, manifestu/tożsamości PWA ani oryginalnego localStorage. Nowe ćwiczenia mają w dokumencie kompatybilności znacznik `journalOnly`, aby nie pojawiały się w dawnych sesjach. Zapis korzysta z istniejącego CAS i transakcji źródło+model; sukces wyświetlamy po ich zakończeniu. Po błędzie draft pozostaje dostępny do poprawki/powtórzenia. Aktualizacja po PR #10: robocze formularze mają [trwałe szkice i odzyskiwanie](WORKOUT_DRAFT_RECOVERY.md), a para jest prezentowana w osobnych kartach A/B.

## Weryfikacja i telefon

Wyniki końcowej regresji i GitHub Actions podano w PR. Testy `test_v2_training.py` wykonują rzeczywiste formularze: podgląd/anulowanie/aktywacja, ochrona starej sesji, back-off, ponowne otwarcie, korekta, notatki, tonaż, segmenty dowolnej długości, L/P i kopiowanie, obie rundy pary, pełne odtworzenie v3 w pustym profilu, niepełny formularz i quota/ponowienie. `test_pwa.py` dodatkowo sprawdza zapis V2 po aktualizacji workera i ponownym otwarciu offline. Wcześniejsza regresja obejmuje zachowanie historii, multi-tab, import, rollback i 12 porównań pikselowych Matrix.

Nie testowano fizycznego Androida, klawiatury na telefonie, instalacji WebAPK ani zachowania przy ubijaniu procesu przez Androida. Nie wdrożono hostingu ani synchronizacji. Do pierwszego treningu na telefonie pozostają: zatwierdzenie/scalenie PR, udostępnienie istniejącej paczki przez wybrany HTTPS, instalacja i krótki test na fizycznym urządzeniu, następnie świadoma aktywacja V2 z kopią. Instrukcja: [ANDROID_TEST_CHECKLIST.md](ANDROID_TEST_CHECKLIST.md). Kopia poza telefonem nadal jest konieczna; czyszczenie danych przeglądarki/originu usuwa lokalną bazę.
