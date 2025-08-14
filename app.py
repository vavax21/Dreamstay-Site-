from flask import Flask, render_template_string, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os, io, csv, secrets
from datetime import datetime, date
from sqlalchemy import case, func

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

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
    lucro = receita - despesa
    percentual = (lucro/receita*100 if receita>0 else 0)
    return receita, despesa, lucro, percentual

def group_by_category():
    receita_expr = func.sum(case((Transaction.type=='Receita', Transaction.value), else_=0))
    despesa_expr = func.sum(case((Transaction.type=='Despesa', Transaction.value), else_=0))
    
    rows = db.session.query(
        Transaction.category,
        receita_expr.label('receita'),
        despesa_expr.label('despesa')
    ).group_by(Transaction.category).order_by((receita_expr + despesa_expr).desc()).all()
    return rows

def group_by_type():
    rows = db.session.query(Transaction.type, func.sum(Transaction.value).label('total'))\
        .group_by(Transaction.type).all()
    return rows

def transactions_filtered(start=None, end=None, category=None):
    q = Transaction.query
    if start: q = q.filter(Transaction.date>=start)
    if end: q = q.filter(Transaction.date<=end)
    if category and category!="Todos": q = q.filter(Transaction.category==category)
    return q.order_by(Transaction.date.desc(), Transaction.id.desc()).all()

# ---------- Routes ----------
@app.route("/", methods=["GET","POST"])
def index():
    start = request.form.get("start_date")
    end = request.form.get("end_date")
    category_filter = request.form.get("category") or "Todos"

    try:
        start_date = datetime.strptime(start,"%Y-%m-%d").date() if start else None
        end_date = datetime.strptime(end,"%Y-%m-%d").date() if end else None
    except:
        start_date, end_date = None, None

    receita, despesa, lucro, percentual = get_totals()
    by_cat = group_by_category()
    by_type = group_by_type()
    recent = transactions_filtered(start_date,end_date,category_filter)

    cat_labels = [r.category for r in by_cat] or ["Sem dados"]
    cat_values = [float(r.receita + r.despesa) for r in by_cat] or [0]
    type_labels = [r.type for r in by_type] or ["Receita","Despesa"]
    type_values = [float(r.total) for r in by_type] or [0,0]
    all_categories = ["Todos"] + [r.category for r in by_cat]
    palette = ['#007bff','#28a745','#dc3545','#ffc107','#17a2b8','#6f42c1','#fd7e14','#6c757d']

    html = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Dashboard Financeiro</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', sans-serif; }
