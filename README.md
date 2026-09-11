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

## Debiti / Crediti

Le categorie possono avere una **natura** (in «Categorie Spese»): voce di spesa
normale, **Debito** (denaro ricevuto da restituire) o **Credito** (denaro
prestato da incassare). I giroconti infragruppo e i finanziamenti soci entrano
sul conto ma vanno restituiti: contarli solo come entrata nasconde che sono
dovuti a qualcuno.

La scheda **🤝 Debiti / Crediti** aggrega quei movimenti per controparte —
ricevuto, restituito, saldo aperto — con il dettaglio espandibile e l'export
CSV. Il nome della controparte viene estratto dalla causale, che nell'estratto
Banco BPM è l'unico posto in cui compare. Si possono registrare anche movimenti
che non passano dal conto (compensazioni, accolli, note di credito).

## Movimenti incrociati

Un giroconto fra due conti della società compare due volte nell'estratto: uscita
di qua, entrata di là. Un bonifico arrivato per errore e restituito identico fa
lo stesso. Finché restano scollegati gonfiano insieme il fatturato e la posizione
debitoria.

Il pulsante **🔗 Incrocia movimenti** (Riconciliazione Banca) li abbina e li
segna come riconciliati; l'abbinamento parte già da solo dopo l'import. Le due
gambe finiscono nelle categorie «Giroconto Interno» o «Partita di Giro», che non
contano né come ricavo né come debito.

Sono riconosciuti tre casi. **Giroconto fra conti**: conti diversi, importo
uguale al centesimo, pochi giorni di distanza. **Partita di giro**: importo
identico più la parola «storno» o la stessa controparte su entrambe le righe.
**Restituzione a rate**: un pagamento sbagliato che rientra spezzato in più
bonifici, con la stessa controparte su tutte le righe e la somma esatta.

Le condizioni sono strette apposta, perché due operazioni vere possono avere lo
stesso importo per caso.

Perché funzioni, in fase di import va mappata anche la colonna **Conto /
Rapporto**: le ultime quattro cifre compaiono poi accanto a ogni movimento,
insieme all'ID della coppia.

## Traduzione delle categorie della banca

Banco BPM esporta una propria colonna Categoria/sottocategoria con una tassonomia
tutta sua — «Servizi - Spese per servizi online», «Fornitori - POS». Presa alla
lettera riempirebbe la Vista per Categoria di nomi estranei, incomparabili con i
Purchase Orders e con i fondi FRS.

All'import le categorie vengono tradotte in quelle di «Categorie Spese», e
l'anteprima mostra quale categoria riceverà ogni riga prima di scrivere. Alcune
regole sulla causale battono l'etichetta della banca, perché in certi casi è
sbagliata: i giroconti fra i conti della società arrivano marcati come «Ricavi».

La categoria originale resta salvata in ogni movimento: si legge passando il
mouse sul menu della categoria, e il pulsante **🔤 Ritraduci categorie dalla
banca** permette di rifare la traduzione da capo.

Alle categorie di partenza se ne sono aggiunte cinque emerse dai dati reali:
**Assicurazioni**, **Attrezzature Ufficio**, **Rappresentanza**, **Auto e
Trasferte** e **Sanzioni**. Senza di quelle un quarto dei movimenti finiva in
«Altro» non perché fosse indistinto, ma perché non c'era dove metterlo.

⚠️ La stessa tabella esiste anche nello skill (`assets/regole_categorie.json`).
Se si modifica una regola va aggiornata in entrambi i posti, altrimenti importare
il CSV nell'app e farlo elaborare allo skill darebbe risultati diversi.

## Fondo Rimborso Finanziamenti

Copre gradualmente i debiti infragruppo e i finanziamenti, e prende il **20% del
margine**. È visibile a tutti, anche in vista Utente.

Quel 20% doveva uscire da qualche parte, e la scelta non è neutra: **Tasse (35%)
e Retribuzioni (24%) restano invariate** perché sono obblighi di legge e
sottofinanziarle sposta solo il problema; la fetta maggiore esce dai **Dividendi,
che scendono dal 15% al 7%**, perché non si distribuisce utile mentre si ha
debito da rimborsare; il resto in proporzione dai fondi discrezionali.

Le categorie **Finanziamento IC** e **Rimborso Finanziamenti** sono collegate a
questo fondo, così i rimborsi lo consumano nella pianificazione.

