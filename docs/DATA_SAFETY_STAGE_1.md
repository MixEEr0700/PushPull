# Etap 1 — ochrona danych i regresja

Baza: zatwierdzony commit `92390b1449bd61c4c6fdc41ccf8a272e5ff914d3` (v0.3 Matrix — szlif 3). Nie ma migracji IndexedDB ani synchronizacji Drive. Nadal obowiązują plan projektu i ograniczenia danych demonstracyjnych.

## Audyt i zmiany

| Obszar | Ryzyko w wersji bazowej | Zachowanie po zmianie |
| --- | --- | --- |
| Odczyt | Błąd JSON lub wersji powodował `fresh()`, potem zapis mógł zastąpić oryginał. Także `null` i inne falsy JSON traktowano jak brak danych. | Tylko brak klucza oznacza nową bazę. Błąd odczytu, schematu lub wersji blokuje interfejs treningu i zapis. Oryginał pozostaje nietknięty; można pobrać dokładny tekst i wczytać zwalidowaną kopię. |
| Zapis | Wyjątki quota/security pozostawiały zmienioną pamięć JS, niespójną z dyskiem. | Każdy zapis przechodzi walidację. Błąd przywraca ostatni zatwierdzony stan w pamięci i wyświetla komunikat zamiast sukcesu. Drafty serii nie są usuwane po nieudanym zapisie. |
| Import | Sprawdzano tylko wersję i kilka kontenerów, bez kopii. | Odczyt pliku → pełna walidacja → potwierdzenie użytkownika → zachowanie dokładnego oryginału pod osobnym kluczem → atomowe `setItem` głównego klucza → podmiana stanu UI. Anulowanie niczego nie zapisuje. Błąd odczytu, walidacji, kopii lub zapisu nie zastępuje bazy. |
| Kopia przed importem | Brak. | Każdy import otrzymuje osobny klucz `pushpull_skeleton_v1_backup_<data-UTC>_<UUID>`. Kopie można pobrać w zakładce Dane i przywrócić przez ten sam walidowany import. Kopie nigdy nie są automatycznie kasowane ani nadpisywane. Nieudany zapis głównego klucza może zostawić dodatkową, poprawną kopię. |
| Eksport | Zrzut pamięci JS. | Format JSON v1 zachowany. Po błędzie zapisu pamięć odpowiada ostatniemu zatwierdzonemu stanowi. Eksport surowego uszkodzonego/nieobsługiwanego oryginału jest osobny i nie próbuje go naprawiać. |
| Wiele kart | Stara karta nadpisywała nowsze dane. | Porównanie dokładnego poprzedniego tekstu przed zapisem/importem; zdarzenie `storage` blokuje starą kartę i wymaga odświeżenia. |
| Serie | Ręczne serie z poprzedniego treningu mogły zostać cicho zastąpione. | Potwierdzenie obejmuje także serie skopiowane do nowej sesji. |
| Kalendarz | Lokalna północ konwertowana do UTC mogła cofnąć miesiąc w Warszawie. | Arytmetyka miesięcy w UTC, bez zmiany wyglądu i zapisanych dat. |
| Offline | Globalne `caches.match` mogło pobrać stary kod z poprzedniego cache. | Nowa nazwa cache i wyszukiwanie wyłącznie w nim; do precache dodano `storage.js`. Stare cache nie są usuwane, localStorage pozostaje bez zmian. |

## Walidacja i kompatybilność

Zachowano klucz `pushpull_skeleton_v1`, `version: 1`, wszystkie istniejące identyfikatory, sesje, serie, notatki i historię zmian. Eksport pozostaje obiektem v1, nie nowym opakowaniem. Nie są generowane brakujące serie ani nowe ID. Starsze wpisy bez `series` oraz bazy bez opcjonalnego `changes` są obsługiwane. Identyfikatory awaryjnego generatora z kropką również pozostają poprawne. Nieznane dodatkowe pola są zachowywane; niedozwolone klucze prototypu są odrzucane.

Walidacja obejmuje cztery plany i pola ćwiczeń, niepowtarzalne ID i sekwencje sesji, rzeczywiste daty, rotację, status i powiązanie aktywnej sesji, relacje wpis–sesja–ćwiczenie, jeden wynik ćwiczenia na sesję, nieujemne skończone ciężary i dodatnie całkowite powtórzenia, zgodność pól głównych z pierwszą serią oraz znaczniki zmian. Dane niespójne, choć wcześniej akceptowane przez luźny import, nie są automatycznie korygowane: pozostają w oryginalnej postaci do ręcznego odzyskania. Identyfikatory muszą być bezpieczne do istniejących atrybutów HTML.

