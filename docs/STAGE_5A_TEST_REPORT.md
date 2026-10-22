# Etap 5A — raport audytu po otrzymaniu DOCX

**Aktualny stan: kontynuacja z 22.10.2026 na końcu dokumentu — D1–D9 odnotowane, projekt 34 pozycji przygotowany; brak implementacji i aktywacji.** Wcześniejsze sekcje zachowują wyniki i ograniczenia uruchomienia z 21.10.2026.

Kontynuacja **tego samego PR #5** na `feature/stage-5a-v2-audit`. Baza aplikacji: `4540fa01441766280a80b60bda667e99a78a2711` (main po PR #4). Poprzedni commit audytu `8367333` zachowywał blokadę źródła; niniejsze uzupełnienie usuwa ją dzięki załącznikowi, bez zmiany aktywnego planu.

## Zmiany dokumentacji

- [V2_PLAN_AUDIT_STAGE_5A.md](V2_PLAN_AUDIT_STAGE_5A.md): pełne 34 lewe komórki źródła, 34 wiersze porównania i 34 odrębne wiersze techniki/komentarzy, legenda, lokalizatory, dokładne różnice, macierz M1–M8 i decyzje D1–D9. Nie ma już ogólnego „oryginał nieodczytany”.
- [MODEL_EXTENSION_STAGE_5B_PROPOSAL.md](MODEL_EXTENSION_STAGE_5B_PROPOSAL.md): projekt uwzględnia potwierdzone back-off, drop, cele per seria, parę z 15 s, strony i nieokreślone cele Brzucha/Łydki. To nadal osobny etap, bez implementacji/migracji.
- `README.md`, `docs/CODEX_HANDOFF.md`: aktualny status audytu.
- `docs/STAGE_5A_TEST_REPORT.md`: ten raport.

**Wyłącznie Markdown.** Runtime, ID, plan/parametry w aplikacji, IndexedDB/localStorage, historia, kopie, CSS/Matrix, statystyki, ikony, manifest, service worker i historyczny plan projektu są identyczne z początkiem kontynuacji PR. Nie wdrożono hostingu, OAuth/Drive ani usług zewnętrznych. Nie modyfikowano innych repozytoriów.

## Kontrole źródła i porównania

Załącznik: `v2. PushPull 01.07.2026.docx`, 17 017 bajtów, SHA-256 `53b52f86fff45b6df46820ac4b994e5ce1107e09cf951b44252a6c9c88aed01d`.

- ZIP odczytany i sprawdzony; `word/document.xml` zawiera 5 tabel o 7/8/8/9/9 wierszach. Wszystkie 34 pozycje odczytane. Brak obrazów, comments/footnotes/endnotes, tekstu ukrytego/przekreślonego i śledzonych zmian. W źródle nie ma dat/autorstwa zwykłych uwag C2.
- Porównanie obejmuje wszystkie nazwy/warianty, kolejność, serie, zakresy, RIR, tempo, back-off/drop/grupy i instrukcje. Każdy cytat zaleceń ma adres Tn/Rn/C1, uwagi osobno C2. Kolejność 34/34 zgodna.
- Potwierdzono pięć brakujących trzecich serii back-off, dwa „drop w każdej serii”, rozdzielone cele 12 oraz 15–20, parę dwóch ćwiczeń z przerwą 15 s. RIR 0 w 30 sparametryzowanych pozycjach; tempa 2111:14, 2010:14, 2011:1, 3111:1. Cztery Brzuch/Łydka bez lokalnych parametrów — brak uzupełniania po domyśle.
- Dzienników ciężarów z C2 nie przepisano do planu/historii. Cytowane przykłady i wzmianki liczbowe służą wyjaśnieniu semantyki, nie są nowym celem obciążenia. Pełny DOCX ani pełny dziennik nie trafiły do repo.
- Kontrola kompletności dokumentacji porównuje 34 pełne cytaty C1, ID i parametry kodu z odczytanymi obiektami oraz sprawdza tempa/RIR i krytyczne struktury. To kontrola przepisania i spójności audytu, nie test działania nieistniejącego silnika grup/dropsetów.

## Faktycznie wykonane testy lokalne — 21.10.2026

Narzędzia: Node 24.19.0, Python 3.12.14, Playwright 1.62.0, Chromium 154.0.8037.57. Testy używają izolowanych profili i danych syntetycznych, nie danych telefonu.

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

