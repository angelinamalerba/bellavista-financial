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

## Struttura

```
BELLAVISTA_App.html   — Applicazione completa (standalone HTML)
```
