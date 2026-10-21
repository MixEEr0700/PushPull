# PushPull — import i przekazanie do Codexa

Data: 21.10.2026. Import zatwierdzonych przez użytkownika źródeł v0.3 Matrix — szlif 3, bez modyfikacji kodu/interfejsu.

## Źródła i struktura
Dostarczono siedem osobnych plików, nie archiwum ZIP. Nie wykonano rozpakowania ani kontroli CRC ZIP. Kontrola lokalnych plików: poprawne UTF-8, niepuste, bez NUL; JS przechodzi node --check, manifest parsuje się jako JSON, ikona jako XML. Wszystkie lokalne odwołania index.html, manifestu i listy cache mają odpowiadające zasoby. Nie znaleziono drugiego wariantu interfejsu ani zewnętrznych zależności/CDN. Przegląd źródeł nie wykazał tokenów, haseł ani prywatnych eksportów.

W katalogu głównym: index.html → style.css + app.js, manifest.webmanifest → icon.svg. app.js rejestruje sw.js; service worker cache'uje te zasoby. Brak bundlera, frameworka i zależności npm. Wykresy są generowane jako SVG. Uruchomienie deweloperskie: python3 -m http.server 8000 w katalogu repozytorium, potem http://localhost:8000. Nie jest to wdrożenie produkcyjne.

Istniejące AGENTS.md, PushPull_PLAN_PROJEKTU_v1.md i README.md zachowano. README dostarczone ze źródłami przeniesiono bez zmian treści do docs/SOURCE_README_v03_matrix_szlif_3.md, aby uniknąć kolizji. Główny README zawiera historyczny stan sprzed importu (brak kodu, 404 integracji); aktualny stan opisuje ten dokument. Przy odczycie przed importem integracja potwierdziła private=true, default_branch=main oraz permissions pull/push/admin=true.

## Dane
localStorage, klucz pushpull_skeleton_v1; obiekt version=1 zawiera exercises, sessions, entries, changes, nextType, activeId. Serie zapisane w entries.series. Eksport i import JSON już istnieją. Drafty serii żyją w pamięci Map do zapisu. Brak IndexedDB, Drive, wersji parametrów planu i snapshotów ćwiczeń w sesjach.

## Wykonana weryfikacja
- node --check app.js i sw.js: PASS.
- Parsowanie manifestu/SVG i sprawdzenie zasobów: PASS.
- Uruchomienie JS w Node VM z symulowanym DOM: PASS dla początkowego generowania HTML, zapisu/korekty bez duplikatu, skróconego/różnego podglądu serii, tonażu 1640 kg (100×10 + 80×8), zakończenia sesji i rotacji do PULL A, ponownego załadowania serializowanych danych.
- Próba testu Playwright: ZABLOKOWANA — brak binarnego Chromium. Nie wykonano testów rzeczywistego UI, Androida, autoheight, instalacji PWA, offline, aktualizacji cache, importu/eksportu w przeglądarce ani pełnej regresji.

## Znane ograniczenia z analizy kodu — bez napraw w tym imporcie
1. Błąd parsowania JSON lub version != 1 powoduje ciche fresh(); kolejny zapis może zastąpić poprzednie dane. Błędy/brak miejsca przy setItem nie mają obsługi. localStorage nie jest backupem; dane są przypisane do origin/przeglądarki.
2. Import waliduje tylko część struktury i zastępuje dane po potwierdzeniu, bez automatycznej kopii; brak walidacji relacji/ID/serii i transakcyjnego rollbacku.
3. Wspólne ex.notes dla notatek użytkownika i trenera. Historia sesji korzysta z bieżącego planu, nie jego wersji z dnia treningu.
4. ID są generowane z typu i pozycji. countSince rozbija PUSH-A-1 do PUSH A, ale porównuje z typem PUSH A; ten konkretny format jest spójny. Natomiast exampleDescriptions używa kluczy ze spacją (PUSH A-5), więc nie trafia w ID z myślnikami (PUSH-A-5).
5. getDraft chroni flagą custom różne serie istniejącego wpisu; serie skopiowane z poprzedniej sesji do nowej nie ustawiają tej flagi. Wymaga testu ochrony ręcznych poprawek.
6. Statystyki ciężaru/powtórzeń biorą pola główne, czyli pierwszą serię; tonaż sumuje wszystkie. Tempo progresji to zmiana tonażu procentowo względem poprzedniego zapisu, nie tempo w czasie. Nie dopowiadać innej metodologii.
7. Nawigacja miesięcy używa lokalnej daty i toISOString(); możliwe przesunięcie miesiąca w dodatniej strefie czasowej. Wymaga testu Europe/Warsaw.
8. Cache ma stałą nazwę pushpull-v2 i strategię cache-first; brak czyszczenia poprzednich cache oraz kontrolowanego procesu aktualizacji. Nie potwierdzono kompatybilności instalacji z ikoną tylko SVG. Ikona ma wcześniejszą niebieską kolorystykę — pozostawiona wiernie.
9. Dane planu są demonstracyjne; tempo i RIR nieuzupełnione. Back-off/drop są częściowo opisami; brak pełnego modelu dropsetów/superserii.

## Najbliższe zadania
Najpierw uruchomić ten import na telefonie i zbudować testy regresji akceptowanego UI oraz powyższych ryzyk. Następnie realizować plan: bezpieczna baza IndexedDB i migracja z kopią/odtwarzaniem, pełna walidacja JSON, stabilne ID i wersje planów/snapshoty sesji, oddzielne notatki, weryfikacja V2 z dokumentem trenera. Publikacja HTTPS/PWA po testach. Drive dopiero po stabilnym offline i backupach. Nie wdrożono tych zmian w imporcie.
