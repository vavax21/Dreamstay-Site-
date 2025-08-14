from flask import Flask, render_template_string, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os, io, csv, secrets
from datetime import datetime, date
from sqlalchemy import case, func

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

# Força o banco remoto do Render
db_url = os.environ.get('DATABASE_URL') or \
    "postgresql://dreamstay_db_4t0w_user:pMB0YohKy1V0feXSuszfK9jEao6c8ZRK@dpg-d2f44dk9c44c73dpp7kg-a.oregon-postgres.render.com/dreamstay_db_4t0w"

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Models ----------
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    value = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)

with app.app_context():
    db.create_all()

# ---------- Utils ----------
def get_totals():
    receita = db.session.query(func.coalesce(func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Receita', Transaction.status!='Cancelado').scalar()
    despesa = db.session.query(func.coalesce(func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Despesa', Transaction.status!='Cancelado').scalar()
    return receita, despesa, receita - despesa

def group_by_category():
    receita_expr = func.sum(case((Transaction.type=='Receita', Transaction.value), else_=0))
    despesa_expr = func.sum(case((Transaction.type=='Despesa', Transaction.value), else_=0))
    
    rows = db.session.query(
        Transaction.category,
        receita_expr.label('receita'),
        despesa_expr.label('despesa')
    ).group_by(Transaction.category)\
     .order_by((receita_expr + despesa_expr).desc())\
     .all()
    return rows

def group_by_type():
    rows = db.session.query(Transaction.type, func.sum(Transaction.value).label('total'))\
        .group_by(Transaction.type).all()
    return rows

def recent_transactions(limit=10):
    return Transaction.query.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).all()

# ---------- Routes ----------
@app.route("/")
def index():
    receita, despesa, lucro = get_totals()
    by_cat = group_by_category()
    by_type = group_by_type()
    recent = recent_transactions()

    cat_labels = [r.category for r in by_cat] or ["Sem dados"]
    cat_values = [float(r.receita + r.despesa) for r in by_cat] or [0]
    type_labels = [r.type for r in by_type] or ["Receita", "Despesa"]
    type_values = [float(r.total) for r in by_type] or [0,0]
    palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f']

    html = '''...'''  # Mantém o template que você já tinha

    return render_template_string(html, receita=receita, despesa=despesa, lucro=lucro,
                                  recent=recent, cat_labels=cat_labels, cat_values=cat_values,
                                  type_labels=type_labels, type_values=type_values, palette=palette)

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method=="POST":
        date_str = request.form.get("date") or date.today().isoformat()
        try: date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except: flash("Data inválida","error"); return redirect(url_for("add"))

        typ = request.form.get("type","").strip()
        cat = request.form.get("category","").strip() or "Outros"
        desc = request.form.get("description","").strip()
        status = request.form.get("status","").strip()
        try: val = float(request.form.get("value","0").replace(",",".")) 
        except: flash("Valor inválido","error"); return redirect(url_for("add"))

        if typ not in ("Receita","Despesa"): flash("Tipo inválido","error")
        elif status not in ("Pago","Pendente"): flash("Status inválido","error")
        else:
            db.session.add(Transaction(date=date_obj,type=typ,category=cat,description=desc,value=val,status=status))
            db.session.commit(); flash("Transação adicionada","success"); return redirect(url_for("index"))

    form_html = '''...'''  # Mantém o template do formulário
    return render_template_string(form_html, today=date.today().isoformat())

@app.route("/delete/<int:tid>", methods=["POST"])
def delete(tid):
    t = Transaction.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    flash("Transação deletada","success")
    return redirect(url_for("index"))

@app.route("/export.csv")
def export_csv():
    rows = Transaction.query.order_by(Transaction.date.asc(), Transaction.id.asc()).all()
    si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(["id","date","type","category","description","value","status"])
    for r in rows: cw.writerow([r.id,r.date,r.type,r.category,r.description,r.value,r.status])
    mem = io.BytesIO(); mem.write(si.getvalue().encode("utf-8")); mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="transacoes.csv", mimetype="text/csv")

if __name__=="__main__":
    app.run(debug=True)
