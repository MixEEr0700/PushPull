# Przypomnienie Google Drive — #156

Przypomnienie wymaga aktywnych autokopii, oczekującej kolejki PPC1 i faktycznie nieudanej próby tej kolejki. Znacznik błędu jest utrwalany w istniejących metadanych Drive; sukces readback usuwa go razem z obsłużoną kolejką. Sam brak tokenu nie oznacza nieaktualnej kopii. Nie zmieniono protokołu punktów, OAuth ani walidacji kopii.

Dialog występuje tylko w widocznej aplikacji, poza aktywną sesją i edytorem wyników. Zapis czasu wyświetlenia w localStorage ogranicza go do raz na 24h po restarcie; Web Locks koordynuje karty, jeśli przeglądarka go obsługuje. Licznik jest wyłącznie metadaną UI, klasyfikowaną jako pomijaną przez capture PPC1; nie zmienia formatu kopii. Niedostępny zapis licznika blokuje pokazanie dialogu.

Kliknięcie bezpośrednio wywołuje dotychczasowe drive.connect(); gdy połączenie jest aktywne, wywołuje retryCanonical bez logowania i ma etykietę Ponów kopię. Anulowanie/zablokowanie logowania pozostawia komunikat i przycisk ponowienia. Weryfikacja kopii pozostaje zadaniem istniejącego transportu. Nie ma push, nowego timera ani odpytywania w tle.

## Weryfikacja syntetyczna

- Node: 9 unikalnych przypadków w drive-reminder.test.mjs i drive-incremental.test.mjs — PASS (w tym istniejący upload/readback).
- Chromium: 2 przypadki komponentu: kliknięcie z aktywacją użytkownika, anulowanie, Ponów kopię, Później, zegar 24h, restart, warunki bezpiecznego widoku, aktualna/wyłączona kopia. PASS.
- Chromium: 2 produkcyjne ścieżki z symulowanym Google API: 401 po zakończeniu sesji → dialog → istniejący OAuth → potwierdzona kopia oraz offline/restart/reconnect → potwierdzona kopia. PASS.
- Szerokości 360/390/412 px, kontrola składni, service worker/hashy: PASS.

## Ograniczenia

Nie testowano rzeczywistego konta Google ani fizycznego Pixela 9. Odbiór wymaga sprawdzenia okna wyboru konta w zainstalowanej PWA, blokady popupu, offline i limitu dobowego. Przy braku Web Locks koordynacja między jednocześnie aktywnymi kartami ma ograniczenia; limit jest trwały w obrębie profilu. Nie próbujemy wykrywać zmian niewprowadzonych do istniejącej kolejki PPC1. Pełny wynik CI jest w checks PR.
