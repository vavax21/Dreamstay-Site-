from flask import Flask, render_template_string, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import os, io, csv, secrets
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(16)

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError("Defina DATABASE_URL!")

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
    receita = db.session.query(db.func.coalesce(db.func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Receita', Transaction.status!='Cancelado').scalar()
    despesa = db.session.query(db.func.coalesce(db.func.sum(Transaction.value), 0))\
        .filter(Transaction.type=='Despesa', Transaction.status!='Cancelado').scalar()
    return receita, despesa, receita - despesa

def group_by_category():
    rows = db.session.query(
        Transaction.category,
        db.func.sum(db.case([(Transaction.type=='Receita', Transaction.value)], else_=0)).label('receita'),
        db.func.sum(db.case([(Transaction.type=='Despesa', Transaction.value)], else_=0)).label('despesa')
    ).group_by(Transaction.category).order_by(db.text('receita + despesa DESC')).all()
    return rows

def group_by_type():
    rows = db.session.query(Transaction.type, db.func.sum(Transaction.value).label('total'))\
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

    # Dados para gráficos
    cat_labels = [r.category for r in by_cat] or ["Sem dados"]
    cat_values = [float(r.receita + r.despesa) for r in by_cat] or [0]
    type_labels = [r.type for r in by_type] or ["Receita", "Despesa"]
    type_values = [float(r.total) for r in by_type] or [0,0]

    # Paleta de cores moderna
    palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f']

    html = '''
    <!doctype html>
    <html lang="pt-br">
    <head>
      <meta charset="utf-8">
      <title>Dreamstay - Finanças</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <style>
        body { background: #f8f9fa; }
        .card { border-radius: 0.75rem; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        table th, table td { vertical-align: middle; }
        .btn-primary { background-color: #0d6efd; border: none; }
        .btn-primary:hover { background-color: #0b5ed7; }
        .btn-danger { background-color: #dc3545; border: none; }
        .btn-danger:hover { background-color: #bb2d3b; }
      </style>
    </head>
    <body>
    <div class="container mt-4">
      <h1 class="mb-4 text-center">Dreamstay - Dashboard Financeiro</h1>
      <div class="row g-3 mb-4">
        <div class="col-md-4"><div class="card p-3 text-white bg-success">Receita: <strong>R$ {{receita}}</strong></div></div>
        <div class="col-md-4"><div class="card p-3 text-white bg-danger">Despesa: <strong>R$ {{despesa}}</strong></div></div>
        <div class="col-md-4"><div class="card p-3 text-white bg-primary">Lucro: <strong>R$ {{lucro}}</strong></div></div>
      </div>

      <div class="row g-4 mb-5">
        <div class="col-md-6"><canvas id="catChart" style="height:300px;"></canvas></div>
        <div class="col-md-6"><canvas id="typeChart" style="height:300px;"></canvas></div>
      </div>

      <h3 class="mb-3">Últimas Transações</h3>
      <table class="table table-striped shadow-sm bg-white rounded">
        <thead class="table-dark"><tr>
          <th>Data</th><th>Tipo</th><th>Categoria</th><th>Valor</th><th>Status</th><th>Ações</th>
        </tr></thead>
        <tbody>
        {% for t in recent %}
          <tr>
            <td>{{t.date}}</td><td>{{t.type}}</td><td>{{t.category}}</td>
            <td>R$ {{'%.2f'|format(t.value)}}</td><td>{{t.status}}</td>
            <td>
              <form action="{{ url_for('delete', tid=t.id) }}" method="POST" style="display:inline;">
                <button type="submit" class="btn btn-sm btn-danger" onclick="return confirm('Confirma deletar?')">Deletar</button>
              </form>
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>

      <div class="mb-5">
        <a class="btn btn-primary me-2" href="{{ url_for('add') }}">Adicionar Transação</a>
        <a class="btn btn-secondary" href="{{ url_for('export_csv') }}">Exportar CSV</a>
      </div>
    </div>

    <script>
    const palette = {{ palette|safe }};
    const ctxCat = document.getElementById('catChart').getContext('2d');
    new Chart(ctxCat, { type: 'pie', data: {
        labels: {{ cat_labels|safe }},
        datasets: [{ data: {{ cat_values|safe }}, backgroundColor: palette }]
    }, options: { responsive: true }});

    const ctxType = document.getElementById('typeChart').getContext('2d');
    new Chart(ctxType, { type: 'bar', data: {
        labels: {{ type_labels|safe }},
        datasets: [{ label: 'Total', data: {{ type_values|safe }}, backgroundColor: ['#0d6efd','#dc3545'] }]
    }, options: { responsive: true, scales: { y: { beginAtZero:true }}}});
    </script>
    </body>
    </html>
    '''
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

    form_html = '''
    <!doctype html>
    <html lang="pt-br">
    <head><meta charset="utf-8"><title>Adicionar Transação</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body>
    <div class="container mt-4">
      <h1>Adicionar Transação</h1>
      <form method="POST">
        <div class="mb-3"><label>Data</label><input type="date" name="date" value="{{today}}" class="form-control" required></div>
        <div class="mb-3"><label>Tipo</label>
          <select name="type" class="form-select" required>
            <option value="Receita">Receita</option>
            <option value="Despesa">Despesa</option>
          </select></div>
        <div class="mb-3"><label>Categoria</label><input type="text" name="category" class="form-control"></div>
        <div class="mb-3"><label>Descrição</label><input type="text" name="description" class="form-control"></div>
        <div class="mb-3"><label>Valor</label><input type="number" step="0.01" name="value" class="form-control" required></div>
        <div class="mb-3"><label>Status</label>
          <select name="status" class="form-select" required>
            <option value="Pago">Pago</option>
            <option value="Pendente">Pendente</option>
          </select></div>
        <button type="submit" class="btn btn-primary">Adicionar</button>
        <a href="{{ url_for('index') }}" class="btn btn-secondary">Voltar</a>
      </form>
    </div>
    </body></html>
    '''
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
