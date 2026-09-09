#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Движок недельного закрытия BELLAVISTA INTERNATIONAL / COMO LAKE ESTATE SRL.

Считает то, что нельзя считать «на глаз»: распределение фондов FRS, номера
недель FRS, разбор выписки Banco BPM с итальянскими числами, сверку с
Purchase Orders. Модель полностью повторяет BELLAVISTA_App.html — если
проценты в приложении изменят, скрипт возьмёт их из выгруженного JSON.

Команды:
  weeks    --anno 2026 [--data 2026-02-10]   календарь недель FRS
  fondi    <importo> [--stato backup.json]   распределение суммы по фондам
  estratto <file.csv> [--stato backup.json]  разбор выписки банка
  chiusura --estratto f.csv --stato b.json   полное закрытие недели

Все команды печатают человекочитаемый отчёт; --json отдаёт машинный вывод.
"""

import argparse
import csv
import datetime
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------- модель FRS

# Доли от выручки (ricavi). Сумма = 50%.
DIRETTI = {
    "agenti": 0.30,
    "partner": 0.05,
    "dirigenza": 0.05,
    "marketing": 0.10,
}

# Доли от маржи (margine = 50% выручки). Сумма = 100%.
MARGINE = {
    "iva": 0.35,
    "retrib": 0.24,
    "dividendi": 0.15,
    "hr": 0.02619847328244275,
    "ceo": 0.03969465648854962,
    "sviluppo": 0.03969465648854962,
    "riserve": 0.02381679389312977,
    "rimborso": 0.03969465648854962,
    "formazione": 0.01587786259541985,
    "affitti": 0.0317557251908397,
    "so": 0.04326717557251909,
}

ETICHETTE = {
    "agenti": "Fondo Agenti",
    "partner": "Fondo Partner",
    "dirigenza": "Fondo Dirigenza",
    "marketing": "Fondo Marketing & IT",
    "iva": "Fondo IVA + Imposte",
    "retrib": "Fondo Retribuzioni + Tasse",
    "dividendi": "Fondo Dividendi",
    "hr": "Fondo Obiettivi HR",
    "ceo": "Fondo Emolumento CEO",
    "sviluppo": "Fondo Sviluppo",
    "riserve": "Fondo Riserve",
    "rimborso": "Fondo Rimborso Investimenti",
    "formazione": "Fondo Formazione",
    "affitti": "Fondo Affitti",
    "so": "Fondo Spese Operative",
}

# Список категорий приложения. Нужен, чтобы выгрузка была самодостаточной:
# если отдать JSON без categorie, в приложении выпадающий список окажется пуст
# и категорию движения нельзя будет поправить.
CATEGORIE_DEFAULT = [
    ("Fondo Agenti", "entrambi", ""), ("Fondo Partner", "entrambi", ""),
    ("Fondo Dirigenza", "entrambi", ""), ("Fondo Marketing & IT", "entrambi", ""),
    ("Fondo IVA+Imposte", "entrambi", ""), ("Fondo Retribuzioni", "entrambi", ""),
    ("Fondo Dividendi", "entrambi", ""), ("Fondo CEO", "entrambi", ""),
    ("Fondo Sviluppo", "entrambi", ""), ("Fondo Riserve", "entrambi", ""),
    ("Fondo Rimborso", "entrambi", ""), ("Fondo Formazione", "entrambi", ""),
    ("Fondo Affitti", "entrambi", ""), ("Fondo SO", "entrambi", ""),
    ("Fattura Cliente", "entrambi", ""), ("Fattura Fornitore", "po", ""),
    ("Storno / Rettifica", "entrambi", ""), ("Saldo Commerciale", "entrambi", ""),
    ("Onorario Notaio", "po", ""), ("Onorario Professionista", "po", ""),
    ("Investimento Immobiliare", "entrambi", ""), ("Rimborso Cliente", "banca", ""),
    ("Mediazione Immobiliare", "entrambi", ""), ("Commissioni", "banca", ""),
    ("Finanziamento IC", "banca", "debito"), ("Stipendi", "banca", ""),
    ("Tasse", "banca", ""), ("Software", "entrambi", ""), ("Marketing", "entrambi", ""),
    ("Spese Ufficio", "entrambi", ""), ("Spese Condominiali", "entrambi", ""),
    ("Formazione Esterna", "entrambi", ""),
    ("Consulenze", "entrambi", ""), ("Assicurazioni", "entrambi", ""),
    ("Attrezzature Ufficio", "entrambi", ""), ("Rappresentanza", "entrambi", ""),
    ("Auto e Trasferte", "banca", ""), ("Sanzioni", "banca", ""),
    ("Giroconto Interno", "banca", ""),
    ("Partita di Giro", "banca", ""),
    ("Altro", "entrambi", ""),
]


def categorie_app(stato):
    """Категории из выгрузки приложения, иначе полный список по умолчанию."""
    salvate = (stato or {}).get("categorie")
    if salvate:
        return salvate
    return [{"name": n, "type": t, **({"natura": na} if na else {})}
            for n, t, na in CATEGORIE_DEFAULT]


QUOTA_MARGINE = 0.50  # margine = 50% ricavi, зашито в calcWeek() приложения


def carica_parametri(stato):
    """Проценты из выгрузки приложения, если они там есть, иначе дефолт."""
    p = dict(DIRETTI)
    p.update(MARGINE)
    if stato:
        salvati = (stato.get("data") or stato).get("params") or {}
        for k, v in salvati.items():
            if k in p and isinstance(v, (int, float)):
                p[k] = float(v)
    return p


def distribuisci(importo, params=None):
    """Распределение выручки по фондам. Зеркало calcWeek() из приложения."""
    p = params or carica_parametri(None)
    quote = {k: importo * p[k] for k in DIRETTI}
    tot_diretti = sum(quote.values())
    margine = importo * QUOTA_MARGINE
    quote_m = {k: margine * p[k] for k in MARGINE}
    tot_margine = sum(quote_m.values())
    quote.update(quote_m)
    return {
        "importo": importo,
        "quote": quote,
        "totDiretti": tot_diretti,
        "margine": margine,
        "totMargine": tot_margine,
        # check должен быть 0.00 — иначе проценты в приложении не сходятся к 100%
        "check": importo - tot_diretti - tot_margine,
    }


# ------------------------------------------------------------ недели FRS

def inizio_anno(anno):
    """Неделя 1 стартует в первый четверг января — так устроен DELTA_BASE."""
    d = datetime.date(anno, 1, 1)
    while d.weekday() != 3:  # 3 = четверг
        d += datetime.timedelta(days=1)
    return d


def calendario(anno, settimane=52):
    inizio = inizio_anno(anno)
    out = []
    for i in range(settimane):
        s = inizio + datetime.timedelta(days=7 * i)
        out.append({"w": i + 1, "start": s, "end": s + datetime.timedelta(days=6)})
    return out


def settimana_di(data, anno=None):
    """Номер недели FRS для даты. Возвращает None вне 52-недельной сетки."""
    anno = anno or data.year
    for r in calendario(anno):
        if r["start"] <= data <= r["end"]:
            return r["w"]
    # дата может попадать в 52-ю неделю предыдущего года
    for r in calendario(anno - 1):
        if r["start"] <= data <= r["end"]:
            return r["w"]
    return None


# ---------------------------------------------------------- контрагент

# Имя контрагента не отдельное поле выписки — оно внутри описания, в нескольких
# устойчивых форматах Banco BPM. Без него нельзя собрать реестр долгов: неясно,
# кому компания должна и кто должен ей.
RE_CONTROPARTE = [
    re.compile(r"BON\.\s*DA\s+(.+?)(?:\s+-\s+|$)", re.I),
    re.compile(r"\bFAVORE\s+(.+?)(?:\s+-\s+|$)", re.I),
    re.compile(r"BONIFICO DALL'ESTERO\s*-\s*[\d\-/]*\s*N\.\s*\d+\s+(.+?)(?:\s+-\s+|$)", re.I),
    re.compile(r"SDD[^:]*:\s*\d*\s*(.+?)(?:\s+-\s+|$)", re.I),
    re.compile(r"CARTA\*\d+\s*-\s*[\d:]+\s*-\s*(.+?)$", re.I),
]

PAESI_CODA = re.compile(r"\s+(NOTPROVIDE|ITA|USA|NLD|GBR|CHE|DEU|FRA|ESP|IRL|LUX|POL|SWE|AUT)$", re.I)


def controparte(desc):
    d = str(desc or "").strip()
    for rx in RE_CONTROPARTE:
        m = rx.search(d)
        if m and m.group(1):
            n = re.sub(r"\s+", " ", m.group(1)).strip()
            while PAESI_CODA.search(n):
                n = PAESI_CODA.sub("", n)
            n = n.rstrip(" -\u2013").strip()
            if len(n) > 2:
                return n[:60]
    return ""


# ------------------------------------------------- разбор выписки Banco BPM

SEPARATORI = [";", ",", "\t"]


def _norm(s):
    """Нижний регистр без диакритики — для устойчивого сравнения заголовков."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def rileva_separatore(testo):
    prima = testo.splitlines()[0] if testo.splitlines() else ""
    return max(SEPARATORI, key=prima.count) if any(prima.count(s) for s in SEPARATORI) else ";"