**È l'unico fondo per l'infragruppo.** Il precedente *Fondo Rimborso
Investimenti* copriva la stessa voce del modello FRS (F11) e non esiste più: la
sua quota è tornata agli altri fondi del margine, che salgono del 18%. Nel
modello Excel quella voce vale il 4%; il 20% è la decisione presa dopo, per
rientrare dei finanziamenti infragruppo.

⚠️ Chi ha dati salvati da prima ha le vecchie percentuali: sommate al nuovo 20%
farebbero 120% e il CHECK va in rosso. Il pulsante **↺ Applica il modello con il
Fondo Rimborso Finanziamenti** (Parametri FRS) rimette tutto a posto in un clic.
All'apertura l'applicazione fonde da sola la quota del vecchio fondo in questo,
così il CHECK resta dov'era finché non si preme il pulsante.

## Pianificazione: budget dei fondi e spesa sotto

Ogni settimana distribuisce i ricavi nei quindici fondi FRS. La scheda
**📊 Pianificazione** (Distribuzione Settimanale) mostra per ogni settimana
quanto di quel budget è già **impegnato** dai Purchase Orders approvati, quanto
è **davvero uscito** dal conto, e quanto **resta**, fondo per fondo, con una
barra di consumo e l'elenco degli ordini che lo stanno usando.

Il disponibile è **cumulato, non settimanale**: quello che non si spende in una
settimana resta per quelle dopo. Ragionare per settimana isolata direbbe che un
fondo è scoperto solo perché l'incasso è arrivato più tardi.

Impegni e uscite sono tenuti distinti apposta: l'impegno è il Purchase Order
approvato, l'uscita è il movimento bancario. Sommarli conterebbe due volte un
ordine già pagato.

**Approvare un ordine oltre la capienza del suo fondo** fa comparire un avviso
con i numeri — importo, disponibile, quanto manca — e l'approvazione si può
annullare. Non è un blocco: la decisione resta di chi approva, ma presa sapendo.

### Cosa copre ogni fondo, e chi firma l'ordine

Non è una regola tecnica ma una decisione aziendale, e la decisione esiste già:
la tabella **🧭 Cosa copre ogni fondo** (in Pianificazione) è il modello Excel
FRS di COMO LAKE ESTATE ricopiato voce per voce — fogli «Расходы — отв.+счета»
e «Responsabili Ordini di Acquisto», governance interna di maggio 2026. Per
ognuna delle diciannove voci F1…F19 dice quale fondo la paga, chi scrive il
Purchase Order, chi lo approva e con quali fornitori tipici.

Sotto, **Chi può richiedere che cosa** elenca per ciascuna delle nove persone
gli ambiti su cui può emettere un ordine. Gli ordini si approvano ogni giovedì
in consiglio finanziario; il contabile paga solo dopo il consiglio.

Le conseguenze pratiche:

- In **Categorie Spese** ogni categoria ha ora tre colonne di governance:
  **Fondo di copertura**, **Chi richiede il PO**, **Chi approva** — precompilate
  dal modello e modificabili.
- In un **nuovo Purchase Order**, scegliendo la categoria si compilano da soli
  richiedente e approvatore, e sotto compare quale fondo paga (con la voce del
  modello, es. «voce F18») e quanto resta disponibile in quella settimana.
- Un ordine per una categoria che il modello non nomina resta **senza firma** e
  l'applicazione lo chiede prima di inserirlo, invece di ereditare il nome
  dell'ordine precedente.
- In fondo alla tabella l'applicazione elenca **le categorie che il modello non
  copre**: sono decisioni da prendere, non errori.

Un'ambiguità del modello è segnalata in chiaro invece di essere risolta di
nascosto: la sigla **FS** indica Filippo Spreafico nel foglio delle spese e
Francesca Severini in quello dei responsabili — qui sono `FilS` e `FrS`.

## Viste per ruolo

Il selettore in testata alterna due viste: **Utente** e **CEO — Direttore
Finanziario**. Nella vista Utente restano nascosti il **Fondo Dividendi** e il
**totale margine**, in tabella, nella dashboard e nell'export CSV. La scelta si
ricorda fra una sessione e l'altra e parte da Utente.

