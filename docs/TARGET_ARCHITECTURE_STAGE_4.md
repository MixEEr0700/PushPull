# Aplikacja Treningowa — architektura docelowa, etap 4

Status: **projekt, nie implementacja**. Baza: `adadf8f8c45af3693de559f09971759a53ea1bb0`, main po PR #3. Ten etap wdraża tylko nazwę użytkową i testy jej aktualizacji. Nie wprowadza nowych funkcji treningowych, profili, schematu IndexedDB, Drive ani raportu trenera. Historyczny plan v1 i dokumenty etapów 1–3 pozostają źródłem historii decyzji.

## Granice i obecny stan

Jedna paczka statyczna, jeden stabilny adres HTTPS i jedna tożsamość PWA mają obsługiwać wielu niezależnych użytkowników. Serwer dostarcza kod, nie treningi; nie powstaje centralny panel trenera ani dostęp trenera do prywatnych Dysków. Użytkownik sam pobiera raport i decyduje, komu go przekazuje.

Obecnie IndexedDB `pushpull` (schema 1) oraz localStorage są izolowane przez origin i profil przeglądarki, nie konto osoby. Dwie osoby w tym samym profilu widzą te same dane. Inny telefon/profil ma własną historię. Podkatalog nie izoluje bazy. Projektowane profile aplikacji nie zastąpią izolacji systemowej: osoba kontrolująca ten sam profil przeglądarki lub kod tego origin może odczytać magazyn. Na współdzielonym urządzeniu rekomendowane osobne profile systemu/przeglądarki.

Warstwy docelowe: zaakceptowany interfejs → przypadki użycia (sesja, import planu, korekta, raport) → domena i walidacja → repozytorium IndexedDB. Niezależne adaptery: pełna kopia JSON, raport dla trenera, opcjonalny Drive. Zapis lokalny ma działać bez logowania i sieci; potwierdzenie zapisu dopiero po zakończeniu transakcji. Synchronizacja ma osobny status, nie może opóźniać ani udawać lokalnego zapisu.

## Model logiczny

Poniżej model przyszły, nie aktualny DDL. Wersje schematu IDB, formatu backupu, planu i raportu są niezależne.

| Encja | Klucz i dane źródłowe | Relacje / reguły |
| --- | --- | --- |
| Profile | `profileId` UUID, nazwa lokalna, data utworzenia | Domyślny profil gościa; `ownerId` w każdej encji domenowej. Binding dostawcy `issuer + sub` oddzielony od lokalnego ID; email nie jest kluczem. |
| Plan | istniejący lub nowy `planId`, owner, nazwa, aktywna wersja | Jeden program może zawierać dowolną liczbę jednostek; nie utożsamiać jednostki z programem. |
| PlanVersion | `planVersionId`, planId, numer, parentVersionId, data, autor/źródło, status weryfikacji | Niezmienny snapshot. Nowy import tworzy wersję; nie przepisuje wykonanych sesji. |
| TrainingUnit | `unitId`, planVersionId, etykieta, kolejność | Dowolna liczba i nazwy, np. całe ciało, góra/dół, PUSH/PULL. Rotacja jest listą ID jednostek, a nie enumem czterech nazw. |
| ExerciseIdentity | istniejący `exerciseId`, owner, nazwa, aliasy, opcjonalna relacja odpowiednika | Tożsamość niezależna od nazwy, pozycji i planu. Nowe ID tylko dla nowego ćwiczenia; nie scalać automatycznie po nazwie. |
| ExercisePrescription | `prescriptionId`, unitId, exerciseId, pozycja, serie, min/max powtórzeń, RIR, tempo, jednostka obciążenia | Parametry należą do wersji planu. Tempo jako uporządkowane fazy oraz oryginalny tekst; jawne null dla nieznanych wartości. Opcjonalne struktury back-off/drop/superserii w kolejnych osobno testowanych etapach. |
| CoachInstruction | ID, prescriptionId/planVersionId, tekst, źródło | Niezmienna instrukcja trenera z planu; korekta tworzy nową wersję. |
| UserNote | ID, owner, exerciseId/sessionId/entryId, tekst, revision | Osobna notatka użytkownika, nie modyfikuje instrukcji. `legacy-shared` zachowane bez zgadywania autorstwa. |
| TrainingBlock | blockId, owner, nazwa, daty, wskazania sesji/wersji | Wyznacza zakres raportu; wybór całej historii również dostępny. |
| Session | istniejący sessionId, owner, unitId, planVersionId, snapshot parametrów, status, data lokalna, strefa, czas UTC jeśli znany | Snapshot z początku sesji; historyczne braki opisane pochodzeniem, bez wymyślania dawnych parametrów. |
| Entry / Set | istniejący entryId, sessionId, exerciseId; setId, entryId, kolejność, ciężar, jednostka, powtórzenia, wykonane RIR/tempo jeśli znane | Waga dziesiętna w ustalonej precyzji i jednostce, nie zaokrąglać oryginału przy migracji. Brak serii nie oznacza zera. Nowe ID serii stabilne; stara pozycja zachowana w mapie migracji. |
| TechniqueEvent | istniejący changeId lub techniczny klucz legacy, exerciseId, data, opis, revision, źródło | Zmiana kąta/maszyny/techniki zachowuje historię; segmenty porównywalności jawne. |
| Revision / Operation | opId, owner, deviceId, entityId, parentRevisionIds, payload, rodzaj, data | Audyt korekt, tombstone zamiast nieodwracalnego kasowania. Czas urządzenia nie rozstrzyga konfliktu. |
| Backup / SyncCheckpoint | ID, owner, format/schema, liczby, hash, pochodzenie, remoteFileId/cursor | Kopie i metadane synchronizacji odrębne; tokeny OAuth nie należą do backupu. |

