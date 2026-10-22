# PushPull — zatwierdzony kierunek po funkcjonalnym V2 (22.10.2026)

## Cel nadrzędny
Przygotować praktyczny mobilny dziennik treningowy, a nie stale rozbudowywać architekturę. Zachować zatwierdzony interfejs **PushPull v0.3 Matrix — szlif 3**, dotychczasową historię, identyfikatory serii i sesji, notatki, statystyki, snapshoty oraz kopie. Zmiany stopniowe, bez przebudowy gotowych funkcji.

## Stan wdrożenia
- PR #6: model domenowy; PR #7: kopia v3; PR #8: addytywna migracja; PR #9: funkcjonalny dziennik — scalone.
- PR #10, commit `60c1f65544a9644875dc65f9eaed1e4c059028c8`: pełny trening V2 w kodzie, oczekuje na CI/review/scalenie (stan w chwili sporządzenia dokumentu). Plan NIE był uruchamiany na danych właściciela ani publikowany.
- Parametry planu 34 kart oraz D1–D9 i O1–O3 są zatwierdzone; szczegóły w `docs/V2_FUNCTIONAL_JOURNAL.md` na gałęzi PR #10 i `docs/V2_NEXT_PLAN_DRAFT_STAGE_5A.md`. Cztery pozycje brzuch/łydki pozostają jawnie nieokreślone.
- Wymagane potwierdzenie powodzenia CI oraz osobna zgoda na publikację HTTPS i aktywację planu na danych użytkownika.

## Decyzja interfejsowa: superserie jako zwykłe ćwiczenia A i B
**Właściciel zatwierdził 22.10.2026**: superserię przedstawiamy jako dwa osobne ćwiczenia, np. `PULL-B-6A — Narciarz` i `PULL-B-6B — Szrugsy`. Każde korzysta ze zwykłego, istniejącego formularza zapisu i edycji wyników. Nie budujemy specjalnego wspólnego formularza superserii. W danej jednostce zachować czytelną kolejność A/B i prostą informację, że jest to para.

Dla tej pary: **2 rundy, każde ćwiczenie 8–10 powtórzeń, 15 s pomiędzy członami**; nie dopisywać nieokreślonej przerwy pomiędzy rundami ani nie wymuszać timera. Oba ćwiczenia zachowują niezależne tożsamości/ID, ciężary, powtórzenia, strony i historię, a zarazem informację o grupie i rundzie w modelu/snapshotach. Bez podwójnego liczenia tonażu i bez przypisywania starego wspólnego wyniku do obu nowych ćwiczeń.

W PR #10 dwa człony mają już oddzielne rekordy/wyniki, lecz przedstawiane są we wspólnej karcie i wymagają ponownego otwarcia formularza po pierwszym zapisie. **Zmiana dotyczy przede wszystkim prezentacji i prostoty obsługi; nie wolno usunąć istniejącej relacji superserii ani przepisywać historycznych danych.** Należy wykonać jako małą poprawkę funkcjonalną, gdy nie opóźnia pierwszego treningu na telefonie.

## Kierunek najbliższych prac (kolejność)
1. Zweryfikować CI PR #10, sprawdzić ewentualne blokery, scalić po zgodzie właściciela. Bez nowych audytów i zbędnych testów.
2. Udostępnić istniejący artefakt PWA przez wybrany bezpieczny HTTPS, po osobnej zgodzie na wdrożenie. Zachować prywatne repozytorium. Zainstalować aplikację na rzeczywistym Androidzie i przetestować krótki cykl: trening → zapis → zamknięcie/ponowne otwarcie → historia/statystyki → eksport/przywrócenie. Przed dotknięciem realnych danych pobrać i sprawdzić kopię poza przeglądarką. Plan V2 aktywować tylko na wyraźne polecenie.
3. Synchronizacja z indywidualnym Google Drive: wygodna autoryzacja, automatyczny zapis pełnych danych, bez wymogu logowania przy każdym treningu, praca offline i późniejsza synchronizacja, bezpieczne rozwiązywanie konfliktów (bez cichego nadpisania), odzyskanie po zmianie telefonu. To obowiązkowa funkcja docelowa, nie opcjonalny dodatek.
4. Uniwersalny **import kolejnych wersji planu jako danych**, bez przebudowy kodu aplikacji: właściciel przekazuje nowy dokument → wyjaśniamy tylko niejasności → przygotowujemy wersjonowany plik danych → aplikacja pokazuje różnice i świadomie aktywuje nowy plan. Stare sesje/snapshoty pozostają przy poprzednim planie. W PR #10 dane V2 są wydzielone do `model/v2-plan-data.mjs`, ale nadal dostarczane wraz z kodem; uniwersalnego importu planu NIE ma.
5. **Przed regularnym używaniem na telefonie** dodać automatyczny lokalny zapis i odzyskiwanie szkiców rozpoczętej sesji (w tym kg, powtórzenia, strony L/P, segmenty dropsetów i człony superserii). To wymaganie obowiązkowe, nie kosmetyczna poprawka po wystąpieniu utraty wyników. Zapis szkicu powinien działać offline, po każdej istotnej edycji, bez potrzeby klikania Zapisz. Po restarcie/ubiciu procesu/odświeżeniu aplikacja musi proponować wznowienie. Szkic oddzielić od zatwierdzonych wyników i statystyk; usuwać go dopiero po potwierdzeniu trwałego zapisu albo świadomym odrzuceniu. Weryfikować przypadek przerwania podczas edycji i odzyskanie bez utraty zatwierdzonych danych.

