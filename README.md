
# Finanças Airbnb - Local (Flask + SQLite + Chart.js)

## Passo a passo (VS Code)

1) **Crie um ambiente virtual (opcional, mas recomendado)**  
   - Windows (PowerShell):
     ```bash
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - macOS / Linux (bash/zsh):
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

2) **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

3) **Execute o servidor**
   ```bash
   python app.py
   ```
   Acesse no navegador: http://127.0.0.1:5000

## Funcionalidades
- Hub com totais de **Receitas**, **Despesas** e **Lucro Líquido**.
- **Formulário** com: Data, Tipo (Receita/Despesa), Categoria, Descrição, Valor, Status (Pago/Pendente).
- **Gráficos** com Chart.js:
  - Pizza: participação por categoria (Receitas + Despesas).
  - Barras: totais por tipo.
- Lista de transações e **exclusão**.
- **Exportar CSV**.

## Observações
- O banco `data.db` (SQLite) é criado automaticamente na primeira execução.
- Os valores devem ser positivos; o sinal (receita/despesa) é definido pelo campo **Tipo**.
- Para começar “zerado”, basta apagar `data.db` (o app recria).
