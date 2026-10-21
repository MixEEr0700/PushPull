# PushPull

Mobilny dziennik treningowy PWA na Androida. Zatwierdzony wzorzec: **PushPull v0.3 Matrix — szlif 3**.

## Stan przygotowania — 21.10.2026
Repozytorium przygotowane organizacyjnie. **Brakuje rzeczywistego kodu zatwierdzonego szkicu. Aplikacja nie jest wdrożona ani przetestowana.** Nie utworzono zastępczej aplikacji ani nowej makiety.

- [Specyfikacja nadrzędna](PushPull_PLAN_PROJEKTU_v1.md)
- [Instrukcje dla Codexa i kryteria testów](AGENTS.md)

## Następny krok
Dostarczyć kompletne źródła „v0.3 Matrix — szlif 3” wraz z zasobami i dostępnymi plikami zależności. Zweryfikować kompletność, zachować oryginalną wersję w historii Git, uruchomić ją i ustalić bazę testów. Dopiero wtedy dobrać komendy instalacji/build, CI i sposób hostowania. Nie ma obecnie potwierdzonych komend uruchomienia.

Następnie: IndexedDB offline-first → walidowany eksport/import JSON i odtworzenie backupu → weryfikacja V2 z dokumentem trenera → regresja i trwałość danych → publikacja PWA HTTPS i test Androida → później Drive.

## Ochrona danych i interfejsu
Zachowujemy zaakceptowany interfejs, stabilne ID ćwiczeń, historię treningów i techniki, wyniki serii oraz wersje planów. Żadnych migracji bez backupu i walidacji. Dane makietowe nie są zweryfikowanym planem treningowym.

## Dostęp i wdrożenie
Repozytorium utworzono jako prywatne na koncie MixEEr0700, gałąź main. Przeglądarka pozwala właścicielowi odczytywać i zapisywać pliki. Próba odczytu przez konektor GitHub zwróciła 404; jego dostęp do nowego repozytorium oraz dostęp środowiska Codex wymagają odrębnego potwierdzenia. Nie zmieniano uprawnień integracji ani nie dodawano współpracowników.

Hosting, manifest, service worker, automatyczne wdrożenie oraz CI nie zostały skonfigurowane przed otrzymaniem kodu. Nie publikować danych treningowych, eksportów ani sekretów w repozytorium lub artefaktach hostingu.

## Weryfikacja
Potwierdzono utworzenie repozytorium i zapis dokumentacji przez interfejs GitHub. Testów aplikacji nie wykonano: brak źródeł. Kryteria gotowości i plan testów znajdują się w specyfikacji i AGENTS.md.
