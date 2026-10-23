# Issue #45 — trzy kroki przywracania

Baza: `main` po PR #42 (`f3b403b`). Wyłącznie usprawnienie prezentacji istniejącego przywracania.

1. **Wybierz kopię** — lista zachowanych plików Drive, bezpośrednio pod nią główna akcja **Wybierz tę kopię**. Wybór pobiera i waliduje wyłącznie podgląd.
2. **Podgląd przed przywróceniem** — krótkie porównanie liczby planów, treningów i wyników w obu bazach. Jawne ostrzeżenie o zastąpieniu, bez scalania, oraz o lokalnych szkicach. Szczegółowe daty, nazwy planów, snapshoty, aktywacje i różnice nadal są dostępne po rozwinięciu szczegółów.
3. **Potwierdź przywrócenie** — **Przywróć wybraną kopię** i **Anuluj** obok siebie. Osobne dotychczasowe potwierdzenie systemowe pozostaje obowiązkowe. Bez zweryfikowanego podglądu nie ma przycisku przywracania.

Fokus i przewinięcie kierują do bieżącego kroku, bez wyszukiwania akcji pod długim zestawieniem. Podczas zatwierdzania przyciski są niedostępne. Anulowanie zamyka wybór/podgląd, bez zmiany danych. Ten sam krótki podgląd służy również plikom JSON.

Bez zmian CSS, Matrix, nawigacji, backendu Drive, formatu kopii, walidacji, IndexedDB, preimage, ochrony rewizji/localStorage i szkiców. Nie zmieniono treningów, planów ani mechanizmu zapisu. Poprzednia dokumentacja bezpieczeństwa: [Issue #40](BACKUP_RESTORE_ISSUE_40.md).

Weryfikacja: istniejąca regresja Node i Chromium oraz nowy test przepływu na 390×844, 360×640 i 1280×800: widoczność akcji, brak zapisu przy wyborze, anulowanie podglądu i potwierdzenia, brak poziomego przewijania. Pełne wyniki w PR. Symulowany Google Drive; w tym PR nie przeprowadzano nowego testu rzeczywistego konta ani fizycznego Androida. Issue #45 odnotowuje osobno wcześniejszy, udany test właściciela PC ↔ telefon.
