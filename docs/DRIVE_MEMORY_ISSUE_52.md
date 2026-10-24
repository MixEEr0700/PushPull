# Issue #52 — awaria renderera podczas ręcznej kopii Drive

Baza: `main` `279bc2e` po PR #49. Wyłącznie syntetyczne, tymczasowe profile; bez konta, kopii i danych właściciela. Issues #50/#51 poza zakresem. Pomiary: Chromium 154.0.8037.57, Playwright 1.62.0, Debian x86_64 (nie Android); Node 24.19.0, Python 3.12.14.

## Co potwierdzono, a czego nie

**Potwierdzony defekt w reprodukcji:** po prawidłowym eksporcie, POST i GET końcowe `same(node, verified)` ponownie kanonizowało całe oba opakowania. Dla dużego, wielokrotnie escapowanego tekstu tworzyło kolejne ogromne ciągi JSON. Przy ograniczeniu V8 do 768 MiB renderer Chromium ulegał awarii właśnie między zakończeniem `readNode` a końcem tego porównania. Ten sam syntetyczny profil po małej poprawce kończy zapis i weryfikację. Próba bez checkpointów w źródle także: przed poprawką `renderer-crash` / `not-verified`, po poprawce `verified`; po ponownym otwarciu `localUnchanged: true` w obu przypadkach.

**Nie ustalono przyczyny konkretnej awarii fizycznego Androida.** Brak crash dumpu, informacji o limicie pamięci i wielkości jego kopii. W naszej reprodukcji POST zdążył zapisać plik; właściciel nie widział nowej kopii. Nie należy utożsamiać tych obserwacji ani ogłaszać pełnego rozwiązania każdego przypadku „Kurza twarz!”. Pamięć jest potwierdzonym problemem odtworzonej ścieżki, ale pozostaje hipotezą dla konkretnego telefonu.

## Ścieżka i mała poprawka

1. `exportModelBackup` weryfikuje źródło/model i eksportuje pełny v3, wraz z archiwami. Nie zapisuje nowego archiwum.
2. `makeNode` weryfikuje v3 i wylicza SHA-256 całego kanonicznego opakowania (bez pola digest).
3. `transport.create` serializuje opakowanie w multipart i wykonuje POST; żaden poprzedni plik nie jest kasowany.
4. `readNode` pobiera konkretny plik, sprawdza format, wersję, ID, parents, digest zgodny z wysłanym oraz ponownie wylicza SHA-256 **całego** odebranego body i waliduje pełny backup.
5. Zamiast kolejnego `canonical(node) === canonical(verified)` porównujemy dokładny tekst `backup` i `digest`. Kontrola całego body jest już wykonana w pkt 4 — obejmuje też datę i dodatkowe pola. Nie wyłączono walidacji, hashy ani kontroli źródła. Komunikat sukcesu nadal następuje dopiero po GET i wszystkich kontrolach.

Jedyna zmiana działania to usunięcie dwóch zbędnych serializacji z ostatniego porównania. Format starych/nowych plików, eksport, IndexedDB, archiwa, dane, ręczny tryb, UI/Matrix oraz offline pozostają bez zmian. `sw.js` odświeżono generatorem.

## Rozmiar i archiwa

W jednym syntetycznym profilu V2 bez dodawania treningów:

| Liczba przywróceń tej samej bazy | Archiwa w eksporcie | Rozmiar v3 (bajty) |
| --- | ---: | ---: |
| 0 | 2 | 378 116 |
| 1 | 3 | 922 851 |
| 2 | 4 | 2 925 821 |
| 3 | 5 | 11 499 261 |
| 4 | 6 | 51 483 641 |

Przywrócenie zabezpiecza poprzednią pełną bazę; jej dokument zawiera już wcześniejsze archiwa w `legacySources.raw`. Następna serializacja ponownie escapuje cudzysłowy/backslashe. **To zagnieżdżanie preimage, nie kolejne ręczne zapisy Drive, powoduje obserwowany wzrost.** Trzy ręczne kopie bez zmiany bazy miały każda 378 116 B v3 / 459 592 B opakowania; archiwa i dane lokalne nie zmieniły się. Niczego nie usuwamy ani nie kompaktujemy.

