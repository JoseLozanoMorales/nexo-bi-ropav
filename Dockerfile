FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY weekly_analysis.py ./
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY objective_dashboards.py objective_charts.js ./
COPY app.py db.py mcp_server.py ai_chat.py dashboard_builder.py recommendations.py semantic_analytics.py statistical_charts.py index.html app.js dashboard.js styles.css integrations.css chat.css ./
COPY ["PROGRAMA EMPRESARIAL", "PROGRAMA EMPRESARIAL"]
EXPOSE 8000
CMD ["python", "app.py"]
