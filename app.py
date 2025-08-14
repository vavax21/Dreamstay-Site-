from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os
import io
import csv
from datetime import date

APP_TITLE = "Dreamstay - Finanças"

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret"  # necessário para flash messages

# ------------- DB Setup -------------
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError("A variável de ambiente DATABASE_URL não está definida!")

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'Receita' ou 'Despesa'
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    value = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'Pago' ou 'Pendente'

with app.app_context():
    db.create_all()  # cria as tabelas no PostgreSQL

# ------------- Utils -------------
def get_totals():
    total_receita = db.session.query(db.func.coalesce(db.func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Receita', Transaction.status!='Cancelado').scalar()
    total_despesa = db.session.query(db.func.coalesce(db.func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Despesa', Transaction.status!='Cancelado').scalar()
    lucro = total_receita - total_despesa
    return total_receita, total_despesa, lucro

def group_by_category():
    rows = db.session.query(
        Transaction.category,
        db.func.sum(db.case([(Transaction.type=='Receita', Transaction.value)], else_=0)).label('receita'),
        db.func.sum(db.case([(Transaction.type=='Despesa', Transaction.value)], else_=0)).label('despesa')
    ).group_by(Transaction.category).order_by(db.text('receita + despesa DESC')).all()
    return rows

def group_by_type():
    rows = db.session.query(
        Transaction.type,
        db.func.sum(Transaction.value).label('total')
    ).group_by(Transaction.type).all()
    return rows

def recent_transactions(limit=10):
    return Transaction.query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()

# ------------- Routes -------------
@app.route("/")
def index():
    total_receita, total_despesa, lucro = get_totals()
    by_cat = group_by_category()
    by_type = group_by_type()
    recent = recent_transactions(10)

    cat_labels = [r.category for r in by_cat]
    cat_values = [float(r.receita + r.despesa) for r in by_cat]

    type_labels = [r.type for r in by_type]
    type_values = [float(r.total) for r in by_type]

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
    if request.method == "POST":
        date_str = request.form.get("date") or date.today().isoformat()
        typ = request.form.get("type", "").strip()
        category = request.form.get("category", "").strip() or "Outros"
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "").strip()

        try:
            value = float(request.form.get("value", "0").replace(",", "."))
        except ValueError:
            value = -1

        if typ not in ("Receita", "Despesa"):
            flash("Tipo inválido. Use Receita ou Despesa.", "error")
        elif status not in ("Pago", "Pendente"):
            flash("Status inválido. Use Pago ou Pendente.", "error")
        elif value < 0:
            flash("Valor inválido.", "error")
        else:
            t = Transaction(date=date_str, type=typ, category=category, description=description, value=value, status=status)
            db.session.add(t)
            db.session.commit()
            flash("Transação adicionada.", "success")
            return redirect(url_for("index"))

    return render_template("add.html", app_title=APP_TITLE, today=date.today().isoformat())

@app.route("/transactions")
def transactions():
    rows = Transaction.query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    return render_template("transactions.html", app_title=APP_TITLE, rows=rows)

@app.route("/delete/<int:tid>", methods=["POST"])
def delete(tid):
    t = Transaction.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    flash("Transação removida.", "success")
    return redirect(url_for("transactions"))

@app.route("/export.csv")
def export_csv():
    rows = Transaction.query.order_by(Transaction.date.asc(), Transaction.id.asc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id", "date", "type", "category", "description", "value", "status"])
    for r in rows:
        cw.writerow([r.id, r.date, r.type, r.category, r.description, r.value, r.status])
    mem = io.BytesIO()
    mem.write(si.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="transacoes.csv", mimetype="text/csv")

if __name__ == "__main__":
    app.run(debug=True)
