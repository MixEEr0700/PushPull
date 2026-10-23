# Issue #40 — pełne przywracanie bazy

Baza: `main` po PR #39 (`8d327a7`). Problem zgłoszony na telefonie nie oznaczał utraty planu w kopii: poprzedni przycisk Drive pobierał plik, nie zastępował bazy drugiego urządzenia.

## Cztery operacje w Dane → Kopie zapasowe

1. **Zapisz kopię na Google Drive** — ręcznie tworzy osobny plik, odczytuje go ponownie i sprawdza integralność. Status podaje czas, liczbę sesji, wyników i kompletnych wersji planów. Nie usuwa wcześniejszych plików.
2. **Przywróć z Google Drive** — lista zachowanych kopii → wybór → podgląd → świadome potwierdzenie → rzeczywiste zastąpienie lokalnej bazy. Lista może pokazać starsze kopie; data zapisu nie jest dowodem pełniejszej historii. Samo połączenie Google, lista i podgląd niczego nie przywracają.
3. **Pobierz kopię JSON** — eksport pliku, bez zmiany bazy.
4. **Przywróć z pliku JSON** — wybór pliku i taki sam podgląd/potwierdzenie/import jak dla Drive.

Podgląd porównuje „Na tym urządzeniu” i „W wybranej kopii”: datę kopii (dla starszego formatu Drive: znany czas zapisu pliku; bez dostępnej daty: „nieustalona”), nazwy zapisanych wersji, aktywny plan, liczbę zakończonych/rozpoczętych sesji, wyników, snapshotów i aktywacji oraz ostatnią datę treningu. Porównuje pełną zawartość danych i liczy brakujące/nowe/zmienione sesje oraz wyniki o tych samych ID. Nie łączy historii. Nie dopisuje fikcyjnego planu V1 z samego szkieletu.

## Integralność i odzyskiwanie

- Format JSON v3, checksumy i adapter starszych v1/v2 pozostają bez zmian. Podgląd używa istniejącej pełnej walidacji source-backed v3, nie spłaszcza danych do samych wyników. Zachowuje plany, aktywną wersję, notatki, instrukcje, snapshoty, aktywacje i wszystkie zapisane struktury serii.
- Pełną weryfikację podglądu pliku i zawartości kopii Drive wykonuje worker wykorzystujący istniejący, precachowany moduł. Duża kopia nie blokuje głównego wątku podczas sprawdzania. Końcowy importer ponownie waliduje oryginalny tekst; dane zapisuje dotychczasowym mechanizmem IndexedDB.
- Podgląd jest związany z rewizją bazy i oryginalnym localStorage. Zmiana lokalna podczas odczytu lub po podglądzie wymaga ponownego podglądu. Transakcja nadal sprawdza rewizję/model i chroni przed nowszym zapisem innej karty, także bez BroadcastChannel.
- Kopia sprzed przywrócenia i nowe dane zapisują się atomowo. W transakcji sprawdzane są rekordy, ID i relacje; dopiero po `oncomplete` dodatkowy niezależny odczyt potwierdza dane/katalog/model. Status sukcesu pojawia się po weryfikacji.
- Błąd przed zakończeniem transakcji nie zastępuje bazy. Jeśli transakcja się zakończy, lecz późniejszy odczyt nie może zostać potwierdzony, aplikacja nie zgłasza sukcesu i blokuje pracę do odświeżenia/sprawdzenia; kopia sprzed operacji pozostaje dostępna. Nie cofa wtedy automatycznie danych, co mogłoby nadpisać nowszy zapis innej karty.
- W razie potrzeby w **Zachowane kopie danych** wybierz kopię sprzed przywrócenia, pobierz ją i użyj **Przywróć z pliku JSON**. Zachowane kopie obu urządzeń pozostają w lokalnym archiwum; mogą powiększać następne eksporty.

**Szkice są lokalne i nie należą do kopii JSON/Drive.** Przed zastąpieniem jest ostrzeżenie. Import nie kasuje szkiców ani ich buforów. Po przywróceniu szkic starego urządzenia/sesji może nie pasować do nowej bazy: w Trening → Niedokończone wpisy można go pobrać do odzyskania; nie jest automatycznie stosowany do innych wyników. Odrzucenie nadal wymaga potwierdzenia.

## Weryfikacja

Syntetyczne, niezależne profile A (V2 + TEST 3×5) i B (tylko V2) korzystają z symulowanego Google Drive. Test sprawdza realne przywrócenie A na B, pełną równość danych i katalogu, snapshotów/aktywacji/planów/statystyk, preimage B, anulowanie, uszkodzenie kopii, zachowanie lokalnego szkicu i restart offline. Dodatkowo: konflikt nowszej rewizji innej karty, zmiana starego localStorage, odmowa sukcesu po awarii odczytu po commicie oraz aktualizacja istniejącej PWA i przywrócenie kopii >16 MiB offline; licznik animacji potwierdza responsywność podczas podglądu. Istniejące testy importu przeszły na świadome zatwierdzenie podglądu — bez obejścia nowego interfejsu.

Wyniki pełnej regresji Node/Chromium i CI są w raporcie PR. Nie testowano rzeczywistego Google ani fizycznego Androida. Duże kopie nadal potrzebują czasu/pamięci i wystarczającego miejsca na nową bazę oraz preimage. Bez migracji schematu, automatycznej synchronizacji, hostingu, nowych uprawnień OAuth i zmian danych właściciela. Matrix/CSS/nawigacja i poprzednie funkcje treningowe pozostają zachowane.