Indeksy docelowe: owner+data sesji, owner+exerciseId+data, sessionId+pozycja wpisu, entryId+pozycja serii, planId+wersja oraz opId. Wszystkie odwołania walidowane w obrębie właściciela. Klucze złożone `[ownerId, legacyId]` pozwalają zachować istniejące ID jako wartości bez kolizji profili. Obecna nazwa bazy pozostaje `pushpull`; przyszłe store'y/indeksy i wersję schematu wdrażać dopiero po testach migracji.

Tonaż = suma ciężar × powtórzenia dla zapisanych serii o zgodnej jednostce. Wyniki obliczeń i agregaty są odbudowywalne, z wersją algorytmu; nie zastępują źródła. Nie łączyć bez oznaczenia kilogramów, funtów, masy własnej ani różnych wariantów techniki. Dotychczasowa metodologia statystyk pozostaje bez zmian w etapie 4.

## Import i wersjonowanie planów

Przyszły kontrakt `training-plan` z `formatVersion`, nazwą, źródłem, wersją i tablicą jednostek. Każda jednostka ma uporządkowane ćwiczenia z jawnym exerciseId lub propozycją nowego ćwiczenia, seriami, zakresem powtórzeń, RIR, tempem i instrukcją. Walidator wymaga skończonych liczb, poprawnych zakresów, unikalnych ID, limitów rozmiaru i poprawnych relacji; traktuje tekst jako tekst, nie HTML/skrypt. Nieobsługiwana wersja i nieznane wymagane pola blokują import, a nie znikają.

Przebieg: odczyt bez zapisu → walidacja → podgląd zmian i mapowanie tożsamości → pełny backup poza aplikacją → potwierdzenie → jedna transakcja → odczyt kontrolny → dopiero publikacja nowej aktywnej wersji. Anulowanie na dowolnym kroku przed commit niczego nie zmienia. W razie quota lub błędu stara wersja jest nadal aktywna. Zmiana planu nie zmienia aktywnej sesji ani nie przelicza historycznych parametrów.

Nazwy podobne nie dowodzą tożsamości. Użytkownik potwierdza powiązanie z istniejącym ćwiczeniem; wątpliwość oznacza oddzielne ćwiczenie i opcjonalną relację, nigdy destrukcyjne scalenie. Obecne cztery rekordy `plans` oznaczają jednostki; migracja opakuje je wspólnym programem legacy, zachowując ich ID jako ID jednostek i mapę pochodzenia. Nie odgadywać, które stare notatki napisał trener.

## Raport dla trenera a pełny backup

Projektowany ręczny raport `training-coach-report`, version 1: zakres (blockId lub cała historia, granice dat włącznie i strefa), czas eksportu, wersja aplikacji/algorytmu, jednostki, jawne braki, liczby rekordów oraz identyfikatory. Zawiera plany i wersje użyte w wybranych sesjach, snapshoty instrukcji, ćwiczenia, daty/status sesji, wszystkie serie i ich kolejność, ciężary/powtórzenia, RIR/tempo jeśli dostępne, notatki, historię techniki i wyliczony tonaż. Zdarzenia sprzed bloku potrzebne do ustalenia techniki początkowej dołączone jako kontekst, wyraźnie poza zakresem wyników. Nieobecne dane oznaczone null/pochodzeniem, a nie zero.

