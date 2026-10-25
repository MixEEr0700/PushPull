# Przygotowana treść PR

Tytuł: `perf: compare complete models without serializing raw archives`

Zapis pojedynczego wyniku ponownie serializował kompletne modele z archiwami raw przy CAS i odczycie kontrolnym. Zmiana zastępuje tylko te dwa porównania pełną równością wartości JSON, bez tworzenia escaped kopii raw. Nadal porównuje wszystkie pola i dokładny tekst źródeł; SHA, walidacja, strict complete, zapisy/readback, formaty i schemat pozostają bez zmian.

288 syntetycznych zapisów offline w Chromium, CPU ×4 (nie Pixel): mediana/p95 V2 + raw 4 MiB 1772/1918 → 1559/1680 ms; V2 40 + raw 4 MiB 10004/10668 → 9171/9892 ms; raw Unicode/escapes 16 MiB 6215/6462 → 4321/4672 ms. Duży V2 ma gorsze maksimum 10962 → 11766 ms. Cel <=1 s nie został osiągnięty i Issue #75 pozostaje otwarte. Nie ma pomiaru poprawki na fizycznym Androidzie.

- Zachowane: Matrix i oczekiwanie z #78, CAS, pełna walidacja, historia, plany, szkice, archiwa, backupy v1–v6, istniejące odtwarzanie i Google Drive. Bez resetu/migracji.
- Nowe testy: równoważność canonical, wielomegabajtowy raw bez serializacji, CAS przy podmienionym raw z tym samym digest i atomowe odrzucenie błędnego readback.
- Dodano izolowany benchmark, dowody pomiarowe i opcjonalny obserwator DevTools poza assetami aplikacji, bez zbierania rekordów ani inicjowania zapisów.
- Raport: `docs/DURABLE_WRITE_P0_REPORT.md`; osobny projekt dalszej architektury i ryzyka: `docs/DURABLE_WRITE_P0_PROJECT.md`. Większej przebudowy nie wdrożono; wymaga osobnego zatwierdzenia.

Weryfikacja lokalna: Node 185/185 PASS; Chromium/PWA 135/135 PASS (CAS, quota/abort, wiele kart, podwójne kliknięcia, restart szkiców, backupy, aktualizacje); kontrola SW i build produkcyjny PASS. CI bez zmian; brak płatnych runnerów. Pełny GitHub Actions zostaje uruchomiony przez ten PR; wynik i link do przebiegu zostaną uzupełnione po jego zakończeniu. Wymagany PASS przed scaleniem. Nie scalać automatycznie.

Refs #75, #73.
