# Google Drive — kopie i synchronizacja zatwierdzonych danych

Aktualny tryb Drive: [ręczne kopie, decyzja Issue #26](GOOGLE_DRIVE_MANUAL_BACKUP_ISSUE_26.md). Opisy automatycznej synchronizacji poniżej są historyczne.


Implementacja Issue #16, oparta na main po PR #18. Nie podłączono konta właściciela, nie utworzono projektu OAuth, nie aktywowano V2 ani ręcznego wdrożenia.

Aktualizacja: [hotfix konfliktów Issue #23](GOOGLE_DRIVE_HOTFIX_ISSUE_23.md) opisuje trwały wybór lokalnej wersji, zachowanie oczekującego uploadu i potwierdzenie przez identyfikator pliku. Poniższy opis PR #19 pozostaje zapisem pierwotnej implementacji.

## Co działa w implementacji

- Dotychczasowy zapis IndexedDB, szkice, JSON v1/v2/v3, formularze, 6A/6B, historia, statystyki, ID i snapshoty pozostają. CSS i tożsamość PWA bez zmian. Kontrolki Google są w istniejącej zakładce Dane; po konfiguracji status pojawia się również nad treningiem.
- Każdy potwierdzony commit (wynik, korekta, notatki, rozpoczęcie/zakończenie, import) uruchamia nieblokujące sprawdzenie kolejki. Sieć/OAuth nigdy nie są częścią transakcji wyniku ani warunkiem jej sukcesu.
- Trwała `state.revision` w istniejącej bazie jest znacznikiem oczekujących zmian. Nie ma przerwy między zatwierdzeniem wyniku a utrwaleniem tego znacznika. Nie tworzymy nowej bazy ani schematu IndexedDB. Szkice mają osobne rekordy meta, nie zmieniają rewizji i nie wchodzą do kopii Drive.
- `drive-sync-v1` w istniejącym magazynie meta przechowuje konfigurację, osobne kolejki kont, bazowe wersje, potwierdzoną rewizję, ostatni sukces, termin ponowienia oraz dokładny upload oczekujący. Aktualizacja używa porównania tokena i potwierdzonego zakończenia transakcji. Token porównania jest losowym ID lokalnym, **nie tokenem OAuth**. Konfiguracja i kolejki nie wchodzą do treningowych eksportów JSON.
- Kopia zawiera istniejący pełny eksport v3, gdy jest dostępny model; w przeciwnym przypadku pełny v2. Nie migrujemy dziennika tylko na potrzeby chmury. Istniejące walidatory obsługują również odtwarzanie v1. Statystyki nadal wynikają z zapisanych danych, bez drugiego zbioru wartości obliczonych.
- Statusy: Zapisano lokalnie / Oczekuje na synchronizację / Zsynchronizowano / Błąd, z informacją offline/autoryzacja/konflikt i czasem ostatniej potwierdzonej kopii. Sukces wymaga odczytu kopii z Drive, weryfikacji SHA-256, schematu, powiązań i zgodności z wysłanym dokumentem.
- Ponowienie przy starcie, powrocie online, powrocie do aplikacji i po opóźnieniu rosnącym do 10 minut; dostępny jest przycisk ponowienia. Termin błędu i upload są trwałe. Wiele lokalnych zmian może zostać objętych jedną pełną kopią. Wcześniejsza operacja jest najpierw rozstrzygana, a nowsza rewizja pozostaje oczekująca.

## Protokół bez nadpisywania

Używany zakres: wyłącznie `https://www.googleapis.com/auth/drive.appdata`. Pliki są w prywatnym `appDataFolder`, nie w publicznym katalogu ani zwykłej liście plików Drive. Ten zakres pozwala aplikacji obsługiwać własną ukrytą przestrzeń; nie daje dostępu do pozostałych plików. Kod nie wykonuje PATCH ani DELETE na plikach kopii.

Każda kopia to niezmienny dokument `pushpull-drive-backup` v1: UUID operacji, rodzice, data, pełny JSON treningów i SHA-256 całości. Prywatne `appProperties` zawierają protokół, UUID, digest i rodziców do wykrywania gałęzi. Rodzice są dzieleni na właściwości mieszczące się w limitach Drive; ponad 60 równoczesnych gałęzi jest jawnie odrzucane, bez kasowania kopii.

Upload z UUID i pełnym dokumentem zostaje zapisany lokalnie **przed** POST. Przy utracie odpowiedzi ponowienie najpierw szuka tego UUID i sprawdza treść. Drive może pozostawić identyczne pliki po niejednoznacznym błędzie POST; aplikacja deduplikuje je według UUID/digestu. Nie dopisuje ani nie duplikuje wyników treningowych przy retry.

Dwa telefony zapisujące równocześnie tworzą dwie zachowane gałęzie. Nie wybieramy zwycięzcy według zegara telefonu, nazwy pliku czy daty. Jeżeli zdalna końcówka różni się od wersji znanej temu urządzeniu, automatyczne wysyłanie zatrzymuje się z komunikatem konfliktu. Wyścig między odczytem listy a POST też nie nadpisze danych: powstają osobne kopie, a ponowny odczyt wykrywa rozbieżność.

Nie ma automatycznego scalania wyników dwóch urządzeń. W Dane → Pokaż kopie Drive można:

1. Obejrzeć/pobrać wybraną pełną kopię i świadomie ją przywrócić.
2. Wybrać „Zachowaj lokalne jako nową wersję”, po potwierdzeniu. Poprzednie gałęzie pozostaną do odzyskania; nowa kopia wskazuje je jako rodziców.

Zmiana konta wymaga rozłączenia poprzedniego konta i świadomego połączenia innego. Lokalne kolejki poprzednich kont nie są kasowane. Token w danej karcie musi odpowiadać kontu wybranemu w trwałym stanie; druga karta nie może przełączyć jego zastosowania na inne konto.

## Jednorazowa konfiguracja Google Cloud — właściciel wykonuje świadomie

1. Użyj stabilnego adresu HTTPS PWA i zachowaj jego origin (zmiana domeny oznacza również inny lokalny IndexedDB). Nie używaj rotujących adresów preview jako adresu codziennego treningu.
2. W [Google Cloud Console](https://console.cloud.google.com/) utwórz/wybierz projekt i włącz **Google Drive API**.
3. W **Google Auth Platform / OAuth consent screen** skonfiguruj aplikację, adres wsparcia i dane wymagane przez konsolę. Dla prywatnych testów wybierz External → Testing i dodaj swoje konto do Test users. Dla kont organizacji stosuj jej zasady. Nie publikuj aplikacji OAuth bez osobnej decyzji; konsola może wymagać potwierdzenia domeny/marki i spełnienia aktualnych zasad Google.
4. W Data Access dodaj tylko zakres `https://www.googleapis.com/auth/drive.appdata`. Nie dodawaj pełnego `drive`, Gmail, kontaktów ani własnego logowania PushPull.
5. Utwórz klienta OAuth typu **Web application**. W Authorized JavaScript origins dodaj dokładny origin, np. `https://twoja-aplikacja.vercel.app` — bez ścieżki, wildcardu i końcowego `/`. Lokalne testy wymagają osobnego `http://localhost:PORT`. Token model GIS nie potrzebuje redirect endpointu ani sekretu w aplikacji.
6. Skopiuj wyłącznie **Client ID** (`…apps.googleusercontent.com`). W PWA: Dane → Google Drive → wpisz ID → Zapisz konfigurację → Połącz / odnów Google. Client ID jest publicznym identyfikatorem, nie hasłem. Nie kopiuj client secret ani tokenów do repozytorium, kodu, historii czatu czy plików JSON.
7. Wybierz swoje konto Google i świadomie zaakceptuj zakres własnej przestrzeni aplikacji. Po „Zsynchronizowano” sprawdź listę i pobierz kopię JSON. Nie uznawaj samego połączenia konta za wykonaną kopię.
8. Na drugim telefonie użyj **tego samego projektu/klienta** i konta. Dane → konfiguracja → połączenie → Pokaż kopie → Podgląd. Samo połączenie nigdy nie przywraca ani nie zastępuje lokalnej historii.

OAuth/GIS ograniczenia: oficjalny [token model](https://developers.google.com/identity/oauth2/web/guides/use-token-model) nie daje przeglądarce refresh tokena. Access token jest wyłącznie w pamięci i zwykle jest ważny około godziny. Po wygaśnięciu lub zimnym restarcie PWA trzeba kliknąć **Połącz / odnów Google**; istniejąca sesja Google może pozwolić zrobić to bez ponownego hasła, ale nie jest to gwarantowane. Popup/zgoda, blokada przeglądarki, tryb Testing i zasady konta zależą od Google. Nie udajemy bezterminowego cichego odświeżania. W pełni bezobsługowa synchronizacja po każdym zimnym starcie pozostaje ograniczeniem przy wymaganiu braku backendu. W międzyczasie trening i kolejka działają lokalnie.

SDK pobieramy wyłącznie z `https://accounts.google.com/gsi/client`, po zapisaniu konfiguracji/kliknięciu połączenia; brak konta nie blokuje otwarcia aplikacji. Żądania API są autoryzowane nagłówkiem Bearer, z `credentials: omit`, bez tokenów w URL. Nie cache'ujemy odpowiedzi Google w service workerze. Odłączenie czyści token w pamięci i zatrzymuje synchronizację; odebranie zgody i skasowanie appData w ustawieniach Google jest odrębną decyzją użytkownika.

Jeśli hosting stosuje CSP, dopuść `script-src https://accounts.google.com/gsi/`, `style-src https://accounts.google.com/gsi/style`, `connect-src https://www.googleapis.com https://accounts.google.com/gsi/` i `frame-src https://accounts.google.com`, zachowując istniejące reguły `'self'`. Dla popup OAuth przy COOP użyj `same-origin-allow-popups`, nie `same-origin`. Lokalny serwer zweryfikowanych artefaktów ma odpowiednie CSP. Nie zmieniono ustawień zewnętrznego hostingu ani OAuth.

## Odtwarzanie i ochrona lokalnej pracy

Podgląd sprawdza digest węzła oraz dotychczasową walidację pełnego JSON (w tym v3 i relacje). Pokazuje datę, liczbę sesji/wyników i aktywny plan. Można pobrać oryginalny treningowy JSON, także dla starej wersji kopii.

Przywrócenie wymaga potwierdzenia zastąpienia lokalnej historii i planu. Lokalna rewizja, konto i zdalne gałęzie muszą być zgodne z podglądem. Zapisz/zabezpiecz lokalne szkice przed przywróceniem — aplikacja blokuje zastąpienie historii, gdy pozostają szkice, również z bufora odzyskiwania. Używany jest istniejący import transakcyjny z kopią sprzed importu. Nie usuwamy szkiców ani oryginalnego localStorage. Odtworzona historia może już zawierać aktywowany plan: jego odtworzenie jest świadomym elementem importu, nie automatyczną aktywacją V2 przez połączenie Drive.

Po przywróceniu powstaje nowa pełna kopia, a dotychczasowe wersje Drive pozostają. Nie trzeba i nie wolno czyścić danych aplikacji na telefonie, aby uruchomić synchronizację.

## Koszty i ograniczenia

Brak własnego backendu, subskrypcji PushPull i dodatkowego konta. Obowiązują limity API oraz pojemność konta Google. Dopisujemy pełne kopie i nie kasujemy starych automatycznie; wraz z historią i archiwami JSON zużycie pamięci i koszt listowania wszystkich węzłów rosną. To świadomy pierwszy protokół ochrony historii, a nie obietnica nieograniczonej retencji. Quota/403/429/5xx pozostawiają lokalną kolejkę i komunikat błędu. Bezpieczna retencja/kompaktowanie wymaga przyszłej osobnej pracy, nie kasowania kopii w tym PR.

Ponawianie działa, gdy aplikacja jest uruchomiona, ma sieć i ważną autoryzację. Android może wstrzymać/ubić PWA; nie gwarantujemy pracy w tle po jej zamknięciu. Kolejka wraca po otwarciu. Awaria/utrata telefonu przed potwierdzoną pierwszą kopią nadal może oznaczać utratę danych; zachowaj również eksport JSON poza telefonem. Usunięcie danych witryny lub ukrytych danych aplikacji w Google jest poza gwarancją aplikacji.

## Weryfikacja

Przebiegi i końcowe wyniki są podane w PR. Testy używają wyłącznie syntetycznych treningów i symulowanego OAuth/Drive:

- Node: trwały retry, restart, brak autoryzacji, utrata odpowiedzi POST, nowszy commit w trakcie retry, dwa urządzenia/równoczesne gałęzie, świadome rozstrzygnięcie, poprawność kopii, quota metadanych, izolacja kont i kart.
- Chromium + rzeczywisty IndexedDB: zapis przed oczekującą odpowiedzią Google, 500 i 401, niezależne 6A/6B, szkice niewysyłane, restart offline, późniejszy upload, zakończenie sesji, v3, nowy profil, konflikt, uszkodzona kopia, anulowanie i potwierdzenie odtwarzania oraz lokalna kopia sprzed importu.
- Dotychczasowa regresja Matrix, modeli, szkiców, JSON, migracji i service workera.

**Niewykonane:** prawdziwa autoryzacja konta Google, rzeczywisty upload/download/limity appData oraz test tej funkcji na fizycznym Androidzie. Mocki nie potwierdzają tych elementów. Przed użyciem kopii jako jedynego zabezpieczenia wykonaj na telefonie: lokalny zapis → potwierdzony Drive → restart PWA → odnowienie Google → offline wynik/zakończenie → online retry → pobranie/odtworzenie w drugim profilu. Sprawdź również wygaśnięcie tokena, zamknięcie popupu, dwa urządzenia i update PWA ze szkicem. Nie używaj rzeczywistych danych bez wcześniejszego eksportu poza urządzenie.
