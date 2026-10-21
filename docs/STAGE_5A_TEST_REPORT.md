# Etap 5A — raport kontroli audytu V2

Baza: `4540fa01441766280a80b60bda667e99a78a2711`, main po PR #4 (scalenie potwierdzone read-only przez GitHub). Gałąź `feature/stage-5a-v2-audit`. Zmieniono wyłącznie dokumentację w repozytorium `MixEEr0700/PushPull`.

## Zakres i status zadania

- [V2_PLAN_AUDIT_STAGE_5A.md](V2_PLAN_AUDIT_STAGE_5A.md): tabela 34 pozycji kodu, wszystkie obecne nazwy/kolejność/serie/target/initialKg oraz wspólne RIR/tempo/notes; źródła kodu, rozdzielenie zaleceń i wyników, macierz możliwości, lista decyzji D1–D8. **Porównanie oryginalnych parametrów niewykonane:** oba odczyty dokumentu Google zwróciły 401.
- [MODEL_EXTENSION_STAGE_5B_PROPOSAL.md](MODEL_EXTENSION_STAGE_5B_PROPOSAL.md): osobna propozycja celów serii, back-off, drop/grup i instrukcji, migracja chroniąca historię, zakres przyszłych testów. Bez implementacji, bez przypisania konkretnych parametrów V2.
- `README.md`, `docs/CODEX_HANDOFF.md`: odnośniki i jawny status blokady.
- `docs/STAGE_5A_TEST_REPORT.md`: ten raport.

Nie zmieniano runtime, aktywnego planu, ćwiczeń, ID, bazy, kluczy, kopii, Matrix/CSS, ikon, statystyk, manifestu ani tożsamości PWA. Nie uruchamiano hostingu/Drive/OAuth. Nie dodawano prywatnych wyników, dokumentu trenera ani sekretów do Git. Brak źródła nie jest zgodnością parametrów.

## Wykonywane polecenia

```sh
node --check app.js
node --check storage.js
node --check indexeddb.js
node --check sw.js
python3 scripts/build_release.py --check
node --test tests/storage.test.js
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
```

Inwentaryzacja: odczyt definicji `initialExercises` z kodu inicjalnego w izolowanym Node VM, bez wykonywania aplikacji i bez dostępu do magazynów użytkownika; 8+8+9+9=34 pozycji. Analiza możliwości obejmuje `storage.js` (walidacja), `indexeddb.js` (źródłowe rekordy i katalog) i `app.js` (edycja/podgląd/statystyki). Istniejące testy rzeczywistego Chromium pokrywają różne wykonane serie, tonaż, historię i ochronę danych. Nie dodano testów udających obsługę struktur, których aplikacja nie implementuje, ani prób importowania nowego modelu do aktywnej aplikacji.

## Wynik lokalny

21.10.2026, Node 24.19.0 / Python 3.12.14 / Playwright 1.62.0 / Chromium 154.0.8037.57:

- Składnia czterech plików JS: **PASS**.
- Świeżość workera i SHA-256 zasobów: **PASS**; runtime nie wymaga regeneracji.
- Testy Node: **43/43 PASS**, 0 pominiętych.
- Python/Chromium: **43/43 PASS**, 0 pominiętych, 44,210 s.
- Matrix: **12/12 porównań pikseli PASS** względem `92390b1` (4 widoki × 3 wymiary).
- W ramach regresji: migracja/abort/quota/retry i kontrola sukcesu po transakcji, pełny backup/import, różne serie, tonaż, edycja historii, restart procesu, offline, worker/update i lokalny zweryfikowany TLS: **PASS**.
- Kontrola dokumentacyjnej inwentaryzacji: **34/34** wiersze w kolejności kodu; ID, nazwy, sets, target i initialKg zgodne z inicjalizatorem. To kontrola przepisania kodu, nie weryfikacja zaleceń trenera.
- `git diff --check`: **PASS**. Runtime i historyczna specyfikacja bez zmian.

Logi lokalne pozostają poza repozytorium. GitHub Actions jest odrębnym wykonaniem; wynik konkretnego commitu podaje końcowy raport i opis PR. [Workflow tej gałęzi](https://github.com/MixEEr0700/PushPull/actions/workflows/regression.yml?query=branch%3Afeature%2Fstage-5a-v2-audit). Workflow nie wdraża aplikacji.

## Ograniczenia

- **NIEWYKONANE:** pełne porównanie z `v2. PushPull 01.07.2026`. `/edit` i `/export?format=txt`: HTTP 401, nie odczytano treści, nie potwierdzono nawet tytułu z metadanych. Tytuł podany przez właściciela. Potrzebny pełny PDF/DOCX z tabelami, legendą, przypisami oraz osobno istotnymi komentarzami, jeżeli nie są w eksporcie.
- Inwentaryzacja jest planem demonstracyjnym repo, nie prywatną bieżącą bazą osoby. Testy używają własnych danych syntetycznych i profili, nie historii telefonu.
- Dotychczasowe regresje nie dowodzą obsługi dropsetów, grup ani celów per seria. Braki stwierdzono analizą całej ścieżki danych; możliwość zachowania dodatkowego JSON nie jest obsługą semantyki.
- Fizyczny Android/WebAPK, zapełnienie rzeczywistego dysku i awarie sprzętu niewykonane. Testy błędów quota/abort kontrolowane na granicy API; widoki mobilne to desktopowy Chromium.
- V2 nadal niezatwierdzony do codziennego użytku. Audyt nie aktywuje poprawek ani modelu. Kolejne kroki wymagają źródła i rozstrzygnięć właściciela wskazanych w audycie.