Wyjścia z tego samego snapshotu: czytelny UTF-8 JSON z opisem pól (ChatGPT) oraz paczka CSV UTF-8 z tabelami sessions, exercises, sets, technique_events, notes, plans i plan_versions, wspólnymi kluczami, nagłówkami i słownikiem. Daty ISO 8601, daty treningów dodatkowo YYYY-MM-DD, liczby bez separatorów tysięcy; instrukcja importu CSV do Excela z jawnym separatorem/przecinkiem dziesiętnym. Komórki tekstowe zaczynające się od `=`, `+`, `-`, `@`, tabulatora lub CR zabezpieczone przed formułami przy eksporcie do arkusza; JSON zachowuje dokładny tekst. Testy muszą sprawdzić Unicode, cudzysłowy, nowe linie, liczby i relacje po odczycie. XLSX może być kolejnym adapterem po analizie zależności; nie jest warunkiem formatu.

Raport jest odczytem spójnej transakcji, nie zmienia historii ani nie przesyła jej automatycznie. Podgląd zakresu i notatek umożliwia świadomą decyzję o ujawnieniu. Brak OAuth, tokenów, danych innych profili, surowych uszkodzonych archiwów i niepowiązanych danych spoza zakresu. ChatGPT/Excel otrzymują plik wyłącznie z decyzji użytkownika. Treści notatek są niezaufanymi danymi, nie instrukcjami dla odbiorcy.

Pełny backup pozostaje osobnym eksportem do odtworzenia wszystkich danych, wersji i archiwów. Raport częściowy nie jest kopią i nie wolno go przyjmować w imporcie backupu. Dzisiejszy `pushpull-backup` v2 i odczyt v1 zachowane. Przyszła zmiana formatu wymaga osobnego numeru i bezstratnego adaptera v1/v2; eksport jednego profilu z jawnym owner/proweniencją, a ewentualny eksport wszystkich profili to odrębna świadoma operacja. Import do innego właściciela wymaga potwierdzenia i mapowania w kopii, nie przejęcia tożsamości Google z pliku.

## Indywidualny Google Drive — decyzje projektowe

Synchronizacja jest dobrowolna, per profil i własne konto. Bez konta trenera, wspólnego Dysku podopiecznych czy dostępu administracyjnego. Profil gościa nie jest automatycznie przypisywany pierwszemu zalogowanemu kontu. Powiązanie konta wymaga potwierdzenia i backupu; zmiana konta zatrzymuje wysyłkę, zamyka dotychczasowy kontekst danych, usuwa token z pamięci i wymaga wyboru właściwego profilu. Nie łączyć automatycznie danych po emailu lub nazwie pliku.

Preferowany prototyp: `drive.appdata` i dedykowany `appDataFolder` na **własnym** Drive. API opisuje ten scope jako dostęp do własnych danych konfiguracyjnych aplikacji. Ukryty folder nie jest zwykłym katalogiem do ręcznego oglądania/udostępniania, dlatego niezależne pełne backupy JSON nadal obowiązkowe. Alternatywa `drive.file`: tylko konkretne pliki utworzone/używane z aplikacją, przydatne dla jawnych plików; nie daje dostępu do całego Dysku. Nie żądać szerokich `drive`/`drive.readonly`, nie wymagać publicznych linków do historii. Wybór appData musi przejść próbę zgodności z aktualnymi zasadami Google przed implementacją.

PWA statyczna może użyć Google Identity Services token model: krótkotrwały access token tylko w pamięci, ponowna świadoma autoryzacja po wygaśnięciu, synchronizacja na pierwszym planie z siecią. Client ID jest publicznym identyfikatorem, **client secret nie może trafić do JS**. Nie przechowywać refresh/access tokenów w localStorage, IndexedDB, logach, URL ani backupie. Nie obiecywać ciągłej synchronizacji po zamknięciu PWA. Backend z bezpieczną sesją/refresh tokenem byłby osobnym projektem, kosztem i granicą zaufania, nie częścią tej architektury statycznej. Identyfikację konta projektować z udokumentowanym OIDC (issuer/sub, aud/nonce i weryfikacja właściwa wybranemu przepływowi), nie przez dekodowanie niezaufanego JWT. Nie dodawać dodatkowych zakresów tożsamości bez potrzeby.

