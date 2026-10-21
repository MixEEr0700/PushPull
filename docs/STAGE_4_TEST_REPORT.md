# Etap 4 — zakres i raport testów

Baza: `adadf8f8c45af3693de559f09971759a53ea1bb0`, main po scalonym PR #3. Gałąź: `feature/stage-4-name-and-architecture`. Nie zmieniano main, widoczności repo ani hostingu; read-only API potwierdziło `private=true`, `has_pages=false`.

## Zmiany plików

| Pliki | Zakres |
| --- | --- |
| `index.html`, `manifest.webmanifest` | Nazwa „Aplikacja Treningowa”, tytuł i opisy; obie nazwy manifestu zgodne. |
| `sw.js` | Wygenerowany identyfikator wydania i SHA-256 dwóch zmienionych zasobów; polityka workera bez zmian. |
| `tests/test_pwa.py` | Dwa dodatkowe testy: kontrakt tożsamości/ikon/danych i rzeczywisty upgrade z etapu 3 z pełną kopią, nową nazwą, offline i odtworzeniem JSON. |
| `README.md`, `docs/README_BEFORE_STAGE_4.md` | Aktualny opis produktu/uruchomienia; wcześniejszy README zachowany bez zmian jako historia. |
| `docs/CODEX_HANDOFF.md`, `docs/ANDROID_TEST_CHECKLIST.md` | Wskazanie obecnego etapu i wymagany fizyczny odbiór nowej nazwy. |
| `docs/TARGET_ARCHITECTURE_STAGE_4.md` | Model, izolacja, plany, notatki, raport/backup, Drive/OAuth/konflikty, hosting i aktualizacje. Wyłącznie projekt. |
| `docs/PROJECT_PLAN_ANNEX_STAGE_4.md` | Wersjonowany aneks, kolejność etapów i bezstratna migracja. Specyfikacja historyczna niezmieniona. |
| `docs/STAGE_4_TEST_REPORT.md` | Ten raport. |

## Co zachowano

CSS, app.js, storage.js, indexeddb.js i szablon workera są bajtowo identyczne z main po PR #3. Wszystkie ikony/logo również. Bez zmian: `id`, `start_url`, `scope`, kolory, IndexedDB `pushpull` schema 1, klucze localStorage, ID i format `pushpull-backup` v2/odczyt v1. Techniczne nazwy plików kopii `pushpull-*` pozostają kompatybilne.

Rotacja czterech treningów, start/koniec, kalendarz i edycja historyczna, szybki wynik/ołówek, serie wspólne i indywidualne, tonaż/statystyki, notatki i technika, migracja z retry, backup/import i offline pozostają objęte pełnym dotychczasowym zestawem regresji. Nie zmieniano parametrów V2. Nie implementowano nowego silnika planów, profili, Drive ani raportu trenera. Nie aktywowano usług.

## Polecenia weryfikacji

```sh
node --check app.js
node --check storage.js
node --check indexeddb.js
node --check sw.js
node --test tests/storage.test.js
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/stage4
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Narzędzia lokalne: Node 24.19.0, Python 3.12.14, Playwright 1.62.0 i Chromium 154.0.8037.57. Dane syntetyczne zgodne ze strukturą starej aplikacji, nie prywatne dane osoby. Weryfikacja danych po zmianie nazwy porównuje cały eksport: data, catalog i archives oraz dokładny tekst źródłowego localStorage i kopię legacy. Przy odtworzeniu import dodatkowo tworzy archiwum poprzedniego stanu.

## Wynik lokalny — 21.10.2026

- Składnia czterech plików JavaScript: **PASS**.
- Node: **43/43 PASS**, 0 pominiętych.
- Python/Chromium: **43/43 PASS**, 0 pominiętych, w tym 41 wcześniejszych i 2 nowe testy etapu 4; czas 50,372 s.
- Matrix: **12/12 zgodnych porównań pikseli** z `92390b1`, cztery ekrany w trzech rozmiarach telefonu.
- Zgodność workera/paczki: **PASS**, release `3421843c0714c4ba7167e377`.
- Instalowalność desktopowa, rzeczywisty lokalny TLS, aktualizacje, restart procesu/offline i pełny backup/import: **PASS** w ramach zestawu Python.
- `git diff --check`: **PASS**.

CI używa dotychczasowego workflow regresji (push/PR), bez wdrażania. Wyniki najnowszego commitu są dostępne w Checks PR oraz [wykonaniach tej gałęzi](https://github.com/MixEEr0700/PushPull/actions/workflows/regression.yml?query=branch%3Afeature%2Fstage-4-name-and-architecture). Faktyczny wynik CI podaje końcowy raport zadania i opis PR; wynik lokalny nie zastępuje CI.

## Ryzyka i niewykonane testy

- **NIEWYKONANE:** fizyczny Android/WebAPK i zmiana etykiety istniejącej instalacji. Chromium potwierdza manifest/upgrade, nie zachowanie launchera; możliwe opóźnienie, monit lub skrócenie długiej nazwy. Nie odinstalowywać ani czyścić danych dla odświeżenia nazwy.
- Testy nie dowodzą zachowania każdego urządzenia przy utracie zasilania lub fizycznie pełnym dysku. Quota/abort są kontrolowane na granicy rzeczywistego API IDB.
- Zachowanie origin i identyfikatora chroni ciągłość instalacji; zmiana domeny/protokołu/portu/profilu wymaga eksportu/importu. IndexedDB i kopia na tym samym telefonie nie chronią przed czyszczeniem pamięci/utratą urządzenia. Zachowywać JSON poza urządzeniem.
- Niezapisane drafty pozostają w pamięci; zapisać przed świadomym zamknięciem wszystkich okien w celu aktualizacji. Cache starych wydań nadal zajmuje miejsce.
- Izolacja kont, migracja do modelu uniwersalnego, OAuth/sync, rozstrzyganie konfliktów i raport trenera wymagają dalszej implementacji/testów. Dokumentacja nie deklaruje gotowych funkcji.
- Nie uruchamiano hostingu, zgód Google, Drive, ręcznego workflow artefaktu ani instalacji Android. V2 nadal niezatwierdzony do codziennego użytku.
