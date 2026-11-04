# PushPull 01.07.2026

Plik `PushPull-01.07.2026.json` jest planem do istniejącego importera `pushpull-plan v1`, a nie kopią danych ani automatyczną aktualizacją aktywnego planu.

W aplikacji z tego commitu: **Dane → Plany treningowe → Importuj nowy plan**, wybierz JSON, sprawdź podgląd, zapisz plan bez aktywacji, następnie wybierz zapisany plan i jawnie aktywuj dla przyszłych treningów. Nie usuwa to dotychczasowych sesji ani nie zmienia ich parametrów. Nie stosować tego pliku w starszej wersji aplikacji, która nie obsługuje opcjonalnego pola `initialUserNotes` — starszy importer odrzuci plik zamiast zgubić notatki.

35 pozycji ma odrębne exerciseId/variantId/positionId, także przy identycznych nazwach. Nie ma przenoszenia wyników ani wpisanych ciężarów. Cztery jednostki: Push A, Pull A, Push B, Pull B (8/8/9/10). Konwencja ciężaru pozostaje nieokreślona zamiast zgadywania masy na hantel lub łącznej. Importer może z tego powodu pokazać ostrzeżenie o nieustalonych parametrach.

`initialUserNotes` zawiera 16 zatwierdzonych notatek. Importer przyjmuje je wyłącznie dla nowych tożsamości ćwiczeń z tego samego pliku i tworzy zwykłe edytowalne `userNotes`; nie zmienia instrukcji trenera ani istniejących notatek. Brak notatki oznacza puste pole.

Brzuch i łydki mają jedną serię z nieokreślonymi powtórzeniami/RIR/tempem. Pusta seria jest celem w planie, nie wykonanym wynikiem. Nie należy zapisywać jej z wymyślonymi wartościami; istniejąca walidacja wyniku nadal wymaga rzeczywiście wpisanych wartości. BO, DS i para 6a/6b korzystają wyłącznie z istniejących struktur i edytora.

Źródła zatwierdzonych parametrów: `docs/PushPull_01.07.2026_SPECYFIKACJA.md` oraz mechanicznie wyodrębnione wiersze `docs/plan-01-07-2026-extracted.json`. Nie wykonano resetu ani instalacji planu na urządzeniu użytkownika. Robocze rozważania czystego startu są poza zakresem tego artefaktu.
