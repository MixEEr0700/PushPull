# Etap 3 — raport automatycznych testów PWA

Baza: `120b854`, gałąź `feature/stage-3-pwa-deployment`. Sprawdzono prywatność repozytorium i wyłączone Pages przez read-only API. Nie aktywowano hostingu.

## Polecenia

```sh
node --check app.js
node --check storage.js
node --check indexeddb.js
node --check sw.js
node --test tests/storage.test.js
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/ci
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Narzędzia: Node 24.19.0, Python 3.12.14, Python Playwright 1.62.0 i Chromium 154.0.8037.57. Instalacja zależności testowych jest opisana w raporcie etapu 2. Ikony można wiernie odtworzyć z zachowanego `icon.svg` przez `python3 scripts/render_icons.py` (Playwright/Chromium). Regeneracja runtime wymaga odświeżenia workera; CI wykrywa stary `sw.js`.

## Nowe kontrole

| Obszar | Wykonany test |
| --- | --- |
| Paczka | Deterministyczna generacja, zgodność workera i wszystkich SHA-256, wyłącznie jawna lista runtime, powtórna identyczna budowa, odmowa nadpisania nieznanego backupu lub zmienionej paczki, odmowa serwowania checkoutu. |
| HTTPS | Lokalny rzeczywisty TLS z tymczasowym certyfikatem/kluczem i jawnym zaufaniem klienta do testowego CA. Weryfikacja łańcucha/hosta pozostaje włączona. Sprawdzono MIME, cache headers, CSP, HSTS, nosniff i zakaz dostępu do źródeł/fixture'ów/backupów oraz POST. |
| Manifest | Parsowanie przez Chromium, `id` zgodny z dawnym implicit ID, start URL, scope, standalone; diagnostyka CDP `Page.getInstallabilityErrors` w zwykłym trwałym profilu, nie incognito. To diagnostyka desktopowa, nie instalacja na Androidzie. |
| Ikony | Podpis i wymiary PNG 192/512, pełna nieprzezroczystość maskable 512 i pozostawienie całego symbolu w centralnej strefie bezpiecznej 80%. SVG oraz kolory/kształt oryginalnej ikony zachowane. |
| Podkatalog / CSP | Paczka działa przy `/PushPull/`, rejestruje odpowiedni scope, otwiera się offline, eksportuje i importuje pełny JSON z rzeczywistymi nagłówkami serwera. |
| Kilka kart / draft | Nowy worker rzeczywiście osiąga stan installed/waiting, nie przeładowuje formularza ani ręcznie zmienionej serii. Zamknięcie jednej z dwóch kart nie aktywuje aktualizacji. Po zapisaniu pracy i zamknięciu ostatniej karty nowy worker aktywuje się, a historia/kopie pozostają identyczne. |
| Nieudane wydanie | Brak `app.js` i odpowiedź 200 z innym HTML/loginem powodują rzeczywiste odrzucenie instalacji. Poprzednia wersja nadal startuje offline z tą samą historią. |
| Aktualizacja z etapu 2 | Rzeczywiste pliki i worker commitu `120b854` → paczka etapu 3. Sprawdzono całą historię, katalog wersji, archiwalne kopie i dokładny oryginał localStorage po aktualizacji oraz offline. |
| Restart procesu | Trwały profil Chromium zamknięto, uruchomiono nowy proces, ustawiono offline jeszcze przed otwarciem strony. PWA działa z cache, a pełna kopia danych pozostaje identyczna. |
| Usunięty zasób cache | Brak pliku daje 503 offline, bez resetu danych. Po powrocie online brakujący zasób jest naprawiany tylko po zgodności SHA-256 i aplikacja wraca z tą samą historią. |

Zachowano wszystkie 43 testy warstwy danych oraz wcześniejsze 30 scenariuszy przeglądarkowych, w tym migrację z błędem i ponowieniem offline. Oczekiwanie workera dostosowano do bezpieczniejszej polityki: zamknięcie starych klientów zamiast wymuszonego `skipWaiting`. W testach nie wyłączano CSP ani sprawdzania certyfikatów. Diagnostyka instalowalności działa w osobnym zwykłym profilu; incognito z założenia nie pozwala instalować PWA.

Porównanie Matrix nadal używa dokładnego kodu `92390b1`: trening, rozwinięta karta, statystyki i kalendarz w 360×800, 390×844 i 412×915. Nie generuje zastępczej makiety ani nowych wzorców na podstawie zmienionej aplikacji.

## Granice wyniku

- Testy workerów/przeglądarki używają rzeczywistego Chromium i bezpiecznego dla przeglądarki loopback HTTP. Osobny test sprawdza rzeczywisty weryfikowany TLS. Nie jest to test publicznego certyfikatu, Tailscale ani Chrome na telefonie.
- Nie wykonano fizycznej instalacji Android/WebAPK, sprawdzenia dotyku/klawiatury/baterii, dostępu przez VPN telefonu, rzeczywistej presji dysku ani awarii sprzętu.
- Nie uruchomiono hostingu, ręcznego workflow artefaktu ani publicznego wdrożenia. CI regresji jest uruchamiane osobno dla commitów/PR, bez deploy.
- Weryfikacja nie zatwierdza demonstracyjnych parametrów V2 do codziennego użytku.

Fizyczne testy i instrukcja: [ANDROID_TEST_CHECKLIST.md](ANDROID_TEST_CHECKLIST.md). Hosting/prywatność/koszty: [PWA_TEST_DEPLOYMENT_STAGE_3.md](PWA_TEST_DEPLOYMENT_STAGE_3.md).

## Wynik lokalny — 21.10.2026

- Składnia `app.js`, `storage.js`, `indexeddb.js`, `sw.js`: **PASS**.
- Warstwa danych: **43/43 PASS**, 0 pominiętych.
- Python/Chromium: **41/41 PASS**, 0 pominiętych (30 wcześniejszych + 11 nowych testów PWA/paczki/HTTPS).
- Diagnostyka `Page.getInstallabilityErrors` w zwykłym profilu Chromium: **brak błędów**. Nie jest to dowód instalacji WebAPK na Androidzie.
- Matrix: **12/12 zgodnych porównań pikseli**.
- Budowa/zgodność workera, pełna lista runtime i testy HTTPS: **PASS**.
- `git diff --check`: **PASS**. `style.css`, `icon.svg`, `storage.js` i `indexeddb.js` identyczne z bazą etapu 3; model bazy i V2 nie zostały zmienione.

CI: [workflow regresji](https://github.com/MixEEr0700/PushPull/actions/workflows/regression.yml?query=branch%3Afeature%2Fstage-3-pwa-deployment) sprawdza składnię, paczkę, Node i cały zestaw Python. Aktualny wynik konkretnego commitu jest widoczny w Checks PR i raporcie końcowym zadania; wynik lokalny nie zastępuje CI. Ręcznego workflow pakowania artefaktu i docelowego hostingu nie uruchamiano.
