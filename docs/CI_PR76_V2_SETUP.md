# PR #76 — granica zakończenia przygotowania testu V2

## Przyczyna

Attempt 2 runu `40180814021`, commit `a170f084cb268541bd605382844b77174e852a3a`,
zakończył się awarią etapu Chromium. Zgłoszony przypadek porównuje pełny stan
przed i po podglądzie aktywnego V2 oraz próbie ponownej aktywacji tego planu.

`V2Training.activate()` kończy także starą sesję fixture. Kliknięcie przycisku
nie czekało na kolejkę `actions`, `savedDrafts.flush()`, obsługę potwierdzenia
oraz trwały commit. Helper wracał, gdy `session-5` mogła być nadal aktywna.
Test zapisywał taki stan jako `before`. Nawigacja do planów czekała już za
operacją zakończenia: późniejszy odczyt widział `activeId: null` i `status: done`.
To uprawniony zapis przygotowania testu, nie zapis podglądu tylko do odczytu.

## Odtworzenie i poprawka

W osobnym profilu Chromium opóźniono SHA kończącej się sesji o 700 ms;
IndexedDB, walidacja, transakcja i CAS pozostały rzeczywiste. Nie modyfikowano
kodu aplikacji. Oryginalny przypadek na `a170f08` zawiódł **3/3** razy dokładnie
przy porównaniu w dawnym wierszu 107: `session-5` → `null`, `active` → `done`.
Nowy test helpera także zawiódł przed poprawką, wykrywając aktywną sesję.

Helper czeka teraz na widoczny przycisk rozpoczęcia następnego treningu.
Aplikacja pokazuje go po istniejącym `await persist()` i ponownym renderze;
nie jest to oczekiwanie przez stały sleep. Jest to ta sama poprawka jednej
linii, która już istnieje w PR #78 — ponownie wykorzystano jej hunk.

Po poprawce: oryginalny przypadek z opóźnieniem **3/3 PASS**, nowy test **PASS**.
Nowy test wymaga `activeId: null`, zachowania całej listy sesji z jedyną
oczekiwaną zmianą statusu kończonej sesji, wszystkich wyników oraz zmian
techniki. Oryginalne pełne porównania stanu przed/po podglądzie, odrzuceniu
ponownej aktywacji i reloadzie pozostają bez zmian. Nie ignorujemy pola
`activeId`, nie aktualizujemy oczekiwanego snapshotu po badanej operacji.

## Zakres i weryfikacja końcowa

Zmiana dotyczy wyłącznie testów i niniejszej dokumentacji, obok wcześniejszej
konfiguracji workflow i AGENTS z PR #76. Runtime, schemat IndexedDB, trwałość,
CAS, Matrix, plany, historia, szkice, Drive i backupy/odtwarzanie nie zmieniają się.

Polecenia pełnej regresji pozostają identyczne. Obejmują Node, Chromium,
IndexedDB/CAS, offline i upgrade PWA, historię, wyniki, plany, szkice,
backupy, odtwarzanie oraz build allowlisty produkcyjnej. Wyniki finalnego
commitu, lokalne i Actions, są podane w opisie PR #76.

Repozytorium jest publiczne. Nie ogranicza się zakresu testów z powodów
finansowych. Workflow nadal używa standardowego `ubuntu-latest`; nie korzysta
z płatnych larger runners i nie zmienia Billing. Zmiany triggerów/cache
nie wycinają żadnego kroku regresji.

API potwierdziło attempt 2 i nieudany krok. Archiwum logów tego starego
przebiegu jest niedostępne przez proxy środowiska (Forbidden na hoście logów).
Podstawą diagnozy są kod, identyczny komunikat odtworzony lokalnie i test
z kontrolowanym opóźnieniem, nie domniemany odczyt niedostępnego archiwum.