body { background:#f0f2f5; padding:20px; color:#333; }
header { text-align:center; margin-bottom:30px; }
h1 { color:#222; }
.cards { display:flex; flex-wrap:wrap; gap:20px; justify-content:center; margin-bottom:40px; }
.card { flex:1 1 200px; background:#fff; border-radius:12px; padding:20px; box-shadow:0 4px 12px rgba(0,0,0,0.08); text-align:center; transition: transform 0.2s; }
.card:hover { transform:translateY(-5px); }
.card h2 { font-size:1.1em; color:#555; margin-bottom:10px; }
.card p { font-size:1.8em; font-weight:bold; }
.charts { display:flex; flex-wrap:wrap; gap:30px; justify-content:center; margin-bottom:40px; }
canvas { background:#fff; border-radius:12px; padding:15px; box-shadow:0 4px 10px rgba(0,0,0,0.05); }
table { width:100%; border-collapse:collapse; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 4px 10px rgba(0,0,0,0.05); margin-bottom:40px; }
th, td { padding:12px 15px; text-align:center; }
th { background:#007bff; color:#fff; }
tr:nth-child(even) { background:#f9f9f9; }
tr:hover { background:#e6f0ff; }
.status-pago { color:green; font-weight:bold; }
.status-pendente { color:orange; font-weight:bold; }
button { padding:6px 12px; border:none; border-radius:6px; background:#dc3545; color:#fff; cursor:pointer; transition: background 0.2s; }
button:hover { background:#c82333; }
a { text-decoration:none; color:#007bff; margin:0 10px; }
a:hover { text-decoration:underline; }
.actions { text-align:center; margin-bottom:40px; }
.filter-form { text-align:center; margin-bottom:30px; }
input, select, button { padding:8px 12px; border-radius:6px; border:1px solid #ccc; margin:0 5px; }
</style>
</head>
<body>
<header><h1>Dashboard Financeiro Ultimate</h1></header>

<div class="cards">
<div class="card"><h2>Receita</h2><p style="color:green;">R$ {{ receita }}</p></div>
<div class="card"><h2>Despesa</h2><p style="color:red;">R$ {{ despesa }}</p></div>
<div class="card"><h2>Lucro</h2><p style="color:{% if lucro>=0 %}green{% else %}red{% endif %}">R$ {{ lucro }}</p></div>
<div class="card"><h2>% Lucro</h2><p style="color:{% if percentual>=0 %}green{% else %}red{% endif %}">{{ "%.2f"|format(percentual) }}%</p></div>
</div>

<div class="filter-form">
<form method="POST">
Data início: <input type="date" name="start_date" value="{{ start }}">
Data fim: <input type="date" name="end_date" value="{{ end }}">
Categoria: <select name="category">{% for cat in all_categories %}<option value="{{ cat }}" {% if category_filter==cat %}selected{% endif %}>{{ cat }}</option>{% endfor %}</select>
<button type="submit">Filtrar</button>
</form>
</div>

<div class="charts">
<canvas id="typeChart" width="300" height="300"></canvas>
<canvas id="catChart" width="600" height="300"></canvas>
</div>

<h2 style="text-align:center; margin-bottom:20px;">Transações Recentes</h2>
<table>
<tr><th>Data</th><th>Tipo</th><th>Categoria</th><th>Descrição</th><th>Valor</th><th>Status</th><th>Ações</th></tr>
{% for t in recent %}
<tr>
<td>{{ t.date }}</td>
<td>{{ t.type }}</td>
<td>{{ t.category }}</td>
<td>{{ t.description }}</td>
<td>R$ {{ t.value }}</td>
<td class="status-{{ t.status.lower() }}">{{ t.status }}</td>
<td>
<form style="display:inline;" action="{{ url_for('delete', tid=t.id) }}" method="post"><button type="submit">Deletar</button></form>
</td>
</tr>
{% endfor %}
</table>

<div class="actions">
<a href="{{ url_for('add') }}">Adicionar Transação</a> | 
<a href="{{ url_for('export_csv') }}">Exportar CSV</a>
</div>

<script>
const typeCtx = document.getElementById('typeChart').getContext('2d');
new Chart(typeCtx, {
type:'doughnut',
data:{labels:{{ type_labels|tojson }}, datasets:[{data:{{ type_values|tojson }}, backgroundColor:{{ palette|tojson }}}]},
options:{plugins:{legend:{position:'bottom'}}, responsive:true}
});

const catCtx = document.getElementById('catChart').getContext('2d');
new Chart(catCtx,{
type:'bar',
data:{labels:{{ cat_labels|tojson }}, datasets:[{label:'Total por Categoria', data:{{ cat_values|tojson }}, backgroundColor:{{ palette|tojson }}}]},
options:{responsive:true, plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}, x:{ticks:{autoSkip:false}}}}
});
</script>
</body>
</html>
"""
    return render_template_string(html, receita=receita, despesa=despesa, lucro=lucro, percentual=percentual,
                                  recent=recent, cat_labels=cat_labels, cat_values=cat_values,
                                  type_labels=type_labels, type_values=type_values, palette=palette,
                                  start=start or '', end=end or '', all_categories=all_categories,
                                  category_filter=category_filter)

@app.route("/add", methods=["GET","POST"])
def add():
    if request.method=="POST":
        date_str = request.form.get("date") or date.today().isoformat()
        try: date_obj = datetime.strptime(date_str,"%Y-%m-%d").date()
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
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Adicionar Transação</title>
<style>
body{background:#f0f2f5; font-family:'Segoe UI',sans-serif; padding:30px;}
h1{text-align:center; margin-bottom:20px;}
form{background:#fff; padding:20px; border-radius:12px; max-width:500px; margin:auto; box-shadow:0 4px 10px rgba(0,0,0,0.08);}
input, select, button{width:100%; padding:10px; margin:10px 0; border-radius:6px; border:1px solid #ccc;}
button{background:#007bff; color:#fff; border:none; cursor:pointer;}
button:hover{background:#0056b3;}
a{display:block; text-align:center; margin-top:15px; color:#007bff; text-decoration:none;}
a:hover{text-decoration:underline;}
</style>
</head>
<body>
<h1>Adicionar Transação</h1>
<form method="POST">
Data: <input type="date" name="date" value="{{ today }}">
Tipo: <select name="type"><option>Receita</option><option>Despesa</option></select>
Categoria: <input type="text" name="category">
Descrição: <input type="text" name="description">
Valor: <input type="text" name="value">
Status: <select name="status"><option>Pago</option><option>Pendente</option></select>
<button type="submit">Adicionar</button>
</form>
<a href="{{ url_for('index') }}">Voltar ao Dashboard</a>
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