## Zatwierdzona zasada synchronizacji z Google Drive (22.10.2026)
- **Szkic niezapisanych pól** (kg, reps, strony, back-off, drop, osobne A/B) pozostaje lokalnym automatycznym szkicem odzyskiwania. Nie jest zatwierdzonym wynikiem, nie zasila statystyk i nie wymaga Internetu.
- **Każdy zatwierdzony wynik** musi najpierw zostać trwale zapisany lokalnie, a następnie wyzwala automatyczną synchronizację aktualnych danych z Google Drive, jeżeli jest aktywne połączenie i autoryzacja.
- **Zakończenie treningu** po lokalnym zapisie uruchamia dodatkową synchronizację pełnej aktualnej historii, statystyk i informacji o sesjach. Zamykanie aplikacji nie może być potrzebne do synchronizacji.
- **Offline / przerwana sieć / wygasła autoryzacja**: trening działa normalnie; zatwierdzone zmiany zachowują status oczekujących, są ponawiane po odzyskaniu połączenia i ponownym uruchomieniu aplikacji. Nie wolno pokazywać sukcesu, zanim Drive potwierdzi zapis.
- **Konflikty i niezawodność**: żadne ciche nadpisywanie nowszej historii starszą kopią; walidacja integralności, bezpieczne odtwarzanie na innym telefonie, brak duplikacji wyników i jawny status synchronizacji (zsynchronizowano / oczekuje / offline / błąd).
- **Zakres**: to zatwierdzony kontrakt przyszłej implementacji, NIE funkcja dostępna w PR #10/#11. Google Drive wymaga osobnej implementacji, konfiguracji OAuth i rzeczywistych testów; nie uruchamiać połączenia z kontem bez świadomej zgody.

## Decyzja właściciela — prostota zamiast nadmiernych zabezpieczeń (22.10.2026)
- To prywatny dziennik ciężarów i treningów, a nie system finansowy. Nie projektować bankowej infrastruktury, dodatkowych kont, własnego backendu ani logowania do samej aplikacji bez realnej potrzeby.
- Właściciel akceptuje publicznie dostępny adres PWA przez HTTPS. Publiczna dostępność plików aplikacji nie oznacza zgody na publiczną publikację jego historii treningów; wyniki pozostają lokalnie, a przyszłe kopie na jego własnym Google Drive.
- Ochrona ma być proporcjonalna: niezawodne szkice, lokalny zapis offline, kopie, ochrona przed przypadkowym nadpisaniem i uczciwy stan synchronizacji. Przy integracji Google wystarczą standardowe mechanizmy autoryzacji Google, bez autorskiego systemu użytkowników.
- Zachować sprawną instalację i wygodę obsługi na Androidzie jako najważniejszy cel. Publikacja hostingu i połączenie konta Google pozostają odrębnymi operacjami wykonywanymi świadomie.

## Kryteria i ograniczenia
- Proste codzienne działanie na telefonie ważniejsze niż dodatkowa infrastruktura i liczba testów.
- Odrębnie raportować: implementację, testy automatyczne, fizyczny telefon, realne dane i produkcyjne wdrożenie.
- Żadna operacja nie może usuwać historii, nadpisywać wcześniejszych wariantów ani zmieniać zatwierdzonego Matrix bez zgody.
- Kolejne plany nie powinny wymagać nowych PR-ów do samej zmiany serii/ćwiczeń, jeśli typy ćwiczeń są już obsługiwane; docelowo import pliku z walidacją i podglądem.
