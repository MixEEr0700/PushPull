# Etap 2 — raport testów

## Przygotowanie

Sprawdzono `main` po PR #1 (`99902a2`). PR #1 był scalony; oba jego uruchomienia GitHub Actions miały wynik SUCCESS. Prace etapu 2 wykonano na `feature/stage-2-indexeddb`, bez modyfikacji `main`.

Środowisko lokalne: Node 24.19.0, Python 3.12.14, Python Playwright 1.62.0, Chromium 154.0.8037.57. Aplikacja nadal jest statyczna, bez zależności npm i bez etapu budowania. Playwright jest zależnością testową.

```sh
node --check app.js
node --check storage.js
node --check indexeddb.js
node --check sw.js
node --test tests/storage.test.js
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Instalacja narzędzi do testów na nowej maszynie: `python3 -m pip install -r tests/requirements.txt` oraz `python3 -m playwright install --with-deps chromium`. Można wskazać `CHROMIUM_PATH`; bez niego testy wybierają systemowy Chromium lub binarkę Playwright. Testy tworzą własne lokalne serwery, konteksty i tymczasowy profil. Nie korzystają z prywatnego profilu ani danych użytkownika.

## Zakres

| Wymaganie | Wykonana kontrola |
| --- | --- |
| Pusta baza | Zweryfikowana inicjalizacja IndexedDB, zero sesji/serii, bez tworzenia pustej historii w localStorage. |
| Struktura v1 i zachowanie danych | Fixture utworzona z ćwiczeń zatwierdzonego kodu: 34 ćwiczenia, 5 sesji, 5 wyników, 8 serii, wpis starszego typu bez serii, notatki Unicode, znaczniki techniki i dodatkowe pola. Porównanie całego dokumentu, ID, relacji i oryginalnego tekstu localStorage znak w znak. |
| Przerwanie w połowie | Wymuszone `transaction.abort()` po rozpoczęciu zapisu serii; brak rekordów częściowej migracji, brak znacznika właściciela, poprawne ponowienie. |
| Zamknięcie podczas migracji | Prawdziwa transakcja utrzymana w stanie aktywnym, zamknięcie karty, sprawdzenie rollbacku i ponowna migracja. |
| Brak miejsca | Wstrzyknięty `QuotaExceededError` podczas zapisu serii i podczas tworzenia kopii; brak zastąpienia historii. Nie jest to test fizycznego zapełnienia dysku. |
| Odczyt kontrolny | Celowe zniekształcenie zapisywanej serii powoduje odrzucenie migracji i pełny rollback. |
| Uszkodzony JSON / wersja | Błędny JSON, `null`, pusty ciąg, nieobsługiwana wersja; ekran odzyskiwania, pobranie oryginału, brak pustej historii. |
| Kilka kart | Nakładające się uruchomienia migracji; równoczesne zapisy dwóch backendów i jednego backendu; tylko jeden zapis danej rewizji może zostać zatwierdzony. |
| Starsza aplikacja | Uruchomiony rzeczywisty kod etapu 1 modyfikuje localStorage po migracji; nowa wersja blokuje edycję i umożliwia eksport obu historii. Import wybranej kopii zabezpiecza konfliktowy zapis. |
| Pełny eksport/import | v2 obejmuje v1, wersje planów i archiwum kopii. Zachowanie dodatkowej wersji archiwalnej, notatek, serii i metadanych; odtworzenie po ponownym otwarciu. Starsze kopie v1 nadal przyjmowane. |
| Błędny pełny import | Odrzucenie niepoprawnych wersji kontenera, katalogu, relacji sesji, parametrów archiwalnej wersji i archiwum; aktywna historia pozostaje identyczna. |
| Zamknięcie i ponowne otwarcie | Nowa karta oraz odrębnie zamknięcie i ponowne uruchomienie rzeczywistego procesu Chromium z tym samym tymczasowym profilem. |
| Uszkodzona/brakująca IndexedDB | Usunięcie serii wykrywa weryfikacja; pobranie technicznego zrzutu i zabezpieczenie go przed odtworzeniem. Brak bazy przy istniejącym znaczniku nie uruchamia automatycznie starej historii. |
| Komunikat sukcesu | Aktywna transakcja nie pokazuje „Wynik zapisany”. Po `oncomplete` komunikat się pojawia. Abort przed zakończeniem nie pokazuje sukcesu i zachowuje poprzedni stan. |
| Offline i PWA | Aktualizacja rzeczywistego workera z kodu etapu 1, błąd migracji po aktualizacji, następnie ponowienie offline; dodatkowo odświeżenie offline i ochrona przed zasobami starego cache. |
| Poprzednia regresja | Pełna rotacja, ręczny wybór, kalendarz Warszawa, serie wspólne/różne, tonaż 1640 kg, cztery metryki, notatki, korekta historycznej daty i wyniku bez duplikowania/zmiany rotacji, eksport/import, anulowanie, quota/security i ochrona ręcznych serii. Testy funkcjonalne odczytują teraz docelową IndexedDB, nie starą kopię localStorage. |
| Matrix | 12 porównań pikseli: trening, rozwinięta karta, statystyki i kalendarz na 360×800, 390×844 i 412×915 względem kodu `92390b1`, z identycznym zegarem i przeglądarką. |

Nie wyłączano wcześniejszych testów warstwy v1. Dodano sprawdzenie blokady zapisu starego adaptera po ustawieniu właściciela IndexedDB.

## Ograniczenia walidacji

Testy działają na prawdziwej IndexedDB i service workerze Chromium, z kontrolowanym wstrzykiwaniem błędów na granicy API. Nie użyto zastępczej implementacji IndexedDB. Wymuszenie abort/quota nie dowodzi zachowania przy każdej awarii sprzętu lub systemu plików.

Nie wykonano testów na fizycznym Androidzie, instalacji PWA przez publiczny HTTPS, innych silników przeglądarek, odcięcia zasilania, ręcznego scalenia dwóch rozbieżnych historii ani benchmarków dużej bazy. Aplikacja nie została opublikowana.

## Wynik lokalny — 21.10.2026

- Składnia czterech plików JavaScript: **PASS**.
- `node --test tests/storage.test.js`: **43/43 PASS**, 0 pominiętych.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: **30/30 PASS**, 0 pominiętych. Obejmuje 12 scenariuszy poprzedniej regresji i 18 dodatkowych scenariuszy IndexedDB/migracji, w tym osobny test dwóch operacji tego samego backendu.
- Porównanie Matrix: **12/12 zgodnych obrazów**.
- `git diff --check`: **PASS**. `style.css`, `icon.svg` i `manifest.webmanifest` identyczne z bazą `main` etapu 2.

## GitHub Actions

Workflow `.github/workflows/regression.yml` uruchamia sprawdzanie składni, wszystkie testy Node oraz wszystkie scenariusze przeglądarkowe. Pobiera pełną historię potrzebną do porównania z zatwierdzonym kodem i do testu aktualizacji z etapu 1.

Aktualne wykonania dla tej gałęzi: [Data safety and mobile regression](https://github.com/MixEEr0700/PushPull/actions/workflows/regression.yml?query=branch%3Afeature%2Fstage-2-indexeddb). Wynik lokalny powyżej nie jest sam w sobie wynikiem CI; obserwowany wynik GitHub Actions dla PR podaje raport końcowy zadania i sekcja Checks pull requesta.
