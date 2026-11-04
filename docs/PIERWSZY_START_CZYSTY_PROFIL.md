# Jednorazowy start czystego dziennika na Pixelu 9

Ta procedura wykorzystuje istniejącą aplikację. Nie uruchamia żadnego resetu automatycznie. Stary profil pozostaje nietknięty; nie usuwaj ręcznie magazynów IndexedDB, danych witryny ani punktów Drive. Wykonanie poniższych działań na telefonie wymaga osobnej, świadomej decyzji właściciela.

## 1. Niezależna kopia i sprawdzenie

1. W dotychczasowym profilu zamknij inne karty aplikacji i zapisz lub zakończ edycję. Nie zakładaj, że kopia obejmuje niezapisane dane pozostające wyłącznie w pamięci innej karty.
2. Wybierz **Dane → Zapisz kopię → Pobierz kopię na urządzenie**. Poczekaj na komunikat zlecenia pobrania i w aplikacji Pliki sprawdź, czy plik faktycznie powstał i ma niezerowy rozmiar.
3. Skopiuj plik PPC1 poza telefon, np. na komputer lub nośnik. Zachowaj także oryginał. Nie polegaj na punkcie cofnięcia znajdującym się w tej samej bazie co dane.
4. W aplikacji wybierz **Dane → Przywróć kopię → Z pliku**, wskaż niezależnie zachowany plik i poczekaj na weryfikację oraz podgląd. Porównaj liczbę treningów, wyników, planów i szkiców z dotychczasowym stanem. **Anuluj podgląd; nie zatwierdzaj przywracania.** Błąd lub rozbieżność wstrzymuje dalsze kroki. Dla pewności możliwość odtworzenia można sprawdzić w osobnym, pustym profilu testowym: przywrócić tam plik, uruchomić ponownie i porównać dane. Sam podgląd nie dowodzi, że wykonano pełny test przywrócenia.
5. PPC1 kanoniczny przechowuje dane treningowe i trwałe szkice, ale nie jest fizycznym obrazem wszystkich technicznych archiwów ani lokalnych punktów cofnięcia. Jeśli są potrzebne osobno, pobierz dostępne punkty przez **Dane → Punkty cofnięcia**, zachowaj poza telefonem i sprawdź podgląd każdego pliku. Nie usuwaj oryginałów ani kopii Drive.

## 2. Osobny pusty profil

1. Po sprawdzeniu kopii i osobnym potwierdzeniu właściciela w ustawieniach Androida włącz wielu użytkowników, jeśli funkcja jest dostępna, i utwórz **nowego użytkownika telefonu**. Jest to osobny profil Androida, nie tryb incognito Chrome. Jeśli urządzenie lub polityka zarządzania nie pozwala go utworzyć, zatrzymaj procedurę; nie zastępuj jej kasowaniem danych starego profilu.
2. Przełącz się na nowego użytkownika, otwórz Chrome i ten sam adres aplikacji, a następnie zainstaluj ją na ekranie głównym. Profil ma własne dane przeglądarki i aplikacji. Nie importuj starej kopii i nie wybieraj starego punktu Drive jako bieżącej historii.
3. Otwórz kalendarz i statystyki: potwierdź brak sesji, wyników i szkiców oraz początkową rotację. Uruchom ponownie aplikację i sprawdź ponownie. Jeśli widzisz wcześniejsze wyniki, przerwij: prawdopodobnie otwarto poprzedni profil albo przywrócono dane.
4. Aplikacja zawiera demonstracyjne ćwiczenia i parametry. **Nie są one nowym zatwierdzonym planem.** Po otrzymaniu dokumentu trenera wprowadź i zweryfikuj nowy plan za pomocą istniejących funkcji przed zapisywaniem rzeczywistych treningów. Nowy plan nie może dziedziczyć wyników ani statystyk ze starego profilu.

## 3. Google Drive i dalsza kontrola

W nowym profilu zalogowanie do Google i konfiguracja OAuth mogą być wymagane ponownie. Stary profil zachowuje swoje ustawienia. Przed włączeniem automatycznych kopii upewnij się, że aktywny jest nowy pusty profil i wybrano właściwe konto. Pierwszy ręczny zapis nowego profilu powinien utworzyć nowy pełny punkt; poczekaj na komunikat potwierdzonej weryfikacji i sprawdź podgląd. Nie wybieraj ani nie usuwaj starych punktów. Potwierdzenie zachowania wszystkich punktów i niezależnej nowej linii na rzeczywistym koncie wymaga osobnego testu użytkownika; symulowane API nie jest takim potwierdzeniem.

W razie potrzeby powrotu przełącz się na stary profil Androida. Przywrócenie starej kopii do nowego profilu zastępuje jego bieżącą historię i wymaga osobnego świadomego wyboru oraz potwierdzenia. Nie scalaj w ten sposób historii testowej z nową.