def parse_importo(v):
    """'1.234,56' → 1234.56; '1,234.56' → 1234.56; '(120,00)' → -120.0."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    negativo = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[^\d,.\-+]", "", s)  # убираем EUR, €, пробелы, NBSP
    if not s or s in "-+":
        return None
    if "," in s and "." in s:
        # последний разделитель — десятичный
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if negativo else n


def parse_data(v):
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# какие заголовки Banco BPM во что ложатся
SINONIMI = {
    "data": ["data contabile", "data operazione", "data valuta", "data"],
    "desc": ["descrizione", "causale", "descrizione operazione", "dettagli", "note"],
    "importo": ["importo", "importo eur", "ammontare"],
    "entrata": ["entrate", "entrata", "avere", "accrediti", "accredito"],
    "uscita": ["uscite", "uscita", "dare", "addebiti", "addebito"],
    "cat": ["categoria", "sottocategoria", "categoria/sottocategoria"],
    "conto": ["rapporto", "conto", "iban", "numero conto"],
}


def mappa_colonne(headers):
    norm = [_norm(h) for h in headers]
    mapping = {}
    for campo, opzioni in SINONIMI.items():
        for opt in opzioni:
            for i, h in enumerate(norm):
                if h == opt:
                    mapping[campo] = i
                    break
            if campo in mapping:
                break
        if campo not in mapping:  # запасной проход — вхождение подстроки
            for opt in opzioni:
                for i, h in enumerate(norm):
                    if opt in h:
                        mapping[campo] = i
                        break
                if campo in mapping:
                    break
    return mapping


def ultime_cifre(rapporto, n=4):
    """«51050 - 426000002368» → «2368». Le ultime cifre bastano a distinguere
    i conti e sono l'unica parte che si legge a colpo d'occhio in una tabella."""
    cifre = re.sub(r"\D", "", str(rapporto or ""))
    return cifre[-n:] if len(cifre) >= n else cifre


def abbina_giroconti(mov, giorni=3):
    """Accoppia le due gambe di un giroconto fra conti della stessa società.

    Un giroconto compare due volte: come uscita su un conto e come entrata
    sull'altro. Finché restano scollegati sembrano un debito verso sé stessi e
    la stessa somma risulta sia entrata sia uscita. Accoppiandoli si azzerano a
    vicenda e sparisce un debito che non esiste.

    Si abbinano solo movimenti su conti DIVERSI, di importo identico e a pochi
    giorni di distanza: senza queste tre condizioni insieme si rischia di legare
    fra loro pagamenti veri che per caso hanno lo stesso importo.
    """
    interni = [m for m in mov if _norm("como lake estate") in _norm(m["desc"])
               or "giroconto" in _norm(m["desc"]) or "giriconto" in _norm(m["desc"])]
    uscite = [m for m in interni if m["out"] > 0]
    entrate = [m for m in interni if m["in"] > 0]
    usate = set()
    coppie = []
    for u in sorted(uscite, key=lambda m: m["date"]):
        du = datetime.date.fromisoformat(u["date"])
        for e in sorted(entrate, key=lambda m: m["date"]):
            if id(e) in usate:
                continue
            if e["conto"] == u["conto"] or not e["conto"] or not u["conto"]:
                continue
            if abs(e["in"] - u["out"]) > 0.01:
                continue
            if abs((datetime.date.fromisoformat(e["date"]) - du).days) > giorni:
                continue
            usate.add(id(e))
            coppie.append({"uscita": u, "entrata": e, "importo": u["out"]})
            u["gir"] = e["gir"] = f"G{len(coppie):03d}"
            u["cat"] = e["cat"] = "Giroconto Interno"
            u["fonte_cat"] = e["fonte_cat"] = f"giroconto abbinato {u['conto']}→{e['conto']}"
            u["rec"] = e["rec"] = "S"
            break
    spaiati = [m for m in interni if not m.get("gir")]
    return coppie, spaiati


SEGNALI_STORNO = ("storno", "rettifica", "restituzione", "rimborso", "bonifico errat", "errato")


def abbina_partite_giro(mov, giorni=120):
    """Accoppia un accredito con lo storno che lo restituisce.

    Capita che arrivi un bonifico non dovuto e che venga rimandato indietro
    identico: le due righe non sono né un ricavo né un debito, sono la stessa
    somma che entra ed esce. Lasciate scollegate gonfiano sia il fatturato sia
    la posizione debitoria.

    Per evitare di accoppiare per sbaglio due operazioni vere che hanno lo
    stesso importo si chiedono tre condizioni insieme: importo uguale al
    centesimo, almeno una delle due righe che parla esplicitamente di storno o
    restituzione, e una distanza di pochi mesi.
    """
    liberi = [m for m in mov if not m.get("gir")]
    entrate = [m for m in liberi if m["in"] > 0]
    uscite = [m for m in liberi if m["out"] > 0]
    usate = set()
    coppie = []
    for e in sorted(entrate, key=lambda m: m["date"]):
        de = datetime.date.fromisoformat(e["date"])
        for u in sorted(uscite, key=lambda m: m["date"]):
            if id(u) in usate or abs(u["out"] - e["in"]) > 0.01:
                continue
            giorni_diff = (datetime.date.fromisoformat(u["date"]) - de).days
            if giorni_diff < 0 or giorni_diff > giorni:
                continue
            # Solo l'importo uguale non basta: due operazioni vere possono
            # coincidere per caso. Serve una prova del legame — o la parola
            # "storno" in una delle due righe, o la stessa controparte.
            testo = _norm(e["desc"]) + " " + _norm(u["desc"])
            stesso_cp = bool(e["cp"]) and _norm(e["cp"]) == _norm(u["cp"])
            if "storno" not in testo and not stesso_cp:
                continue
            if not any(sig in testo for sig in SEGNALI_STORNO) and not stesso_cp:
                continue
            usate.add(id(u))
            coppie.append({"entrata": e, "uscita": u, "importo": e["in"], "giorni": giorni_diff})
            e["gir"] = u["gir"] = f"P{len(coppie):03d}"
            e["cat"] = u["cat"] = "Partita di Giro"
            e["fonte_cat"] = u["fonte_cat"] = f"partita di giro: entrata e storno di pari importo a {giorni_diff} giorni"
            e["rec"] = u["rec"] = "S"
            break
    return coppie


def abbina_parziali(mov, giorni=120, max_pezzi=3):
    """Accoppia un pagamento sbagliato con i rientri che lo restituiscono a rate.

    La restituzione non arriva sempre in un colpo solo: un doppio bonifico da
    19.000 può tornare come 10.000 più 9.000 a due giorni di distanza. Con il
    solo abbinamento uno-a-uno quelle righe restano scollegate e l'uscita
    doppia continua a pesare come spesa vera.

    Qui si richiede la stessa controparte su tutte le righe e la somma esatta
    al centesimo: due condizioni che insieme rendono improbabile un abbinamento
    casuale, molto più della sola coincidenza di importo.
    """
    import itertools
    liberi = [m for m in mov if not m.get("gir")]
    per_cp = {}
    for m in liberi:
        if m["cp"]:
            per_cp.setdefault(chiave_controparte(m["cp"]), []).append(m)

    coppie = []
    for cp, gruppo in per_cp.items():
        usati = set()
        for singolo in sorted(gruppo, key=lambda m: (-max(m["in"], m["out"]), m["date"])):
            if id(singolo) in usati or singolo.get("gir"):
                continue
            importo = singolo["out"] or singolo["in"]
            verso_opposto = "in" if singolo["out"] else "out"
            d0 = datetime.date.fromisoformat(singolo["date"])
            candidati = [m for m in gruppo
                         if id(m) not in usati and not m.get("gir") and m is not singolo
                         and m[verso_opposto] > 0
                         and 0 <= (datetime.date.fromisoformat(m["date"]) - d0).days <= giorni]
            trovata = None
            for n in range(2, max_pezzi + 1):
                for combo in itertools.combinations(candidati, n):
                    if abs(sum(c[verso_opposto] for c in combo) - importo) < 0.01:
                        trovata = combo
                        break
                if trovata:
                    break
            if not trovata:
                continue
            idc = f"R{len(coppie) + 1:03d}"
            for m in (singolo,) + tuple(trovata):
                usati.add(id(m))
                m["gir"] = idc
                m["cat"] = "Partita di Giro"
                m["rec"] = "S"
                m["fonte_cat"] = f"restituzione a rate: {len(trovata)} rientri da {cp}"
            coppie.append({"origine": singolo, "rientri": list(trovata), "importo": importo})
    return coppie


def leggi_estratto(percorso, regole=None, anno=None):
    """CSV Banco BPM → список движений с датой, суммой, неделей и категорией."""
    raw = Path(percorso).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            testo = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        testo = raw.decode("utf-8", errors="replace")

    sep = rileva_separatore(testo)
    righe = list(csv.reader(io.StringIO(testo), delimiter=sep))
    righe = [r for r in righe if any(str(c).strip() for c in r)]
    if not righe:
        return [], {"errore": "файл пустой"}

    # заголовок — первая строка, где узнаются дата и хотя бы одна сумма
    idx_header, mapping = None, {}
    for i, r in enumerate(righe[:15]):
        m = mappa_colonne(r)
        if "data" in m and ({"importo", "entrata", "uscita"} & set(m)):
            idx_header, mapping = i, m
            break
    if idx_header is None:
        return [], {"errore": "не найдена строка заголовков (нужны 'Data' и 'Importo'/'Entrate'/'Uscite')",
                    "prima_riga": righe[0]}

    movimenti, scartate = [], []
    for r in righe[idx_header + 1:]:
        def cell(campo):
            i = mapping.get(campo)
            return r[i] if i is not None and i < len(r) else ""

        data = parse_data(cell("data"))
        if not data:
            scartate.append(r)
            continue

        entrata = uscita = 0.0
        if "importo" in mapping:
            n = parse_importo(cell("importo"))
            if n is not None:
                entrata, uscita = (n, 0.0) if n >= 0 else (0.0, -n)
        if "entrata" in mapping:
            n = parse_importo(cell("entrata"))
            if n:
                entrata = abs(n)
        if "uscita" in mapping:
            n = parse_importo(cell("uscita"))
            if n:
                uscita = abs(n)
        if not entrata and not uscita:
            scartate.append(r)
            continue

        desc = str(cell("desc")).strip()
        cat_file = str(cell("cat")).strip()
        if cat_file:
            cat, fonte = traduci_categoria_banca(cat_file, desc, regole)
        else:
            cat, fonte = classifica(desc, regole)
        movimenti.append({
            "date": data.isoformat(),
            "desc": desc,
            "in": round(entrata, 2),
            "out": round(uscita, 2),
            "cat": cat,
            "cat_banca": cat_file,
            "cp": controparte(desc),
            "conto": ultime_cifre(cell("conto")),
            "fonte_cat": fonte,
            "settimana": settimana_di(data, anno),
            "rec": "N",
        })

    movimenti.sort(key=lambda m: m["date"])
    coppie, spaiati = abbina_giroconti(movimenti)
    partite = abbina_partite_giro(movimenti)
    parziali = abbina_parziali(movimenti)
    return movimenti, {"separatore": sep, "colonne": mapping, "righe_scartate": len(scartate),
                       "giroconti": coppie, "giroconti_spaiati": spaiati,
                       "partite_giro": partite, "parziali": parziali}


# --------------------------------------------------------- классификация

def carica_regole(percorso=None):
    p = Path(percorso) if percorso else Path(__file__).parent.parent / "assets" / "regole_categorie.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"regole": [], "default": "Altro"}


def traduci_categoria_banca(cat_banca, descrizione, regole=None):
    """Категория из выписки Banco BPM → категория приложения.

    Банк присылает свою таксономию («Servizi - Spese per servizi online»),
    и брать её как есть нельзя: в приложении другой список, иначе аналитика
    развалится. Если перевода нет — падаем на разбор описания.
    """
    regole = regole or carica_regole()
    # автокатегория банка иногда просто неверна — сначала жёсткие правила по описанию
    d = _norm(descrizione)
    for r in regole.get("regole_forzate", []):
        for kw in r.get("parole", []):
            if _norm(kw) in d:
                return r["categoria"], f"правило «{kw}» (важнее банка: {cat_banca})"
    mappa = regole.get("mappa_banca", {})
    norm = {_norm(k): v for k, v in mappa.items()}
    tradotta = norm.get(_norm(cat_banca))
    if tradotta:
        return tradotta, f"банк: {cat_banca}"
    cat, fonte = classifica(descrizione, regole)
    return cat, f"{fonte} (банк: {cat_banca} — нет в mappa_banca)"


def chiave_controparte(nome):
    """Ключ для группировки контрагентов.

    «CBV INTERIOR GALLERY S.R.L.» и «CBV INTERIOR GALLERY SRL» — одна компания,
    но в выписке она пишется по-разному. Без нормализации организационной формы
    один и тот же контрагент разъезжается на две строки реестра, и сальдо по
    нему выглядит открытым, хотя оно закрыто.
    """
    n = _norm(nome)
    n = re.sub(r"\bs\s*\.?\s*r\s*\.?\s*l\s*\.?\b", "srl", n)
    n = re.sub(r"\bs\s*\.?\s*p\s*\.?\s*a\s*\.?\b", "spa", n)
    n = re.sub(r"\bs\s*\.?\s*a\s*\.?\b", "sa", n)
    n = re.sub(r"\bs\s*\.?\s*n\s*\.?\s*c\s*\.?\b", "snc", n)
    return re.sub(r"[^a-z0-9 ]", "", n).strip()


def e_ricavo(mov, regole=None):
    """Приход, который действительно выручка и подлежит распределению по FRS.

    Поступление на счёт и выручка — разные вещи: внутригрупповые переводы,
    займы учредителя и возвраты приходят на тот же счёт, но их распределение
    по фондам раздуло бы фонды деньгами, которых компания не заработала.
    """
    regole = regole or carica_regole()
    ricavi = set(regole.get("ricavi_frs", ["Fattura Cliente"]))
    return mov["in"] > 0 and mov["cat"] in ricavi


def classifica(descrizione, regole=None):
    """Категория по ключевым словам. Возвращает (категория, источник)."""
    regole = regole or carica_regole()
    d = _norm(descrizione)
    for r in regole.get("regole", []):
        for kw in r.get("parole", []):
            if _norm(kw) in d:
                return r["categoria"], f"правило «{kw}»"
    return regole.get("default", "Altro"), "не распознано"


# ------------------------------------------------------- сверка с PO

def concilia_po(movimenti, po, tolleranza=0.01):
    """Ищет для каждого неоплаченного PO расход банка с той же суммой."""
    aperti = [o for o in po if o.get("status") in ("attesa", "approvato")]
    abbinamenti, usati = [], set()
    for i, o in enumerate(aperti):
        importo = float(o.get("amount") or 0)
        for j, m in enumerate(movimenti):
            if j in usati or not m["out"]:
                continue
            if abs(m["out"] - importo) <= tolleranza:
                abbinamenti.append({"po": o, "movimento": m, "po_idx": i})
                usati.add(j)
                break
    non_abbinati = [o for i, o in enumerate(aperti) if i not in {a["po_idx"] for a in abbinamenti}]
    return abbinamenti, non_abbinati


# ------------------------------------------------------------- вывод

def eur(n):
    if abs(n) < 0.005:
        n = 0.0  # иначе округление даёт «-0,00» и это читается как ошибка
    s = f"{n:,.2f}".replace(",", " ").replace(".", ",")
    return f"€ {s}"


def stampa_fondi(calc):
    righe = ["| Фонд | База | Сумма |", "|---|---|---|"]
    for k in DIRETTI:
        righe.append(f"| {ETICHETTE[k]} | ricavi | {eur(calc['quote'][k])} |")
    righe.append(f"| **Totale diretti** | | **{eur(calc['totDiretti'])}** |")
    righe.append(f"| **Margine (50%)** | ricavi | **{eur(calc['margine'])}** |")
    for k in MARGINE:
        righe.append(f"| {ETICHETTE[k]} | margine | {eur(calc['quote'][k])} |")
    righe.append(f"| **Totale margine** | | **{eur(calc['totMargine'])}** |")
    stato = "✅ сходится" if abs(calc["check"]) < 0.01 else "⚠️ НЕ СХОДИТСЯ"
    righe.append(f"| **Check** | | **{eur(calc['check'])}** {stato} |")
    return "\n".join(righe)


def carica_stato(percorso):
    if not percorso:
        return None
    obj = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return obj.get("data") if isinstance(obj, dict) and "data" in obj else obj


# --------------------------------------------------------------- команды

def cmd_weeks(a):
    cal = calendario(a.anno)
    if a.data:
        d = parse_data(a.data)
        w = settimana_di(d, a.anno)
        r = next((x for x in cal if x["w"] == w), None)
        print(f"{d} → неделя FRS {w}" + (f" ({r['start']} — {r['end']})" if r else ""))
        return
    for r in cal:
        print(f"W{r['w']:>2}  {r['start']} — {r['end']}")


def cmd_fondi(a):
    calc = distribuisci(a.importo, carica_parametri(carica_stato(a.stato)))
    print(f"Выручка недели: {eur(a.importo)}\n")
    print(stampa_fondi(calc))


def cmd_estratto(a):
    stato = carica_stato(a.stato)
    mov, meta = leggi_estratto(a.file, carica_regole(a.regole), a.anno)
    if a.json:
        print(json.dumps({"movimenti": mov, "meta": meta}, ensure_ascii=False, indent=2))
        return
    if meta.get("errore"):
        print(f"❌ {meta['errore']}")
        if meta.get("prima_riga"):
            print(f"   первая строка: {meta['prima_riga']}")
        return
    print(f"Разобрано движений: {len(mov)} (разделитель «{meta['separatore']}», "
          f"пропущено строк: {meta['righe_scartate']})\n")
    print("| Дата | W | Описание | Приход | Расход | Категория | Источник |")
    print("|---|---|---|---|---|---|---|")
    for m in mov:
        print(f"| {m['date']} | {m['settimana'] or '—'} | {m['desc'][:45]} | "
              f"{eur(m['in']) if m['in'] else ''} | {eur(m['out']) if m['out'] else ''} | "
              f"{m['cat']} | {m['fonte_cat']} |")
    da_rivedere = [m for m in mov if m["fonte_cat"] == "не распознано"]
    if da_rivedere:
        print(f"\n⚠️ Без категории: {len(da_rivedere)} — проверить вручную и при "
              f"необходимости дописать правило в assets/regole_categorie.json")


def cmd_chiusura(a):
    stato = carica_stato(a.stato) or {"weeks": [], "po": [], "bank": [], "categorie": [], "deltaEdits": {}}
    params = carica_parametri(stato)
    mov, meta = leggi_estratto(a.estratto, carica_regole(a.regole), a.anno)
    if meta.get("errore"):
        print(f"❌ Не удалось разобрать выписку: {meta['errore']}")
        sys.exit(1)

    settimana = a.settimana or (max((m["settimana"] for m in mov if m["settimana"]), default=None))
    del_sett = [m for m in mov if m["settimana"] == settimana]
    regole = carica_regole(a.regole)
    entrate = sum(m["in"] for m in del_sett)
    uscite = sum(m["out"] for m in del_sett)
    ricavi = sum(m["in"] for m in del_sett if e_ricavo(m, regole))
    non_ricavi = entrate - ricavi
    calc = distribuisci(ricavi, params)

    per_cat = {}
    for m in del_sett:
        c = per_cat.setdefault(m["cat"], {"in": 0.0, "out": 0.0, "n": 0})
        c["in"] += m["in"]
        c["out"] += m["out"]
        c["n"] += 1

    abbinamenti, po_aperti = concilia_po(del_sett, stato.get("po", []))
    # у совпавшего PO категория уже утверждена — она надёжнее догадки по ключевому слову
    for ab in abbinamenti:
        cat_po = (ab["po"].get("cat") or "").strip()
        if cat_po and ab["movimento"]["fonte_cat"] in ("не распознано", ""):
            ab["movimento"]["cat"] = cat_po
            ab["movimento"]["fonte_cat"] = f"из PO {ab['po'].get('supplier', '')}".strip()
    cal = {r["w"]: r for r in calendario(a.anno or datetime.date.today().year)}
    periodo = cal.get(settimana)

    out = [f"# Закрытие недели FRS {settimana}"]
    if periodo:
        out.append(f"Период: **{periodo['start']} — {periodo['end']}**")
    out += [
        "",
        "## 1. Итог недели",
        "",
        f"- Поступления всего: **{eur(entrate)}**"
        + (f" (из них не выручка: {eur(non_ricavi)} — переводы, займы, возвраты)" if non_ricavi else ""),
        f"- **Выручка для FRS: {eur(ricavi)}**",
        f"- Списания: **{eur(uscite)}**",
        f"- Сальдо недели: **{eur(entrate - uscite)}**",
        f"- Движений в выписке: {len(del_sett)} из {len(mov)} в файле",
        "",
        "## 2. Распределение фондов FRS",
        "",
        stampa_fondi(calc),
        "",
        "## 3. Движения по категориям",
        "",
        "| Категория | Приход | Расход | Шт. |",
        "|---|---|---|---|",
    ]
    for c, v in sorted(per_cat.items(), key=lambda x: -(x[1]["in"] + x[1]["out"])):
        out.append(f"| {c} | {eur(v['in']) if v['in'] else '—'} | "
                   f"{eur(v['out']) if v['out'] else '—'} | {v['n']} |")

    out += ["", "## 4. Сверка с Purchase Orders", ""]
    if abbinamenti:
        out.append("Совпали по сумме — проверить и перевести в статус «pagato»:")
        out.append("")
        out.append("| PO | Поставщик | Сумма | Движение в банке |")
        out.append("|---|---|---|---|")
        for ab in abbinamenti:
            o, m = ab["po"], ab["movimento"]
            out.append(f"| {o.get('date','')} | {o.get('supplier','')} | {eur(float(o.get('amount') or 0))} | "
                       f"{m['date']} — {m['desc'][:40]} |")
    else:
        out.append("Совпадений с открытыми PO не найдено.")
    if po_aperti:
        out += ["", f"Открытых PO без оплаты: **{len(po_aperti)}** — "
                    f"{', '.join(str(o.get('supplier','?')) for o in po_aperti[:8])}"]

    da_rivedere = [m for m in del_sett if m["fonte_cat"] == "не распознано"]
    out += ["", "## 5. Требует решения", ""]
    if da_rivedere:
        for m in da_rivedere:
            somma = eur(m["in"]) if m["in"] else f"-{eur(m['out'])}"
            out.append(f"- {m['date']} · {somma} · {m['desc'][:70]} → категория не определена")
    else:
        out.append("Все движения распознаны, ручных решений не требуется.")
    if abs(calc["check"]) >= 0.01:
        out.append(f"- ⚠️ Проценты FRS не сходятся к 100%: расхождение {eur(calc['check'])} "
                   f"— проверить вкладку «Parametri FRS»")

    rapporto = "\n".join(out)
    print(rapporto)

    if a.out_json:
        nuovo = dict(stato)
        nuovo["bank"] = list(stato.get("bank", [])) + [
            {**{k: m[k] for k in ("date", "desc", "in", "out", "cat", "rec", "cp", "conto")},
             **({"gir": m["gir"]} if m.get("gir") else {})} for m in del_sett
        ]
        if entrate:
            nuovo["weeks"] = list(stato.get("weeks", [])) + [
                {"date": (periodo["start"].isoformat() if periodo else del_sett[0]["date"]),
                 "amount": round(entrate, 2)}
            ]
            nuovo["weeks"].sort(key=lambda w: w["date"])
        Path(a.out_json).write_text(
            json.dumps({"schema": "bellavista-financial", "schemaVersion": 1,
                        "exportedAt": datetime.datetime.now().isoformat(), "data": nuovo},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n---\n💾 Обновлённое состояние: `{a.out_json}` "
              f"(загрузить в приложении: Dashboard → «Ripristina / importa JSON»)")
    if a.out_report:
        Path(a.out_report).write_text(rapporto, encoding="utf-8")


def cmd_periodo(a):
    """Отчёт по всем неделям сразу — для сверки квартала или года целиком."""
    stato = carica_stato(a.stato) or {}
    params = carica_parametri(stato)
    regole = carica_regole(a.regole)
    mov, meta = leggi_estratto(a.estratto, regole, a.anno)
    if meta.get("errore"):
        print(f"❌ {meta['errore']}")
        sys.exit(1)

    anno = a.anno or datetime.date.fromisoformat(mov[0]["date"]).year
    cal = {r["w"]: r for r in calendario(anno)}

    per_sett = {}
    per_cat = {}
    matrice = {}
    for m in mov:
        w = m["settimana"]
        s_ = per_sett.setdefault(w, {"in": 0.0, "out": 0.0, "ricavi": 0.0, "n": 0})
        s_["in"] += m["in"]; s_["out"] += m["out"]; s_["n"] += 1
        if e_ricavo(m, regole):
            s_["ricavi"] += m["in"]
        c = per_cat.setdefault(m["cat"], {"in": 0.0, "out": 0.0, "n": 0})
        c["in"] += m["in"]; c["out"] += m["out"]; c["n"] += 1
        cella = matrice.setdefault((w, m["cat"]), {"in": 0.0, "out": 0.0, "n": 0})
        cella["in"] += m["in"]; cella["out"] += m["out"]; cella["n"] += 1

    tot_in = sum(m["in"] for m in mov)
    tot_out = sum(m["out"] for m in mov)
    tot_ricavi = sum(m["in"] for m in mov if e_ricavo(m, regole))
    calc = distribuisci(tot_ricavi, params)

    out = [f"# Riconciliazione {anno} — {len(mov)} movimenti", ""]
    date = sorted(m["date"] for m in mov)
    out += [f"Periodo: **{date[0]} → {date[-1]}**", "",
            "## 1. Totali del periodo", "",
            f"- Entrate totali sul conto: **{eur(tot_in)}**",
            f"- di cui ricavi da distribuire nei fondi FRS: **{eur(tot_ricavi)}**",
            f"- di cui NON ricavi (giroconti, prestiti soci, rimborsi): **{eur(tot_in - tot_ricavi)}**",
            f"- Uscite totali: **{eur(tot_out)}**",
            f"- Saldo del periodo: **{eur(tot_in - tot_out)}**", "",
            "## 2. Settimana per settimana", "",
            "| Sett. | Periodo | Entrate | di cui ricavi FRS | Uscite | Netto | Mov. |",
            "|---|---|---|---|---|---|---|"]
    for w in sorted(k for k in per_sett if k is not None):
        v = per_sett[w]
        r = cal.get(w)
        periodo = f"{r['start']} / {r['end']}" if r else "—"
        out.append(f"| W{w} | {periodo} | {eur(v['in']) if v['in'] else '—'} | "
                   f"{eur(v['ricavi']) if v['ricavi'] else '—'} | {eur(v['out']) if v['out'] else '—'} | "
                   f"{eur(v['in'] - v['out'])} | {v['n']} |")
    if None in per_sett:
        v = per_sett[None]
        out.append(f"| — | fuori dalle 52 settimane | {eur(v['in'])} | — | {eur(v['out'])} | "
                   f"{eur(v['in'] - v['out'])} | {v['n']} |")

    out += ["", "## 3. Totali per categoria", "",
            "| Categoria | Entrate | Uscite | Netto | Mov. |", "|---|---|---|---|---|"]
    for c, v in sorted(per_cat.items(), key=lambda x: -(x[1]["in"] + x[1]["out"])):
        out.append(f"| {c} | {eur(v['in']) if v['in'] else '—'} | {eur(v['out']) if v['out'] else '—'} | "
                   f"{eur(v['in'] - v['out'])} | {v['n']} |")

    out += ["", "## 4. Distribuzione FRS sui ricavi del periodo", "",
            f"Ricavi: **{eur(tot_ricavi)}**", "", stampa_fondi(calc)]

    gir = meta.get("giroconti", [])
    par = meta.get("partite_giro", [])
    prz = meta.get("parziali", [])
    if gir or par or prz:
        out += ["", "## 5. Movimenti incrociati (si annullano a vicenda)", ""]
    if gir:
        out += [f"**Giroconti fra i conti della società: {len(gir)} coppie, "
                f"{eur(sum(g['importo'] for g in gir))}**", "",
                "| ID | Data | Da conto | A conto | Importo | Causale |", "|---|---|---|---|---|---|"]
        for g in gir:
            out.append(f"| {g['uscita']['gir']} | {g['uscita']['date']} | ...{g['uscita']['conto']} | "
                       f"...{g['entrata']['conto']} | {eur(g['importo'])} | {g['entrata']['desc'][:48]} |")
    if par:
        out += ["", f"**Partite di giro (accredito e storno di pari importo): {len(par)}, "
                    f"{eur(sum(p['importo'] for p in par))}**", "",
                "| ID | Entrata | Storno | Giorni | Importo | Causale |", "|---|---|---|---|---|---|"]
        for p in par:
            out.append(f"| {p['entrata']['gir']} | {p['entrata']['date']} | {p['uscita']['date']} | "
                       f"{p['giorni']} | {eur(p['importo'])} | {p['entrata']['desc'][:48]} |")

    if prz:
        out += ["", f"**Restituzioni a rate: {len(prz)}, {eur(sum(p['importo'] for p in prz))}**", "",
                "| ID | Uscita | Importo | Rientri | Controparte |", "|---|---|---|---|---|"]
        for p in prz:
            rientri = " + ".join(f"{eur(r['in'] or r['out'])} il {r['date']}" for r in p["rientri"])
            out.append(f"| {p['origine']['gir']} | {p['origine']['date']} | {eur(p['importo'])} | "
                       f"{rientri} | {p['origine']['cp']} |")

    senza = [m for m in mov if "нет в mappa_banca" in m["fonte_cat"] or m["fonte_cat"] == "не распознано"]
    out += ["", "## 6. Da rivedere", ""]
    if senza:
        out.append(f"{len(senza)} movimenti senza traduzione certa della categoria:")
        out.append("")
        for m in senza[:25]:
            somma = eur(m["in"]) if m["in"] else f"-{eur(m['out'])}"
            out.append(f"- {m['date']} · {somma} · {m['desc'][:60]} → **{m['cat']}** ({m['fonte_cat']})")
        if len(senza) > 25:
            out.append(f"- … e altri {len(senza) - 25}")
    else:
        out.append("Tutte le categorie della banca sono state tradotte.")

    rapporto = "\n".join(out)
    print(rapporto)
    if a.out_report:
        Path(a.out_report).write_text(rapporto, encoding="utf-8")

    if a.out_matrice:
        righe = [["Settimana", "Dal", "Al", "Categoria", "Entrate", "Uscite", "Netto", "N. movimenti"]]
        for (w, c), v in sorted(matrice.items(), key=lambda x: (x[0][0] or 999, x[0][1])):
            r = cal.get(w)
            righe.append([f"W{w}" if w else "fuori",
                          r["start"].isoformat() if r else "", r["end"].isoformat() if r else "",
                          c, f"{v['in']:.2f}", f"{v['out']:.2f}", f"{v['in'] - v['out']:.2f}", v["n"]])
        with open(a.out_matrice, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f, delimiter=";").writerows(righe)
        print(f"\n💾 Dettaglio settimana × categoria: `{a.out_matrice}`")

    if a.out_json:
        nuovo = dict(stato) if stato else {"po": [], "bankBalances": {"conto": 0, "libro": 0},
                                           "deltaEdits": {}, "debiti": []}
        # senza le percentuali complete l'app calcola i fondi su undefined e la
        # Dashboard mostra NaN: la quota di ogni fondo va sempre nel file
        nuovo["params"] = params
        nuovo["categorie"] = categorie_app(stato)
        nuovo.setdefault("debiti", [])
        nuovo["bank"] = [{**{k: m[k] for k in ("date", "desc", "in", "out", "cat", "rec", "cp", "conto")},
                          **({"gir": m["gir"]} if m.get("gir") else {})} for m in mov]
        settimane_con_ricavi = sorted(k for k in per_sett if k in cal and per_sett[k]["ricavi"] > 0)
        nuovo["weeks"] = [{"date": cal[w]["start"].isoformat(), "amount": round(per_sett[w]["ricavi"], 2)}
                          for w in settimane_con_ricavi]

        # La scheda Delta 2025/2026 si compila a mano e resta indietro: qui si
        # riempie dai movimenti veri, così il confronto con il 2025 è aggiornato
        # senza ridigitare nulla. La descrizione elenca le fatture della settimana,
        # perché un numero senza il suo perché non serve a chi lo rilegge fra un mese.
        delta = dict(nuovo.get("deltaEdits") or {})
        for w in settimane_con_ricavi:
            voci = [m for m in mov if m["settimana"] == w and e_ricavo(m, regole)]
            def _euro(n):  # solo il numero va convertito in formato italiano, non il nome
                return f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
            desc = " | ".join(f"{m['cp'] or 'senza controparte'} ({_euro(m['in'])})"
                              for m in sorted(voci, key=lambda m: -m["in"]))
            delta[str(w)] = {"amt26": round(per_sett[w]["ricavi"], 2), "desc26": desc[:400]}
        nuovo["deltaEdits"] = delta
        Path(a.out_json).write_text(json.dumps(
            {"schema": "bellavista-financial", "schemaVersion": 1,
             "exportedAt": datetime.datetime.now().isoformat(), "data": nuovo},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 Stato per l'app: `{a.out_json}`")


def cmd_debiti(a):
    """Реестр долгов и требований по контрагентам."""
    regole = carica_regole(a.regole)
    mov, meta = leggi_estratto(a.estratto, regole, a.anno)
    if meta.get("errore"):
        print(f"❌ {meta['errore']}")
        sys.exit(1)
    cat_debito = set(a.categorie.split(",")) if a.categorie else {"Finanziamento IC"}

    per = {}
    for m in mov:
        if m["cat"] not in cat_debito:
            continue
        cp = m["cp"] or "(controparte non riconosciuta)"
        k = chiave_controparte(cp) or cp
        r = per.setdefault(k, {"nome": cp, "ricevuto": 0.0, "restituito": 0.0, "n": 0, "righe": []})
        if len(cp) > len(r["nome"]):   # si tiene la forma più completa del nome
            r["nome"] = cp
        r["ricevuto"] += m["in"]
        r["restituito"] += m["out"]
        r["n"] += 1
        r["righe"].append(m)

    righe = sorted(((v["nome"], v) for v in per.values()),
                   key=lambda x: -abs(x[1]["ricevuto"] - x[1]["restituito"]))
    tot_deb = sum(max(0.0, v["ricevuto"] - v["restituito"]) for _, v in righe)
    tot_cre = sum(max(0.0, v["restituito"] - v["ricevuto"]) for _, v in righe)

    out = ["# Debiti e crediti per controparte", "",
           f"Categorie considerate: {', '.join(sorted(cat_debito))}", "",
           f"- Debiti aperti (da restituire): **{eur(tot_deb)}**",
           f"- Crediti aperti (da incassare): **{eur(tot_cre)}**",
           f"- Posizione netta: **{eur(tot_deb - tot_cre)}**", "",
           "| Controparte | Posizione | Ricevuto | Restituito | Saldo aperto | Mov. |",
           "|---|---|---|---|---|---|"]
    for cp, v in righe:
        saldo = v["ricevuto"] - v["restituito"]
        pos = "Debito" if saldo > 0.005 else ("Credito" if saldo < -0.005 else "Chiuso")
        out.append(f"| {cp} | {pos} | {eur(v['ricevuto']) if v['ricevuto'] else '—'} | "
                   f"{eur(v['restituito']) if v['restituito'] else '—'} | {eur(abs(saldo))} | {v['n']} |")
    rapporto = "\n".join(out)
    print(rapporto)
    if a.out_report:
        Path(a.out_report).write_text(rapporto, encoding="utf-8")
    if a.out_csv:
        rows = [["Controparte", "Data", "Causale", "Ricevuto", "Restituito", "Categoria"]]
        for cp, v in righe:
            for m in sorted(v["righe"], key=lambda x: x["date"]):
                rows.append([cp, m["date"], m["desc"], f"{m['in']:.2f}", f"{m['out']:.2f}", m["cat"]])
        with open(a.out_csv, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f, delimiter=";").writerows(rows)
        print(f"\n💾 Dettaglio: `{a.out_csv}`")


def main():
    ap = argparse.ArgumentParser(description="Недельное закрытие Bellavista")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("weeks", help="календарь недель FRS")
    w.add_argument("--anno", type=int, default=datetime.date.today().year)
    w.add_argument("--data", help="показать неделю для конкретной даты")
    w.set_defaults(func=cmd_weeks)

    f = sub.add_parser("fondi", help="распределение суммы по фондам FRS")
    f.add_argument("importo", type=float)
    f.add_argument("--stato", help="JSON-выгрузка из приложения (берёт оттуда проценты)")
    f.set_defaults(func=cmd_fondi)

    e = sub.add_parser("estratto", help="разбор выписки Banco BPM")
    e.add_argument("file")
    e.add_argument("--stato")
    e.add_argument("--regole")
    e.add_argument("--anno", type=int)
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_estratto)

    c = sub.add_parser("chiusura", help="полное закрытие недели")
    c.add_argument("--estratto", required=True)
    c.add_argument("--stato")
    c.add_argument("--regole")
    c.add_argument("--anno", type=int)
    c.add_argument("--settimana", type=int, help="по умолчанию — последняя неделя в выписке")
    c.add_argument("--out-json", help="куда записать обновлённое состояние для импорта в приложение")
    c.add_argument("--out-report", help="куда записать отчёт в Markdown")
    c.set_defaults(func=cmd_chiusura)

    pr = sub.add_parser("periodo", help="riconciliazione di tutte le settimane in una volta")
    pr.add_argument("--estratto", required=True)
    pr.add_argument("--stato")
    pr.add_argument("--regole")
    pr.add_argument("--anno", type=int)
    pr.add_argument("--out-json", help="stato da importare nell'app")
    pr.add_argument("--out-report", help="rapporto in Markdown")
    pr.add_argument("--out-matrice", help="CSV con il dettaglio settimana × categoria")
    pr.set_defaults(func=cmd_periodo)

    db = sub.add_parser("debiti", help="registro debiti/crediti per controparte")
    db.add_argument("--estratto", required=True)
    db.add_argument("--regole")
    db.add_argument("--anno", type=int)
    db.add_argument("--categorie", help="categorie di natura debito/credito, separate da virgola")
    db.add_argument("--out-report")
    db.add_argument("--out-csv")
    db.set_defaults(func=cmd_debiti)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
