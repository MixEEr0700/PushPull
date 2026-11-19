# PPC1 na dwóch urządzeniach

Od PR #171 standardowe kopie w zakładce Dane używają PPC1. Dotyczy to pliku na urządzeniu oraz punktów Google Drive. Czytniki starszych struktur obsługują zapis historyczny i wewnętrzne punkty ratunkowe.

## Przywracanie na istniejącym profilu

- Nowy profil IndexedDB v2 ma pustą kotwicę starej bazy.
- Profil po sprawdzonej migracji może nadal zawierać `pushpull_skeleton_v1`. To zapis kontrolny wykrywający działanie starszej aplikacji. Worker audytuje stan IndexedDB i sprawdza dokładną zgodność kotwicy z obiektem wskazanym przez `legacyRef`. Przywracanie zachowuje lokalną kotwicę i wiąże ją z nowym stanem IndexedDB v2. Kotwica pozostaje na tym urządzeniu.
- Profil nadal korzystający ze starej bazy albo ze zmienioną kotwicą wymaga najpierw pomyślnego przejścia istniejącej weryfikacji i aktualizacji. Przy sprzecznych zapisach aplikacja blokuje kanoniczne przywracanie i zachowuje oba źródła.

Podgląd porównuje identyfikatory oraz zawartość sesji, wyników, snapshotów i przypisań wersji. Pokazuje też różnice w planach, notatkach, zmianach techniki, szkicach, buforach i ustawieniach. Stan domyślny blokuje przywracanie, gdy kopia pominęłaby bądź zmieniłaby dane lokalne. Użytkownik może zrezygnować albo zaznaczyć osobną zgodę na zastąpienie i zatwierdzić operację. Uzupełnienie dotychczasowej historii wymaga zwykłego potwierdzenia. Każda operacja zastępuje aktywny stan kopią.

Worker ponownie sprawdza zgodność z podglądem i tworzy zweryfikowany punkt cofnięcia przed rezerwacją zapisu. Przerwany zapis pozostaje zablokowany do zakończenia cofania. Starsze punkty referencyjne i lokalne archiwa pozostają dostępne na tym samym urządzeniu. Punkty i archiwa techniczne są przechowywane lokalnie. Rozmiar bazy i dostępne miejsce mogą ograniczyć utworzenie trwałego punktu cofnięcia.

Po przywróceniu ponownie połącz to samo konto Google na tym urządzeniu. Aplikacja zachowuje lokalną preferencję automatycznych kopii i odłącza poprzednie kolejki. Pierwszy zapis Drive po przywróceniu tworzy pełny punkt. Kolejne mogą być przyrostowe według obowiązującego protokołu. Wcześniejsze punkty Drive pozostają dostępne.

## Odbiór na Samsungu i Pixelu

1. Użyj istniejących instalacji z tym samym kontem Google i włączonymi automatycznymi kopiami. Zakończ edycję na drugim telefonie i w dodatkowych kartach.
2. Na Samsungu zapisz trening i poczekaj na „Kopia zweryfikowana”. Na Pixelu wybierz ten punkt przez **Dane → Przywróć kopię → Przywróć z Google Drive**. W podglądzie sprawdź, które sesje i wyniki są tylko w kopii. Jeśli widnieją lokalne różnice, odłóż przywracanie do wyjaśnienia.
3. Potwierdź przywracanie, uruchom ponownie PWA i sprawdź ostatni trening, zapisane serie i rotację. W **Narzędziach serwisowych → Punkty cofnięcia** sprawdź dostępność punktu sprzed operacji.
4. Połącz ponownie to samo konto Google na Pixelu. Zakończ kolejny trening i poczekaj na zweryfikowaną kopię. Przywróć ją na Samsungu i powtórz cykl. Każdy trening ma wystąpić raz.
5. Na jednym telefonie wybierz starszy punkt i sprawdź, czy podgląd pokazuje brakujące lokalne dane, a przycisk potwierdzenia jest zablokowany. Anuluj podgląd i sprawdź zachowanie historii.
