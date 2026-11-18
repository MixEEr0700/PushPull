/** Presentation only; never promotes POST, restored data or connection to success. */
export function drivePresentation(s){
 const configuration=`Automatyczne kopie ${s.automatic?'włączone':'wyłączone'}. ${s.connected?'Google połączone.':'Wymagane logowanie Google.'}`;
 const d=s.detail||'';let operation='';
 if(s.busy)operation=s.pending?'Zapisywanie kopii na Drive…':'Trwa operacja Google Drive…';
 else if(s.pending&&s.backupFailed)operation=s.connected?'Nie udało się zapisać kopii. Ponów zapis.':'Nie udało się zapisać kopii. Połącz ponownie z Google.';
 else if(s.pending)operation=s.connected?'Kopia oczekuje na wysłanie.':'Kopia oczekuje na wysłanie. Wymagane logowanie.';
 else if(/^(Błąd:|Nie pobrano|Nie zweryfikowano)/.test(d))operation='Błąd Google Drive — wymagana interwencja.';
 else if(/^(Kopia zweryfikowana|Kopia zapisana i zweryfikowana)/.test(d))operation=d;
 const verified=s.verified&&Number.isFinite(Date.parse(s.verified))?'Ostatnia kopia zweryfikowana: '+new Date(s.verified).toLocaleString('pl-PL',{timeZone:'Europe/Warsaw'})+'.':'';
 const detail=/^(Błąd:|Nie pobrano|Nie zweryfikowano|Trening zapisany lokalnie|Kopia sprawdzona|Anulowano|Wybierz|Punkt PPC1)/.test(d)?d:'';
 return {summary:[operation,verified,configuration].filter(Boolean).join(' '),detail};
}
