
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import sqlite3
import os
import io
import csv
from datetime import date

APP_TITLE = "Finanças Airbnb - Local"
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret"  # necessário para flash messages

# ------------- DB helpers -------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Receita','Despesa')),
            category TEXT NOT NULL,
            description TEXT,
            value REAL NOT NULL CHECK(value >= 0),
            status TEXT NOT NULL CHECK(status IN ('Pago','Pendente'))
        );
    """)
    conn.commit()
    conn.close()

def fetchall(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

# ------------- Utils -------------
def get_totals():
    # Totais por tipo
    row = fetchall("SELECT IFNULL(SUM(value),0) as total FROM transactions WHERE type='Receita' AND status!='Cancelado'")
    total_receita = row[0]["total"] if row else 0.0
    row = fetchall("SELECT IFNULL(SUM(value),0) as total FROM transactions WHERE type='Despesa' AND status!='Cancelado'")
    total_despesa = row[0]["total"] if row else 0.0
    lucro = total_receita - total_despesa
    return total_receita, total_despesa, lucro

def group_by_category():
    # Soma por categoria (considera receitas e despesas separadamente)
    rows = fetchall("""
        SELECT category,
               SUM(CASE WHEN type='Receita' THEN value ELSE 0 END) AS receita,
               SUM(CASE WHEN type='Despesa' THEN value ELSE 0 END) AS despesa
        FROM transactions
        GROUP BY category
        ORDER BY (receita + despesa) DESC, category ASC
    """)
    return rows

def group_by_type():
    rows = fetchall("""
        SELECT type, SUM(value) as total
        FROM transactions
        GROUP BY type
        ORDER BY type
    """)
    return rows

def recent_transactions(limit=10):
    rows = fetchall("""
        SELECT * FROM transactions
        ORDER BY date DESC, id DESC
        LIMIT ?
    """, (limit,))
    return rows

# ------------- Routes -------------
@app.route("/")
def index():
    init_db()
    total_receita, total_despesa, lucro = get_totals()
    by_cat = group_by_category()
    by_type = group_by_type()
    recent = recent_transactions(10)

    # Dados para gráficos
    # Pizza por categoria (usaremos a soma absoluta: receita + despesa)
    cat_labels = [r["category"] for r in by_cat]
    cat_values = [float(r["receita"] + r["despesa"]) for r in by_cat]

    # Barras por tipo
    type_labels = [r["type"] for r in by_type]
    type_values = [float(r["total"]) for r in by_type]

    return render_template(
        "index.html",
        app_title=APP_TITLE,
        total_receita=total_receita,
        total_despesa=total_despesa,
        lucro=lucro,
        recent=recent,
        cat_labels=cat_labels,
        cat_values=cat_values,
        type_labels=type_labels,
        type_values=type_values
    )

@app.route("/add", methods=["GET", "POST"])
def add():
    init_db()
    if request.method == "POST":
        # Captura e valida
        date_str = request.form.get("date") or date.today().isoformat()
        typ = request.form.get("type", "").strip()
        category = request.form.get("category", "").strip() or "Outros"
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "").strip()

        try:
            value = float(request.form.get("value", "0").replace(",", "."))
        except ValueError:
            value = -1  # inválido

        if typ not in ("Receita", "Despesa"):
            flash("Tipo inválido. Use Receita ou Despesa.", "error")
        elif status not in ("Pago", "Pendente"):
            flash("Status inválido. Use Pago ou Pendente.", "error")
        elif value < 0:
            flash("Valor inválido.", "error")
        else:
            execute("""
                INSERT INTO transactions(date, type, category, description, value, status)
                VALUES (?,?,?,?,?,?)
            """, (date_str, typ, category, description, value, status))
            flash("Transação adicionada.", "success")
            return redirect(url_for("index"))

    return render_template("add.html", app_title=APP_TITLE, today=date.today().isoformat())

@app.route("/transactions")
def transactions():
    init_db()
    rows = fetchall("""
        SELECT * FROM transactions
        ORDER BY date DESC, id DESC
    """)
    return render_template("transactions.html", app_title=APP_TITLE, rows=rows)

@app.route("/delete/<int:tid>", methods=["POST"])
def delete(tid):
    execute("DELETE FROM transactions WHERE id=?", (tid,))
    flash("Transação removida.", "success")
    return redirect(url_for("transactions"))

@app.route("/export.csv")
def export_csv():
    # exporta todas as transações em CSV
    rows = fetchall("SELECT * FROM transactions ORDER BY date ASC, id ASC")
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "date", "type", "category", "description", "value", "status"])
    for r in rows:
        cw.writerow([r["id"], r["date"], r["type"], r["category"], r["description"], r["value"], r["status"]])
    mem = io.BytesIO()
    mem.write(si.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="transacoes.csv", mimetype="text/csv")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