Przed uruchomieniem: zatwierdzony origin HTTPS i domena, OAuth consent screen, polityka prywatności/usuwania danych, dozwolone origins i ewentualne redirect URI, sprawdzenie klasyfikacji wybranych scope i wymogów weryfikacji. Tryb external/testing ogranicza dostęp do wskazanych testerów; limity, żywotność zgód/refresh tokenów i weryfikacja zależą od aktualnej konfiguracji Google, nie są gwarancją tej dokumentacji. Nie konfigurowano projektu Google, klientów, zgód ani kluczy. CSP i zależności sieciowe GIS będą wymagały osobnego przeglądu; obecna restrykcyjna CSP nie jest gotową integracją OAuth.

### Konflikty, awarie i odzyskiwanie

1. Każda lokalna transakcja atomowo zapisuje zmianę i outbox z opId; opId zapewnia idempotencję ponowień. Odrębne deviceId, wersje rodziców i owner na wszystkich operacjach. Brak sieci/revoked token/quota Drive nie cofa lokalnego treningu.
2. Zamiast nadpisywać jeden plik stanu z wielu urządzeń: niezmienne paczki operacji per urządzenie i okresowe pełne checkpointy z hash/licznikami. Nazwa pliku Drive nie jest unikalnym kluczem; zapamiętać fileId, deduplikować po opId i zawartości, pobierać wszystkie rozbieżne gałęzie. Nie zakładać transakcji wieloplikowej ani wyłącznej blokady Drive.
3. Publikacja checkpointu po zweryfikowaniu kompletu paczek i spójności; referencja do niekompletnej paczki jest ignorowana z komunikatem i retry. Importowane dane najpierw w obszarze staging, walidacja wersji/hash/relacji/owner, backup lokalny, potem atomowa akceptacja. Nie ufać plikowi tylko dlatego, że jest na Drive.
4. Niezależne nowe sesje można dołączyć. Równoczesne korekty tej samej serii/notatki lub usunięcie kontra edycja zachowują obie rewizje i wymagają rozstrzygnięcia; bez last-write-wins według zegara. Konflikt wersji planu nie przepisuje wcześniejszych sesji. Tombstone nie usuwa zawartości odzyskiwalnych kopii.
5. Retry z backoff/jitter dla 429/5xx, rozróżnienie auth/403 quota/brak uprawnień, wznowienie po zerwaniu transferu. Odmowa zapisu nie pokazuje sukcesu synchronizacji. Wygaśnięty kursor zmian oznacza pełne ponowne listowanie i deduplikację, nie reset historii.
6. Nowy telefon: wybrać profil/konto, odczytać zweryfikowany checkpoint i operacje, pokazać zakres, zatwierdzić po backupie ewentualnej historii lokalnej. Usunięty/uszkodzony plik → wcześniejszy checkpoint, lokalny outbox lub JSON. Nie propagować braku pliku jako usunięcia wszystkich sesji.

Retencja i kompaktowanie dopiero po udowodnieniu odtwarzalności oraz uwzględnieniu długo nieaktywnych urządzeń. Drive nie gwarantuje nieusuwalności; użytkownik może cofnąć zgodę/usunąć dane. Hash wykrywa niespójność, nie jest podpisem ani ochroną przed złośliwym kodem. Drive nie jest szyfrowaniem end-to-end przez aplikację; ewentualne szyfrowanie i odzyskiwanie klucza wymaga osobnego projektu. Kod z origin ma dostęp do danych, więc XSS i przejęcie hostingu pozostają istotnymi ryzykami.

## Hosting niezależny od komputera i aktualizacje

Dla docelowej aplikacji wielu użytkowników rekomendowane **statyczne HTTPS na Cloudflare Pages ze stałą własną domeną**, z ręcznie zatwierdzaną publikacją wyłącznie allowlistowanego artefaktu. Komputer autora nie musi działać. Repo może pozostać prywatne, np. przez upload samej paczki; odbiorca strony i tak dostaje kod runtime. Dostępna publicznie aplikacja nie oznacza publicznej historii — dane pozostają lokalne lub na indywidualnym Drive. To proponowane przyszłe wdrożenie, wymagające osobnej zgody; niczego nie aktywowano.