## Uruchomienie testów

W katalogu głównym repozytorium:

```sh
node --check app.js
node --check storage.js
node --check sw.js
node --test tests/storage.test.js
python3 -m pip install -r tests/requirements.txt
python3 -m playwright install chromium
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Instalacja Playwright jest potrzebna tylko do testów, aplikacja nie otrzymuje zależności runtime. Testy wybierają `CHROMIUM_PATH`, systemowy `chromium`, a następnie przeglądarkę Playwright. W testowanym środowisku Python Playwright 1.62.0 i `/usr/bin/chromium` były już dostępne. Testy uruchamiają własny serwer HTTP na wolnym porcie, izolowane konteksty i dane demonstracyjne; nie otwierają profilu użytkownika. CI zapisano w `.github/workflows/regression.yml`; wykonanie na GitHub jest odrębne od lokalnej walidacji.

Testy Node sprawdzają walidację i zachowanie oryginału przy błędach JSON, wersji, relacji, dat, odczytu, quota, tworzenia kopii i zapisu głównego klucza oraz odtworzenie kopii i kompatybilność starszych danych.

Testy Chromium obejmują pełną rotację, ręczny wybór, kalendarz Warszawa, wyniki różniących się serii, tonaż 1640 kg, notatki, cztery metryki statystyk, edycję wyniku i daty historycznej sesji bez duplikowania/zmiany rotacji, reload, eksport/import, anulowanie, błędne dane, pobranie i odtworzenie kopii, odzyskiwanie po uszkodzonym odczycie, quota/security, ręczne serie oraz konflikt kart i offline. Test wizualny porównuje piksele bieżącej wersji z kodem dokładnie zatwierdzonego commitu, w tym samym Chromium i z tym samym zegarem: trening, rozwinięta karta, statystyki, kalendarz; rozmiary 360×800, 390×844 i 412×915. Wymaga obecności commitu bazowego w historii Git (CI pobiera pełną historię).

## Ograniczenia

- Kopia w tym samym localStorage nie chroni przed usunięciem danych przeglądarki, awarią urządzenia ani brakiem miejsca. Należy regularnie pobierać JSON poza przeglądarkę. Brak miejsca na kopię blokuje import, zamiast kontynuować bez zabezpieczenia.
- localStorage zapewnia atomowość pojedynczego `setItem`, ale nie transakcję wielokluczową ani atomowy compare-and-swap pomiędzy równocześnie zapisującymi kartami. Sprawdzenie konfliktu i `storage` ograniczają ryzyko; nie należy równolegle edytować w wielu kartach, zwłaszcza ze starą wersją aplikacji. To pozostaje tematem dla warstwy transakcyjnej w kolejnym etapie.
- Walidator sprawdza schemat i relacje, nie poprawność treningowego planu V2. Nie rekonstruuje ani nie migruje uszkodzonych danych i nie zmienia wersji bazy.
- Kolorystyka, CSS, karty i moduł statystyk pozostają zachowane. Nowe kontrolki dotyczą wyłącznie kopii/odzyskiwania danych.
- Testy mobilne wykonuje desktopowy Chromium z mobilnym viewportem. Nie zastępują testu dotyku, klawiatury, instalacji PWA ani zachowania na rzeczywistym Androidzie. Nie potwierdzają wszystkich scenariuszy aktualizacji PWA ani awarii urządzenia w trakcie zapisu.
- Nadal brak IndexedDB, rozdzielenia notatek trenera/użytkownika i wersjonowania parametrów planu. Nie są to zmiany tego etapu.

## Wynik lokalnej walidacji — 21.10.2026

- Node 24.19.0: składnia `app.js`, `storage.js`, `sw.js` poprawna; **42/42 testy warstwy danych PASS**, 0 pominiętych.
- Python 3.12.14 / Playwright 1.62.0 / Chromium 154.0.8037.57: **12/12 scenariuszy przeglądarkowych PASS**, 0 pominiętych. W scenariuszu wizualnym wykonano 12 porównań pikseli z zatwierdzonym kodem (4 ekrany × 3 rozmiary), wszystkie zgodne.
- `git diff --check`: PASS. `style.css`, `icon.svg`, `manifest.webmanifest` identyczne z bazą.
- Niewykonane: rzeczywisty Android, instalacja PWA przez HTTPS, pełna macierz aktualizacji PWA, uruchomienie CI na GitHub (wynik lokalny nie jest wynikiem CI).
