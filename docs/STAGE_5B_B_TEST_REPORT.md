# Raport testów — etap 5B, krok B

Data: 22.10.2026. Baza: PR #6 / `063c02b5272ebb4066d498f82faf34e7353b588c`. Gałąź: `feature/stage-5b-b-backup-restore`. Zakres: trzy odseparowane moduły kopii, testy w istniejącym node:test i dokumentacja. Bez zmian CI i kontraktów kroku A. Format i granice: [BACKUP_STAGE_5B_B.md](BACKUP_STAGE_5B_B.md).

## Faktycznie wykonano lokalnie

| Kontrola | Wynik |
| --- | --- |
| `node --test tests/*.test.*` | **68/68 PASS**, 0 pominiętych: wcześniejsze 55 i 13 nowych testów kopii. |
| `python3 -m unittest discover -s tests -p 'test_*.py' -v` | **43/43 PASS**, 0 pominiętych; Chromium/Playwright. |
| `python3 scripts/build_release.py --check` | PASS: worker i hashe runtime zgodne. |
| `python3 scripts/build_release.py --output dist/stage5bb` | PASS: niezmienne wydanie `3421843c0714c4ba7167e377`; bez publikacji. |
| `node --check` dla runtime i modułów modelu/kopii | PASS. |
| `git diff --check` | PASS. |

Nowe 13 testów w `tests/backup.test.mjs` sprawdza:

1. Pełny round-trip v3 i ponowny eksport: wszystkie rekordy/ID, dwie wersje planu, historyczny snapshot, odrębność dipów i maszyny, back-off, segmenty, brak automatycznej zmiany obciążeń, instrukcje, notatki i pola dodatkowe. Odtworzenie tworzy odłączony, zamrożony model.
2. Odrębne wyniki dwóch członków superserii i dwóch rund, lewe/prawe strony, back-off oraz segmenty z różnymi ciężarami; porównanie całego payload przez deepEqual.
3. Zachowanie i objęcie hashem nieznanych pól obwiedni/integrity oraz kluczy opaque; brak zmiany prototypu.
4. Uszkodzony JSON, nieobsługiwana wersja, zmieniona instrukcja, brak wyników, błędne liczniki: błąd przed restore, nienaruszony stan źródłowy.
5. Duplikaty snapshotów/sesji/wyników/referencji, osierocone relacje, zła tożsamość, brakujące obowiązkowe rekordy/pola, zły owner i referencja notatki: jawne odrzucenie zamiast naprawy.
6. `uninterpreted` zachowuje przyszły zapis bez wymyślania snapshotu, wersji payload lub parametrów.
7. Podgląd oddzielony od restore, odrzucenie podrobionego podglądu, wymagane potwierdzenie zastąpienia izolowanego stanu, dokładna poprzednia kopia zwrócona przed przypisaniem nowego stanu. Wadliwa poprzednia kopia nie pozwala odtworzyć stanu.
8. v1 z istniejącego fixture oraz v2 z katalogiem wygenerowanym przez rzeczywisty obecny `PushPullDB.parseBackup`: pełne rekordy, katalog, archiwa, nieznane pola, dokładny tekst. Oba formaty przechodzą także opakowanie w v3 i odtworzenie bez konwersji.
9. Błędne stare relacje, duplikaty i wersje: odrzucenie bez zgadywania danych.
10. Rzeczywiste stare importery storage/IndexedDB odrzucają v3; próba starego commit nie wykonuje nawet zapisu kopii, historia pozostaje identyczna.
11. Duplikaty kluczy również z escape, zaokrąglane literały liczb, underflow, minus zero, undefined, NaN, Date, gettery: odrzucenie zamiast cichej utraty.
12. Jawnie kompletny pusty payload przechodzi; brak obowiązkowej kolekcji nie staje się pustą historią.
13. Import i pełny cykl nowych modułów przy pułapkach na indexedDB/localStorage/document/fetch przechodzi; runtime porównany bajtowo z bazą PR #6 pozostaje identyczny.

Wcześniejsza regresja obejmuje rotację, kalendarz, historyczną edycję, ręczne i powielane serie, tonaż, notatki, błędy zapisu/importu, migrację istniejącej bazy, quota/abort, wiele kart, ponowny start, offline i rzeczywiste aktualizacje service workera. **12 porównań pikselowych Matrix** z zatwierdzonym `92390b1` przeszło bez różnic; istniejące kontrole nazwy i tożsamości PWA również przeszły. Nie zmieniano bazowych obrazów ani tolerancji.

## GitHub Actions

Istniejący workflow `regression.yml` automatycznie obejmuje nowe `.test.mjs` oraz wcześniejsze testy Python. Nie dodano jobów ani zależności. Wyniki wykonania na aktualnym SHA są w kontrolach PR i końcowym raporcie/treści PR; lokalne wyniki powyżej nie są deklaracją wyniku CI.

## Ograniczenia i niewykonane operacje

- Testy wykonano na syntetycznych fixture, nie na prywatnej historii użytkownika. v2 ma rzeczywisty kształt eksportera, nie jest prywatnym eksportem z telefonu.
- Round-trip obejmuje pełny dostarczony graf i wszystkie dane opaque. Nie dowodzi semantycznej poprawności wnętrza przyszłych schematów wyników ani kompletności danych nieprzekazanych przez wywołującego.
- Nie testowano v3 na produkcyjnej IndexedDB, bo biblioteka nie ma operacji zapisu do niej. Nie przeprowadzono kroku C, nowej migracji, obsługi nowych transakcji ani integracji UI. Wcześniejsze testy IndexedDB dotyczą dotychczasowego, niezmienionego kodu.
- Nie wykonano testów fizycznego Androida/WebAPK ani nowego modułu w aktywnej PWA. Chromium nie jest fizycznym telefonem. UI aplikacji nie udostępnia jeszcze v3.
- Suma kontrolna nie uwierzytelnia autora. Nie zapisujemy automatycznie kopii poza przeglądarką; użytkownik przyszłej integracji musi móc ją pobrać i zachować. Duże pliki wymagają pamięci na kopie/serializację; przekroczenie zasobów kończy się błędem bez zapisu. Brak streamingu i arbitralnej obsługi precyzji liczb poza JSON/Number.
- Nie aktywowano V2, hostingu, Drive/OAuth ani kroków C–H. Repo prywatne; brak zmian bazy, kluczy, identyfikatorów, statystyk, mechanizmu tonażu, CSS, ikon i tożsamości PWA.
