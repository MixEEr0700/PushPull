# Aplikacja Treningowa — aktualne przekazanie

Etap 5B, krok B: osobno zlecony mechanizm pełnych kopii nowego modelu. [Format/API i ograniczenia](BACKUP_STAGE_5B_B.md), [raport testów](STAGE_5B_B_TEST_REPORT.md). Implementacja tworzy i weryfikuje v3 oraz odtwarza odrębny stan w pamięci; odczytuje bezstratnie v1/v2. Brak integracji z aktywnym dziennikiem, migracji i kroków C–H. Poniższy akapit A opisuje stan jego zakończenia przed zleceniem B.

Etap 5B, krok A: właściciel osobno zlecił implementację niezależnych kontraktów. [Model i API](DATA_MODEL_STAGE_5B_A.md), [raport testów](STAGE_5B_A_TEST_REPORT.md). Moduł nie jest podłączony do aplikacji/PWA; brak migracji i aktywacji. Dalsze kroki B–H pozostają poza zakresem. Starsze wzmianki D8 o braku zgody na kod opisują stan przed tym zleceniem.

Etap 5A: [audyt V2](V2_PLAN_AUDIT_STAGE_5A.md) zakończono na podstawie DOCX (34/34), a 22.10.2026 odnotowano zatwierdzone decyzje właściciela D1–D9. [Projekt 34 pozycji](V2_NEXT_PLAN_DRAFT_STAGE_5A.md) oddziela oryginał trenera od 10 wyborów D2; otwarte tylko O1/O2/O3. Implementacja wymaga osobnego zlecenia D8; aktywacja wyłącznie przyszłą świadomą operacją D7. [Projekt modelu i kolejność PR A–H](MODEL_EXTENSION_STAGE_5B_PROPOSAL.md) nie są implementacją. Parametry aktywnego planu i dane pozostają bez zmian; [wyniki kontroli](STAGE_5A_TEST_REPORT.md).

Etap 4 zmienia nazwę użytkową bez zmiany tożsamości PWA i danych. Aktualny kierunek: [aneks planu](PROJECT_PLAN_ANNEX_STAGE_4.md), [architektura i model](TARGET_ARCHITECTURE_STAGE_4.md), [raport testów](STAGE_4_TEST_REPORT.md). Drive, nowy silnik planów i raport trenera są wyłącznie projektowane. Poniżej pozostaje historyczny zapis etapów 1–3; opisy dawnych braków nie oznaczają obecnego stanu.

# PushPull — import i przekazanie do Codexa

> Etap 3 przygotowuje testową paczkę PWA bez aktywacji hostingu. Hosting, koszty i prywatność: [PWA_TEST_DEPLOYMENT_STAGE_3.md](PWA_TEST_DEPLOYMENT_STAGE_3.md); telefon: [ANDROID_TEST_CHECKLIST.md](ANDROID_TEST_CHECKLIST.md); wykonane testy: [STAGE_3_TEST_REPORT.md](STAGE_3_TEST_REPORT.md). Testów fizycznego Androida jeszcze nie wykonano.

> Poniżej zachowano historyczny audyt importu. Aktualny etap 2 wprowadza IndexedDB; model, migrację i odzyskiwanie opisuje [INDEXEDDB_MIGRATION_STAGE_2.md](INDEXEDDB_MIGRATION_STAGE_2.md), a wykonane kontrole [STAGE_2_TEST_REPORT.md](STAGE_2_TEST_REPORT.md). Ograniczenia pierwotnego importu nie są automatycznie aktualnym stanem kodu.

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
