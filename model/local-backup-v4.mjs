/** Local, read-only integration. Never calls restore, writes storage or uses Drive. */
import {exportBackupV4} from './backup-v4-export.mjs';
import {decodeBackup,V4_LIMITS} from './backup-v4.mjs';
import {backupSummary} from './legacy-model.mjs';
export async function exportLocalV4(database,options){
 const snapshot=database.export();
 // A pre-journal bridge can carry model metadata outside the v2 snapshot.
 const input=!snapshot.data.trainingJournal&&database.model?await database.exportModelBackup():snapshot;
 return exportBackupV4(input,options);
}
export async function previewLocalV4(file,{signal}={}){
 if(file.size>V4_LIMITS.fileBytes)throw Error('Kopia przekracza limit rozmiaru v4. Nie zmieniono danych.');
 const stage=await decodeBackup(await file.text(),{signal});
 if(stage.formatVersion!==4)throw Error('Ten podgląd obsługuje v4. Dla v1/v2/v3 użyj dotychczasowego przywracania JSON.');
 // Return only a small summary: no raw, staging or restore capability retained by UI.
 return {summary:backupSummary(stage.live.data,{createdAt:stage.createdAt}),archives:stage.archives.length};
}