⚠️ **È un filtro di visualizzazione, non una protezione.** L'applicazione è un
file HTML e i dati stanno nel browser: chiunque possa aprirla può leggerli
comunque, anche i valori nascosti. Serve a non mostrare i compensi sullo schermo
durante una riunione o una condivisione. Per una vera separazione servono utenze
e un server.

## Tabella dei fondi a gruppi

I quindici fondi occupavano ventidue colonne e per vedere il CHECK — la
quadratura, cioè il dato che conta di più — bisognava scorrere oltre lo schermo.
Ora i fondi stanno sotto il totale a cui appartengono e si aprono con il **+**:
la tabella parte da sei colonne con ricavi, i due totali e la quadratura, e si
espande solo quando serve il dettaglio.

## Ricostruire le settimane dai ricavi in banca

La distribuzione settimanale si compilava a mano rileggendo l'estratto conto, ma
gli incassi sono già nei movimenti. **📥 Ricostruisci le settimane dai ricavi in
banca** (scheda Distribuzione Settimanale) li raggruppa per settimana FRS,
mostra in anteprima quali settimane cambiano e da quali clienti arrivano, e
compila insieme la distribuzione e la scheda Delta 2025/2026.

Contano solo le categorie con natura **Ricavo** — impostabile in Categorie Spese,
di serie Fattura Cliente, Mediazione Immobiliare e Saldo Commerciale. È la
distinzione che regge tutto: sul conto arrivano anche giroconti fra i conti
della società, finanziamenti soci e storni, e distribuirli nei fondi FRS
gonfierebbe i fondi con denaro mai guadagnato. Sull'estratto 2026 la differenza
è fra 849.818 euro entrati e 542.640 di fatturato vero.

L'anteprima avvisa se ci sono settimane inserite a mano senza riscontro in banca,
elencandole prima di sostituirle.

## Regole apprese dalle correzioni

Le regole scritte a mano coprono quello che si sapeva quando sono state scritte,
ma i fornitori cambiano. Ogni volta che si corregge la categoria di un movimento
l'app registra una regola **controparte → categoria** e propone di allineare gli
altri movimenti della stessa controparte. Al prossimo estratto conto quella
regola viene applicata **prima di tutte le altre**, perché è l'unica confermata
da chi conosce l'azienda.

La chiave è il nome dell'esercente, non la causale: i pagamenti con carta
contengono un riferimento diverso a ogni transazione («CANVA* I04746-48812417
CAMDEN») e usarlo come chiave darebbe una regola valida per un solo addebito.

Il pulsante **🧠 Impara dalle categorie attuali** (scheda Categorie Spese) deriva
le regole da com'è categorizzato l'archivio oggi, saltando le controparti che
compaiono in categorie diverse — lì serve una decisione, non una regola. La
scheda elenca le regole apprese, quanti movimenti coprono e permette di
dimenticarle.

Le regole vivono nei dati e viaggiano nel backup JSON: **anche lo skill le
rispetta**, quindi correggere in app e far elaborare allo skill dà lo stesso
risultato. L'interruttore «🧠 Impara dalle mie correzioni» sopra i movimenti
disattiva l'apprendimento quando si vuole fare una correzione una tantum.

## Correggere le categorie dei movimenti

Nella scheda Riconciliazione Banca la categoria di ogni movimento è ora un menu
a tendina modificabile, con sopra una barra per filtrare per categoria o cercare
nella causale, e per assegnare una categoria a tutti i movimenti filtrati in una
volta. Serve soprattutto a svuotare «Altro»: la categoria assegnata all'import è
un'ipotesi, e la Vista per Categoria vale quanto vale quell'ipotesi.

Ogni riga ha una casella di selezione: si spuntano i movimenti (o si usa la
casella in testata per prendere tutte le righe mostrate) e si assegna in blocco
lo stato di riconciliazione. Il pulsante **Applica a tutti i filtrati** agisce
invece sull'intero filtro, comprese le righe non visibili — utile quando il
filtro seleziona più movimenti di quanti la tabella ne disegni. La selezione
sopravvive al cambio di filtro, così si possono raccogliere movimenti da
categorie diverse prima di applicare.

Con estratti conto lunghi la tabella disegna le prime 400 righe; il filtro serve
a restringere, mentre i totali e la riconciliazione restano calcolati su tutti i
movimenti.

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
