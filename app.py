from flask import Flask, render_template_string, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os, io, csv, secrets
from datetime import datetime, date
from sqlalchemy import case, func

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

# Banco remoto
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

    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Dashboard Financeiro</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f4f6f8; color: #333; }
        h1 { color: #333; }
        .cards { display: flex; gap: 20px; margin-bottom: 30px; }
        .card { flex: 1; padding: 20px; border-radius: 10px; background: #fff; box-shadow: 0 3px 6px rgba(0,0,0,0.1); text-align: center; }
        .card h2 { margin: 0; font-size: 1.2em; }
        .card p { font-size: 1.5em; margin: 5px 0; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        th, td { padding: 12px 15px; text-align: left; }
        th { background: #007bff; color: #fff; }
        tr:nth-child(even) { background: #f9f9f9; }
        .status-pago { color: green; font-weight: bold; }
        .status-pendente { color: orange; font-weight: bold; }
        a { text-decoration: none; color: #007bff; }
        a:hover { text-decoration: underline; }
        button { padding: 5px 10px; border: none; border-radius: 4px; background: #dc3545; color: #fff; cursor: pointer; }
        button:hover { background: #c82333; }
    </style>
</head>
<body>
    <h1>Dashboard Financeiro</h1>
    <div class="cards">
        <div class="card">
            <h2>Receita</h2>
            <p style="color: green;">{{ receita }}</p>
        </div>
        <div class="card">
            <h2>Despesa</h2>
            <p style="color: red;">{{ despesa }}</p>
        </div>
        <div class="card">
            <h2>Lucro</h2>
            <p style="color: {% if lucro >=0 %}green{% else %}red{% endif %};">{{ lucro }}</p>
        </div>
    </div>

    <canvas id="catChart" width="400" height="200"></canvas>
    <canvas id="typeChart" width="400" height="200" style="margin-top:30px;"></canvas>

    <h2>Transações Recentes</h2>
    <table>
        <tr><th>Data</th><th>Tipo</th><th>Categoria</th><th>Descrição</th><th>Valor</th><th>Status</th><th>Ações</th></tr>
        {% for t in recent %}
        <tr>
            <td>{{ t.date }}</td>
            <td>{{ t.type }}</td>
            <td>{{ t.category }}</td>
            <td>{{ t.description }}</td>
            <td>{{ t.value }}</td>
            <td class="status-{{ t.status.lower() }}">{{ t.status }}</td>
            <td>
                <form style="display:inline;" action="{{ url_for('delete', tid=t.id) }}" method="post">
                    <button type="submit">Deletar</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>

    <p><a href="{{ url_for('add') }}">Adicionar Transação</a> | <a href="{{ url_for('export_csv') }}">Exportar CSV</a></p>

<script>
    const catCtx = document.getElementById('catChart').getContext('2d');
    new Chart(catCtx, {
        type: 'bar',
        data: {
            labels: {{ cat_labels|tojson }},
            datasets: [{
                label: 'Total por Categoria',
                data: {{ cat_values|tojson }},
                backgroundColor: {{ palette|tojson }}
            }]
        },
        options: { responsive: true }
    });

    const typeCtx = document.getElementById('typeChart').getContext('2d');
    new Chart(typeCtx, {
        type: 'doughnut',
        data: {
            labels: {{ type_labels|tojson }},
            datasets: [{
                label: 'Total por Tipo',
                data: {{ type_values|tojson }},
                backgroundColor: {{ palette|tojson }}
            }]
        },
        options: { responsive: true }
    });
</script>
</body>
</html>
"""

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

    form_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Adicionar Transação</title>
</head>
<body>
<h1>Adicionar Transação</h1>
<form method="POST">
    Data: <input type="date" name="date" value="{{ today }}"><br>
    Tipo: 
    <select name="type">
        <option>Receita</option>
        <option>Despesa</option>
    </select><br>
    Categoria: <input type="text" name="category"><br>
    Descrição: <input type="text" name="description"><br>
    Valor: <input type="text" name="value"><br>
    Status: 
    <select name="status">
        <option>Pago</option>
        <option>Pendente</option>
    </select><br>
    <button type="submit">Adicionar</button>
</form>
<p><a href="{{ url_for('index') }}">Voltar</a></p>
</body>
</html>
"""
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
