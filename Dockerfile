# --- 1) Build the React app ---------------------------------------------
FROM node:20-slim AS web
WORKDIR /web
# package-lock.json was generated on Windows; installing from package.json
# lets npm pick the Linux-native Rollup/esbuild binaries.
COPY nse-terminal/package.json ./
RUN npm install --no-audit --no-fund
COPY nse-terminal/ ./
RUN rm -rf node_modules/.vite && npm run build

# --- 2) Flask API + static site -----------------------------------------
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PORT=10000 \
    DB_PATH=/tmp/stock_market.db
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY app.py stock_extractor.py predictor.py ./
COPY data ./data
COPY --from=web /web/dist ./nse-terminal/dist

EXPOSE 10000
# One worker: the quote scheduler and refresh state live in-process.
# Threads handle concurrent requests.
CMD gunicorn app:app --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT}
