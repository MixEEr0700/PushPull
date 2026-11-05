# Powtarzanie wyników — #159

Przy kończeniu sesji aplikacja najpierw rozstrzyga szkice istniejącą ścieżką, następnie utrwala brakujące powtarzalne wyniki i dopiero po potwierdzonych zapisach zamyka sesję. Zatwierdzone wpisy aktualnej sesji mają pierwszeństwo. Odrzucenie szkicu wyklucza jego ćwiczenie z powtórzenia w tej operacji.

Poprzednik musi należeć do zakończonej wcześniejszej sesji oraz identycznego, potwierdzonego kontekstu snapshotu: wersji planu, pozycji, wariantu, parametrów i układu serii. Wartości oraz konwencja kopiowane są bez przeliczania; nowe są ID wyniku, wierszy i segmentów. Nie używa się prefill do przekształcania historycznych L/P. Wyniki przechodzą normalne recordEntry, walidację, CAS, readback oraz strict complete. Statystyki i indeks ostatnich wyników otrzymują zwykłe nowe rekordy. Ręczne Oznacz zmianę pozostaje bez zmian.

Pominięto jest odwracalnym oznaczeniem w metadanych bieżącej sesji (skippedExerciseIds); zapis wykorzystuje istniejący pełny commit i kontrolę rewizji. Nie można nim zastąpić zapisanego wyniku ani nierozstrzygniętego szkicu. Metadane sesji pozostają częścią istniejącego modelu i kopii PPC1; nie powstaje nowy format backupu.

Po błędzie wyników sesja pozostaje aktywna. Już potwierdzone rekordy pozostają i są pomijane podczas ponowienia. Szkice usuwa wyłącznie dotychczasowy mechanizm po zakończeniu. Operacja nie obiecuje jednej transakcji obejmującej wszystkie wyniki; kompletność końca sesji jest potwierdzana dopiero po wszystkich zapisach.

## Testy celowane

- Chromium: zapis konwencji, kolejny trening bez edycji, dziedziczenie wyniku i konwencji, ręczny wynik bez nadpisania, Pominięto po restarcie: PASS.
- Chromium: historyczne L/P, asymetria i dropset, nowe ID, zmiana wariantu bez kopiowania, błąd zapisu i ponowienie po restarcie: PASS.
- Chromium: awaria drugiego automatycznego zapisu, częściowo utrwalone wyniki, restart i brak duplikatów: PASS.
- Istniejąca regresja finish_pairs: osiem przypadków PASS (siedem bez zmian, jeden ponowiony po zachowaniu dotychczasowego tekstu toastu).
- Node: cztery testy konwencji i tonażu PASS. Składnia i kontrola hashy service workera PASS.

## Ograniczenia

Bez wiarygodnego snapshotu porównywalności nie tworzymy automatycznego rekordu (dotyczy również niepowiązanych dawnych danych). Brak poprzednika jest sygnalizowany przy zakończeniu, bez fikcyjnych wyników. Oznaczenie Pominięto i zakończenie wymagają wczytania historii; duże archiwa nie są ładowane do porównywania. Nie wykonano testu na fizycznym Pixelu 9, prywatnych danych ani rzeczywistym Google Drive. Pełne CI w checks PR.