- Składnia czterech plików JS: **PASS**.
- Zgodność workera/hash zasobów: **PASS**; regeneracja niepotrzebna, runtime bez zmian.
- Node: **43/43 PASS**, 0 pominiętych.
- Python/Chromium: **43/43 PASS**, 0 pominiętych, 48,872 s.
- Matrix: **12/12 porównań pikseli PASS** względem `92390b1` (4 widoki × 3 wymiary telefonu).
- W ramach pełnej dotychczasowej regresji: serie/tonaż/edycja historii, migracja/abort/quota/retry, backup/import, sukces dopiero po oncomplete, kilka kart, restart procesu/offline, aktualizacje workera i lokalny zweryfikowany TLS: **PASS**.

Kontrola dokumentów: **PASS** — CRC całego ZIP, 34/34 pełne cytaty C1, ID/kolejność/pola kodu i odnośniki C2, liczniki temp/RIR oraz 5 back-off/2 drop/4 niesparametryzowane; lokalne linki rozwiązują się poprawnie. Kontrola zakresu: **PASS**, zmienionych wyłącznie 5 plików Markdown względem `8367333`. `git diff --check`: **PASS**. Wynik GitHub Actions dla nowego commitu jest odrębny od wyniku lokalnego; dostępny w [workflow gałęzi](https://github.com/MixEEr0700/PushPull/actions/workflows/regression.yml?query=branch%3Afeature%2Fstage-5a-v2-audit), Checks oraz aktualizowanym opisie PR. Workflow nie wdraża aplikacji.

## Ograniczenia i decyzje — stan 21.10.2026 przed ustaleniami właściciela

- **Odczyt załącznika i porównanie 34/34 wykonane.** HTTP 401 z poprzedniej próby Google Docs nie jest już blokadą tego audytu. Nie odczytano ewentualnych komentarzy internetowego oryginału, których nie ma w DOCX.
- Zapis technicznych uwag C2 nie zawiera autorów/dat i miesza wyniki z wariantami. Pierwszeństwo korekt, daty obowiązywania, drop-segmenty, konwencja stron/ciężarów i nieokreślone Brzuch/Łydka wymagają decyzji D1–D9; nie zgadujemy.
- Porównano kod inicjalnego planu w repo, nie prywatną bieżącą IndexedDB użytkownika. Zachowanie i identyfikatory historii pozostają nietknięte.
- **NIEZAIMPLEMENTOWANE i NIETESTOWANE jako gotowe funkcje:** model back-off/segmentów drop/grup/stron/przerw, cele per seria, oddzielne instrukcje oraz nowa migracja. Udane istniejące testy nie dowodzą ich działania; osobny etap modelu ma własne kryteria odbioru.
- Fizyczny Android/WebAPK, zapełnienie realnego dysku i awarie sprzętu nadal niewykonane. Quota/abort są kontrolowane na granicy API; mobilne widoki działają w desktopowym Chromium.
- Nie zatwierdzono aktywacji poprawionego V2 ani codziennego używania aplikacji. PR pozostaje do przeglądu, bez automatycznego scalania i bez publikacji.

## Kontynuacja — decyzje właściciela, 22.10.2026

Nowy zakres dokumentacyjny po commicie `7fb00f3`: zapis zatwierdzonych D1–D9 oraz pełnego uzupełnienia sekcji 3–5 dostarczonego w odpowiedzi właściciela. Koniec pierwotnego wklejonego pliku był ucięty; nie był rekonstruowany na podstawie domysłów. Uzupełnienie potwierdza ograniczenie do dokumentacji, bez nowego PR, scalenia lub aktywacji.

### Co uzupełniono

- `docs/V2_PLAN_AUDIT_STAGE_5A.md`: sekcja „Decyzje właściciela D1–D9”, rozróżnienie historycznej analizy DOCX i obecnych wyborów; stare pytania zastąpione stanem decyzji i odnośnikiem do faktycznie otwartych danych.
- `docs/V2_NEXT_PLAN_DRAFT_STAGE_5A.md`: nowa, **nieaktywna** tabela 34 pozycji PUSH A/PULL A/PUSH B/PULL B; osobne pochodzenie każdego z 10 wariantów D2 i relacja do C1/C2; pola serii/zakresów/RIR/tempa/struktur/instrukcji/statusu. Pięć istotnie zmienionych wariantów ma niepotwierdzone cele z odniesieniem do C1, cztery Brzuch/Łydka pozostają nieokreślone D1. Bez planowanego obciążenia z historii.
- `docs/MODEL_EXTENSION_STAGE_5B_PROPOSAL.md`: tożsamość ćwiczenia, wariant i pozycja rozdzielone; PUSH-A-4 otrzymał projekt odrębnej przyszłej tożsamości i mapowania pozycji, bez zmiany wyników dipów. Dodano D3–D9 i kolejność PR A–H (kontrakty, kopie, migracja, snapshoty, edytor/strony, drop, grupy, aktywacja) z osobnymi testami i bramkami.
- `README.md`, `docs/CODEX_HANDOFF.md`: aktualny stan decyzji i odnośnik do nowego projektu.
- `docs/STAGE_5A_TEST_REPORT.md`: niniejszy zapis kontynuacji; wcześniejsze wyniki pozostają opisem poprzedniego uruchomienia, nie zastępują poniższego.

### Co zachowano

Zmiany wyłącznie w sześciu plikach Markdown. Kod `app.js`, `indexeddb.js`, `storage.js`, CSS, mechanizmy zapisu, IndexedDB i kopie, plan aktywny, wszystkie ID i relacje, sesje, serie/wyniki, statystyki, notatki/technika, ikony/logo, PWA i oryginalna specyfikacja pozostają bez zmian. Pełne cytaty C1, źródłowe parametry i techniczne cytaty C2 pozostają oddzielone od decyzji właściciela. Nie przepisano historii do przyszłych wariantów, nie wygenerowano nowych faktycznych ID ani dat aktywacji. Nie zmieniano prywatności repo ani nie konfigurowano hostingu, Drive lub OAuth; nie modyfikowano innych repozytoriów.

### Faktycznie wykonana regresja

22.10.2026 (Europe/Warsaw), istniejące polecenia podane wyżej:

- Składnia czterech JS: **PASS**.
- Zgodność workera i SHA-256 runtime: **PASS**, bez regeneracji.
- Node: **43/43 PASS**, 0 pominiętych.
- Python/Chromium: **43/43 PASS**, 0 pominiętych, 48,272 s.
- Matrix: **12/12 porównań pikseli PASS**, oryginalny wzorzec `92390b1`.
- Zachowana cała regresja wyników, tonażu, historii, błędów migracji/zapisu, kopii/importu, restartu procesu, offline i aktualizacji PWA. Nie dodano testów udających implementację przyszłego modelu.

Kontrola spójności dokumentacji: **PASS**. Sprawdzono SHA-256/CRC źródła, zachowanie wszystkich 34 cytatów C1 i źródłowych pól audytu, niezmienione cytaty techniczne C2, 34 unikalne pozycje nowej tabeli z prawidłową jednostką/kolejnością, 10 wariantów zgodnych z listą właściciela, rejestr D1–D9, cztery odroczone i pięć niepotwierdzonych zestawów parametrów, cele/back-off/drop/rundy, odnośniki i lokalne kotwice. Plan etapów zawiera 8 osobnych kroków A–H. Kontrola zakresu: **PASS**, dokładnie sześć plików Markdown względem `7fb00f3`, runtime bez zmian. `git diff --check`: **PASS**. GitHub Actions dla nowego commitu jest osobnym wykonaniem; końcowy wynik podaje opis PR i raport zadania. Poprzednie zielone CI nie zastępuje nowego. Workflow nie wdraża aplikacji.

### Pozostałe bramki, bez ponownego otwierania D1–D9

- **O1**: tożsamość/rodzaj ruchu maszyny PUSH-A-4.
- **O2a–O2e**: potwierdzenie, czy źródłowe cele serii/zakresów/RIR/tempa nadal obowiązują dla istotnie zmienionych PUSH-A-4, PULL-A-1, PUSH-B-1, PULL-B-3 i PULL-B-5. Warianty są wybrane; ich automatyczne dziedziczenie parametrów nie jest zatwierdzone.
- **O3**: konkretna konwencja obciążenia dla przyszłych zapisów sprzętu. Legacy pozostaje nieznane bez przeliczeń.
- **D8**: osobne zlecenie implementacji nadal wymagane — zatwierdzono wyłącznie przygotowanie etapu. O1/O2 są dodatkowo bramką konkretnego nowego planu, nie powodem do zgadywania wartości na etapie ogólnego modelu. Aktywacja wyłącznie świadomą przyszłą operacją D7, nie w tym PR.

D1 świadomie odroczone, drop ma elastyczne segmenty D3, para ma dwie rundy/8–10/15 s D4, L/P i kopiowanie zatwierdzone D5, ochrona legacy-shared D6 i zachowanie nieostrych instrukcji D9 są ustalone. Nie prosimy ponownie o ich zatwierdzenie. Brak dawnego autorstwa/daty nie jest poleceniem ich odtworzenia.

Fizyczny Android/WebAPK, faktyczna implementacja nowego modelu/migracji/edytora/aktywacji i testy takich nowych funkcji nadal **NIEWYKONANE**; nie są zakresem tego PR. Dokumentacja nie dowodzi ich działania. Nie uruchomiono hostingu i nie scalono PR #5.