Dla 4 przywróceń opakowanie Drive miało 99 067 117 B (sam v3: 51 483 641 B). Bez ograniczenia sterty zapis starego kodu kończył się poprawnie, ale w jednym pomiarze ostatnie porównanie zwiększyło raportowaną stertę z ok. 792 MB do 1 287 MB. Agregowany RSS rendererów sięgał ok. 1,7–2,2 GB w próbach dużej kopii. Osobny profil z dodatkiem 16 MiB bez zagnieżdżonych archiwów również działał, przy chwilowej stercie ponad 600 MB. Nie ma podstaw do wyznaczenia uniwersalnej „bezpiecznej wielkości kopii”.

Odczyty `performance.memory` z flagą precyzyjnego pomiaru i RSS są checkpointami, nie ciągłym pomiarem szczytu. RSS sumuje własne procesy rendererów (w tym współdzielone strony); nie jest pomiarem RAM Androida. Limit `--max-old-space-size` ogranicza V8, nie emuluje Androidowego zabijania procesów. Mniejsze limity 128/256/512 MiB dla niektórych profili powodowały awarię już przy otwieraniu bazy; wykluczono je jako reprodukcję samego uploadu.

## Powtarzalna diagnostyka

`tests/drive_backup_probe.py` korzysta z istniejących Playwright/Chromium i serwera testowego. Zawsze tworzy własny tymczasowy profil i lokalny serwer udający Drive, z syntetycznym OAuth. Nie ma opcji wskazania profilu, pliku kopii lub konta właściciela. Nie loguje treści treningów ani tokenów — tylko etapy, wielkości, liczniki, wynik i zgodność lokalnego stanu. Duże próby są opt-in, poza normalną regresją unittest.

```sh
python3 tests/drive_backup_probe.py --copies 3
python3 tests/drive_backup_probe.py --opaque-mib 16
# Stary moduł: oczekiwana awaria w odtworzonych warunkach (wynik zależy też od Chrome/GC).
python3 tests/drive_backup_probe.py --restore-cycles 4 --heap-mib 768 --drive-ref 279bc2e --no-trace
# Moduł z poprawką: w wykonanej próbie verified / localUnchanged: true.
python3 tests/drive_backup_probe.py --restore-cycles 4 --heap-mib 768 --no-trace
```

Bez `--no-trace` skrypt dodaje wyłącznie checkpointy do serwowanego modułu (nie do plików aplikacji). POST/GET odbywają się przez natywny HTTP; skrypt nie pobiera wielkiego `request.post_data` przez DevTools. W pierwotnej próbie z przechwytywaniem ok. 100 MB przez API Playwright wystąpił timeout — nie zaliczono go do awarii produktu. Kod wyjścia 0 oznacza zweryfikowany zapis i niezmieniony stan lokalny; 1 oznacza brak potwierdzenia lub błąd próby.

## Regresja i ograniczenia

- Test Node limituje ponowną serializację pełnego backupu **po** kompletnej weryfikacji readback. Na `279bc2e` kończy się błędem alokacji; po poprawce przechodzi, z niezmienioną treścią kopii. Sprawdza rzeczywisty `upload`, bez atrap hashy/walidacji.
- Chromium: trzy ręczne kopie v3 >1 MiB z zapisanym wynikiem, snapshotem i lokalnym szkicem. Pełny fingerprint bazy, archiwów, rewizji, szkiców i ustawień Drive pozostaje identyczny; stare pliki bez zmian, brak wzrostu rozmiaru po samych uploadach; restart zachowuje stan.
- Istniejące testy: offline, wygaśnięta autoryzacja, błąd POST, błąd GET/weryfikacji, zmiana lokalna podczas uploadu. Uzupełniono utratę odpowiedzi po POST: plik może już istnieć, brak sukcesu i automatycznej powtórki; następny ręczny zapis dodaje osobny plik.
- Pełne wyniki Node, Chromium, buildu i GitHub Actions są w PR.

Poprawka usuwa konkretny odtworzony pik pamięci. Nie zmniejsza samych kopii ani kosztu wcześniejszego eksportu/walidacji, multipart i GET. Bardzo duże archiwa mogą nadal wyczerpać pamięć wcześniej. Bez fizycznego Androida i realnego Google nie można potwierdzić usunięcia pierwotnej awarii właściciela; potrzebny jest kontrolowany odbiór i ewentualnie beztreściowe informacje o wersji Chrome, rozmiarze kopii i przyczynie zakończenia procesu. Nie sugerujemy resetowania, usuwania historii/archiwów ani odinstalowania aplikacji.
