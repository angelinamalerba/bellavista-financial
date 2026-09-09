# Bellavista International — Gestione Finanziaria FRS

Applicazione web standalone per la gestione finanziaria di **BELLAVISTA INTERNATIONAL / COMO LAKE ESTATE SRL**.

## Funzionalità

- **Distribuzione Fondi FRS** — Distribuzione settimanale dei ricavi nei fondi FRS (Agenti, Partner, Dirigenza, Marketing, IVA, Retribuzioni, Dividendi, ecc.)
- **Purchase Orders** — Gestione ordini di acquisto con stati (Attesa / Approvato / Pagato / Rifiutato)
- **Riconciliazione Bancaria** — Importazione CSV Banco BPM con rilevamento automatico del formato, vista settimanale FRS e vista per categoria
- **Dashboard Delta 2025/2026** — Confronto spese 2025 vs incassi 2026 settimana per settimana con grafici
- **Categorie Spese** — Gestione categorie personalizzabili
- **Parametri FRS** — Configurazione percentuali dei fondi

## Come usare

Apri `BELLAVISTA_App.html` direttamente nel browser. Nessuna installazione richiesta — app completamente standalone con dati salvati in localStorage.

### Import CSV Banco BPM

1. Vai su **Riconciliazione Banca** → carica il file CSV scaricato da Banco BPM
2. L'app rileva automaticamente il formato (separatore virgola, decimali italiani)
3. Le colonne si mappano da sole: Data contabile, Descrizione, Importo, Categoria/sottocategoria
4. Clicca **Anteprima** poi **Importa**
5. Le viste per settimana FRS e per categoria si aggiornano automaticamente

### Import Purchase Orders da Excel

**Purchase Orders** → riquadro **📥 Importa Purchase Orders da Excel / CSV**.
Accetta `.xlsx` e `.csv`; il vecchio `.xls` va prima salvato in uno dei due.

1. Carica il file — se il foglio di lavoro ne contiene più di uno, scegli quale
2. Le colonne si mappano da sole dal nome dell'intestazione; le righe di titolo
   sopra le intestazioni vengono saltate
3. **👁 Anteprima** — segnala righe incomplete, categorie non presenti in
   Categorie Spese, stati non riconosciuti e ordini già a registro
4. **✅ Importa ordini selezionati**

Servono almeno **Fornitore** e **Importo**: senza, la riga non è un ordine e
resta bloccata. «Seleziona tutte le nuove» esclude di proposito i duplicati, e
importarne uno a mano richiede una conferma esplicita — un ordine doppio è un
rischio di pagamento doppio.

Le date arrivano corrette sia come date Excel sia come testo `gg/mm/aaaa`, e gli
importi sia in formato italiano (`1.850,00`) sia inglese. Il pulsante **⬇ Scarica
modello CSV** produce un file con le intestazioni giuste già pronte.

Il lettore `.xlsx` è scritto nell'app stessa (uno `.xlsx` è uno ZIP di XML e il
browser sa già decomprimere): nessuna libreria esterna, nessuna connessione,
funziona offline come il resto dell'applicazione.

### Backup e scambio dati (JSON)

Dashboard → **💾 Backup completo (JSON)** scarica *tutti* i dati dell'app in un
unico file: settimane, purchase orders, movimenti bancari, categorie, parametri
FRS e modifiche al Delta. **📤 Ripristina / importa JSON** li ricarica.

Serve per tre cose: il backup, lo spostamento dei dati su un altro computer e
l'elaborazione automatica (vedi sotto). L'importazione **sostituisce** i dati
esistenti e chiede conferma mostrando quante righe sta per caricare.

## Chiusura settimanale automatica

`.claude/skills/bellavista-weekly-close/` contiene uno skill per Claude che
esegue la chiusura settimanale: legge l'estratto conto CSV di Banco BPM,
assegna le categorie, calcola la distribuzione dei fondi FRS, riconcilia i
pagamenti con i Purchase Orders aperti e produce un JSON pronto da importare.

Il motore di calcolo è utilizzabile anche da solo, senza dipendenze esterne:

```bash
python3 .claude/skills/bellavista-weekly-close/scripts/frs.py fondi 152500
python3 .claude/skills/bellavista-weekly-close/scripts/frs.py chiusura \
  --estratto estratto.csv --stato backup.json --anno 2026 --out-json nuovo.json
```

Le regole di categorizzazione stanno in `assets/regole_categorie.json` e vanno
estese man mano che compaiono nuovi fornitori.

## Struttura

```
BELLAVISTA_App.html   — Applicazione completa (standalone HTML)
.claude/skills/bellavista-weekly-close/
                      — Skill per la chiusura settimanale (motore FRS + regole)
```
