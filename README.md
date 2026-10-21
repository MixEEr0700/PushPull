# Aplikacja Treningowa

Mobilny dziennik treningowy offline, rozwijany w istniejącym repozytorium `MixEEr0700/PushPull`. Zachowany interfejs Matrix v0.3 — szlif 3, lokalna baza IndexedDB i pełne kopie JSON. Nazwa aplikacji nie zmienia technicznych identyfikatorów ani historii.

**Wersja testowa:** parametry V2 wymagają potwierdzenia z dokumentem trenera. Instalacja na fizycznym Androidzie pozostaje niewykonana. Obecnie dane rozdziela origin/profil przeglądarki; nie ma kont użytkowników ani synchronizacji Drive.

## Uruchomienie i testy

Python 3.12, Node 24; brak zależności npm. Zależności testów przeglądarkowych:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -m playwright install --with-deps chromium
node --test tests/storage.test.js
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/releases/stage-4
python3 scripts/serve_test.py --directory dist/releases/stage-4 --port 8000
```

Serwer nasłuchuje lokalnie; nie aktywuje hostingu HTTPS. Każde wydanie budować do nowego katalogu. Nie publikować checkoutu, backupów ani sekretów. Pełne JSON zachowywać także poza przeglądarką. Nazwy plików kopii `pushpull-*` i format kopii pozostają kompatybilne.

## Dokumentacja

- [Audyt V2 — etap 5A](docs/V2_PLAN_AUDIT_STAGE_5A.md): uzupełniony z DOCX, 34/34 pozycje; rozbieżności i decyzje przed wdrożeniem; [raport kontroli](docs/STAGE_5A_TEST_REPORT.md).

- [Plan historyczny](PushPull_PLAN_PROJEKTU_v1.md) i [aneks etapu 4](docs/PROJECT_PLAN_ANNEX_STAGE_4.md).
- [Architektura docelowa, model, migracja, Drive i hosting](docs/TARGET_ARCHITECTURE_STAGE_4.md).
- [Ochrona danych](docs/DATA_SAFETY_STAGE_1.md), [IndexedDB i odzyskiwanie](docs/INDEXEDDB_MIGRATION_STAGE_2.md).
- [Testowe HTTPS](docs/PWA_TEST_DEPLOYMENT_STAGE_3.md), [instalacja i testy Androida](docs/ANDROID_TEST_CHECKLIST.md).
- [Raport etapu 4](docs/STAGE_4_TEST_REPORT.md), [przekazanie](docs/CODEX_HANDOFF.md), [zasady pracy](AGENTS.md).

Zachowany [poprzedni README](docs/README_BEFORE_STAGE_4.md) dokumentuje stan sprzed importu źródeł; nie opisuje aktualnych możliwości aplikacji.
