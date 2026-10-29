# Aplikacja Treningowa

Mobilny dziennik treningowy offline, rozwijany w istniejącym repozytorium `MixEEr0700/PushPull`. Zachowany interfejs Matrix v0.3 — szlif 3, lokalna baza IndexedDB i pełne kopie JSON. Nazwa aplikacji nie zmienia technicznych identyfikatorów ani historii.

**Wersja testowa:** parametry V2 wymagają potwierdzenia z dokumentem trenera. Instalacja na fizycznym Androidzie pozostaje niewykonana. Obecnie dane rozdziela origin/profil przeglądarki; nie ma kont użytkowników ani synchronizacji Drive.

## Uruchomienie i testy

Python 3.12, Node 24; brak zależności npm. Zależności testów przeglądarkowych:

```sh
python3 -m pip install -r tests/requirements.txt
python3 -m playwright install --with-deps chromium
node --test tests/*.test.*
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --output dist/releases/stage-4
python3 scripts/serve_test.py --directory dist/releases/stage-4 --port 8000
```

Serwer nasłuchuje lokalnie; nie aktywuje hostingu HTTPS. Każde wydanie budować do nowego katalogu. Nie publikować checkoutu, backupów ani sekretów. Pełne JSON zachowywać także poza przeglądarką. Nazwy plików kopii `pushpull-*` i format kopii pozostają kompatybilne.

## Dokumentacja

- [Szybki rozruch na bazie etapu C](docs/FAST_START_ISSUE_82.md): pomiary etapów, odroczony audyt raw, integralność grafu live i bezpieczna aktualizacja root.

- [Zapis przyrostowy IndexedDB v2 — Issue #82](docs/INCREMENTAL_WRITE_STAGE_C.md): integracja z Matrix, aktualizacja z checkpointem, rzeczywisty strict complete oraz syntetyczne pomiary przed/po. Osobne etapy [A](docs/INCREMENTAL_WRITE_STAGE_A.md) i [B](docs/INCREMENTAL_WRITE_STAGE_B.md); odbiór na fizycznym Androidzie pozostaje osobny.

- [Trwały zapis — etap B](docs/DURABLE_WRITE_STAGE_B.md): implementacja, natywne pomiary przed/po i [projekt zapisu przyrostowego](docs/INCREMENTAL_WRITE_P0_DESIGN.md).

- [Pierwsza reakcja i trwały zapis — Issue #75](docs/UI_RESPONSIVENESS_ISSUE_75.md): rozdzielone pomiary, bezpieczny stan oczekiwania i projekt dalszego usprawnienia.

- [Responsywność Androida — Issue #73](docs/ANDROID_RESPONSIVENESS_ISSUE_73.md): pomiary na syntetycznej historii, ograniczenia i scenariusz weryfikacji telefonu.

- [Dziennik — pierwsza część funkcjonalna](docs/FUNCTIONAL_JOURNAL_PART_1.md): świadome włączenie, sesje ze snapshotem, serie, kalendarz i pełne odtwarzanie v3; bez aktywacji nowego V2 i edytorów struktur specjalnych.

- [Minimalna migracja — etap 5B / krok C](docs/MINIMAL_MIGRATION_STAGE_5B_C.md): jawna migracja testowa, wspólny transakcyjny zapis i najkrótsza ścieżka do telefonu.

- [Pełne kopie nowego modelu — etap 5B / krok B](docs/BACKUP_STAGE_5B_B.md): działające API v3, bezstratny odczyt v1/v2 i odtworzenie w pamięci; bez migracji i podłączenia do aplikacji.

- [Model danych — etap 5B / krok A](docs/DATA_MODEL_STAGE_5B_A.md): odseparowane kontrakty i walidacja; bez podłączenia do treningu, migracji i aktywacji.

- [Audyt V2 — etap 5A](docs/V2_PLAN_AUDIT_STAGE_5A.md): zakończone porównanie DOCX 34/34 i rejestr decyzji właściciela D1–D9; [raport kontroli](docs/STAGE_5A_TEST_REPORT.md).

- [Projekt przyszłego planu — 34 pozycje](docs/V2_NEXT_PLAN_DRAFT_STAGE_5A.md): wybrane warianty, źródła parametrów i jawne otwarte pola; bez aktywacji.

- [Plan historyczny](PushPull_PLAN_PROJEKTU_v1.md) i [aneks etapu 4](docs/PROJECT_PLAN_ANNEX_STAGE_4.md).
- [Architektura docelowa, model, migracja, Drive i hosting](docs/TARGET_ARCHITECTURE_STAGE_4.md).
- [Ochrona danych](docs/DATA_SAFETY_STAGE_1.md), [IndexedDB i odzyskiwanie](docs/INDEXEDDB_MIGRATION_STAGE_2.md).
- [Testowe HTTPS](docs/PWA_TEST_DEPLOYMENT_STAGE_3.md), [instalacja i testy Androida](docs/ANDROID_TEST_CHECKLIST.md).
- [Raport etapu 4](docs/STAGE_4_TEST_REPORT.md), [przekazanie](docs/CODEX_HANDOFF.md), [zasady pracy](AGENTS.md).

Zachowany [poprzedni README](docs/README_BEFORE_STAGE_4.md) dokumentuje stan sprzed importu źródeł; nie opisuje aktualnych możliwości aplikacji.

Etap E (Issue #88), indeksy kontekstów i przyrostowe komendy sesji: [kontrakt, bezpieczeństwo i odbiór Pixel 9](docs/FAST_START_STAGE_E_ISSUE_88.md). Zależność: niescalony PR #87, bez zmiany Matrix i formatów kopii.

Raport zakładki Dane: [Issue #90](docs/DATA_TAB_ISSUE_90.md).

- [Compact Matrix v0.4 — etap F, testy i ograniczenia](docs/COMPACT_MATRIX_STAGE_F.md)
- [Uproszczenie Dane — etap G, bezpieczeństwo i pomiary](docs/SIMPLE_DATA_STAGE_G.md)
- [Compact Matrix v0.4 — szlif kart, Issue #95](docs/COMPACT_MATRIX_ISSUE_95.md)
- [Compact Matrix v0.4 — końcowy szlif i analiza wspólnych notatek](docs/COMPACT_MATRIX_FINAL_POLISH.md)

- [Kompaktowy edytor serii — Issue #99: L/P, segmenty, testy i pomiary](docs/COMPACT_EDITOR_ISSUE_99.md)

- [Odtwarzanie L/P i dowolne segmenty dropsetu — Issue #101](docs/COMPACT_EDITOR_ISSUE_101.md)

- [Prezentacja wyników, bezpieczne szybkie pola i przyrostowy zapis notatek](docs/RESULTS_NOTES_POLISH.md)