Żądania statyczne Pages są według odczytanego oficjalnego źródła darmowe bez limitu liczby żądań; pozostałe limity budów/rozmiaru i zasady usług obowiązują. Domena kosztuje według rejestratora; Functions/backend/OAuth-verification i płatna kontrola dostępu mogą zwiększyć koszty. Nie wyceniono nieutworzonych usług. Dla prywatnego testu niezależnego od PC: mały VPS stale działający z serwerem artefaktu i Tailscale Serve, opłata VPS i ewentualny plan VPN; wymaga administrowania/aktualizacji OS. Alternatywnie Cloudflare Access dopiero po ochronie wszystkich adresów produkcji, preview i aliasów oraz testach PWA offline. Prywatne repo ani Access tylko preview nie dowodzą prywatności witryny. GitHub Pages: dostępność z prywatnego repo zależy od planu; prywatny dostęp do strony ma dodatkowe ograniczenia Enterprise opisane w etapie 3.

Najpierw wybrać stały origin: zmiana hosta/protokołu/portu nie przenosi IndexedDB. Dla zmiany domeny wymagany eksport na starym origin, zwalidowany import na nowym i zachowanie starej instalacji do porównania. Do żadnego hostingu nie wysyłać JSON użytkownika, sekretów ani fixture'ów. Konfiguracja nagłówków CSP, MIME, no-cache/HSTS i całej paczki ma odpowiadać etapowi 3; istniejący serwer loopback nie jest automatycznie konfiguracją Cloudflare.

Aktualizacja: niezmienny artefakt z SHA-256, weryfikacja w CI, świadome zatwierdzenie wydania, kompletna atomowa publikacja na tym samym origin. Service worker pobiera i weryfikuje cały shell, nie wymusza reload/skipWaiting; czeka na zamknięcie wszystkich starych klientów. Nigdy nie usuwa danych IDB/LS. Cofnięcie kodu musi sprawdzać zgodność schematu: stary kod nie może otworzyć nowszej bazy i zacząć pustej. Preferowany roll-forward; rollback kodu nie jest rollbackiem danych. Kopia poza urządzeniem przed każdą migracją. Stare cache dziś pozostają i zajmują miejsce; ich przyszła retencja wymaga osobnego testu bez dotykania bazy.

## Zmiana nazwy i już zainstalowana PWA

HTML title, opis oraz manifest name/short_name teraz „Aplikacja Treningowa”. `id: ./index.html`, `start_url: ./index.html`, `scope: ./`, kolory, logo, ikony, nazwa bazy i klucze pozostają dokładnie te same. Regeneracja workera zmienia wyłącznie wydanie shellu i jego hashe. Nazwa jest metadanymi, nie kluczem danych ani nową aplikacją przy zachowaniu origin/ID. Długi short_name może zostać skrócony przez launcher.

Przeglądarka może opóźnić odświeżenie nazwy WebAPK albo wymagać monitu. Nie obiecujemy zmiany etykiety launchera natychmiast. Nie usuwać instalacji ani danych, aby wymusić nową nazwę. Test Chromium sprawdza rzeczywisty upgrade stage3 → stage4 i dane, ale nie testuje aktualizacji WebAPK na fizycznym Androidzie. Odbiór telefonu pozostaje obowiązkowy w [checkliście](ANDROID_TEST_CHECKLIST.md).

## Źródła i zakres weryfikacji

21.10.2026 odczytano oficjalne [Drive v3 discovery (zakresy i API)](https://github.com/googleapis/google-api-go-client/blob/main/drive/v3/drive-api.json), [Google Auth Library](https://github.com/googleapis/google-auth-library-nodejs/blob/main/README.md) i [Cloudflare Pages pricing](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/docs/pages/functions/pricing.mdx). Źródła Pages/Access/Tailscale i ograniczenia ich odczytu pozostają w [etapie 3](PWA_TEST_DEPLOYMENT_STAGE_3.md). Discovery potwierdza zakres uprawnień, nie aktualne decyzje weryfikacji OAuth konkretnego klienta.

Przed implementacją sprawdzić dokumentację [GIS token model](https://developers.google.com/identity/oauth2/web/guides/use-token-model), [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth), [appDataFolder](https://developers.google.com/workspace/drive/api/guides/appdata) i [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies). Te strony są referencjami do przyszłej weryfikacji; nie deklarujemy wykonania consent flow ani dostępu do konfiguracji Google. Nie wpisano klienta OAuth, domeny, tokenów ani danych użytkowników.
