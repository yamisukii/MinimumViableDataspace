# AM2Scale host services in one image: documentation, discovery (and later the
# portal). One container runs them together via ui/serve_all.py, one port each.
#
# Build from the repository root, because the docs service also serves the
# Markdown that lives outside ui/:
#     podman build -t am2scale-ui:latest -f ui/Dockerfile .
FROM python:3.12-slim

# numpy + model2vec are only needed by discovery, openpyxl by the dataset import.
# No compiler needed - all three ship wheels.
RUN pip install --no-cache-dir \
        "numpy==2.4.2" \
        "model2vec==0.8.2" \
        "openpyxl==3.1.5"

# Bake the embedding model into the image so the container never needs the
# network. HF_HUB_OFFLINE below makes that a hard guarantee at runtime.
ENV HF_HOME=/opt/hf \
    HF_HUB_DISABLE_SYMLINKS=1
RUN python -c "from model2vec import StaticModel; StaticModel.from_pretrained('minishlab/potion-base-8M')" \
    && find /opt/hf -name "*.lock" -delete

WORKDIR /app

# the services themselves
COPY ui/ /app/ui/
# the documentation the docs service publishes (paths must mirror the repo,
# because ui/docs/server.py resolves them relative to the repo root)
COPY README.md /app/README.md
COPY docs/ /app/docs/
COPY compose/README.md /app/compose/README.md

# runtime state of discovery (knowledge graph + vector index) -> volume
RUN mkdir -p /data
VOLUME ["/data"]

ENV BIND_HOST=0.0.0.0 \
    SERVICES=docs,discovery \
    DOCS_PORT=5190 \
    DISCOVERY_PORT=5185 \
    DISCOVERY_DATA_DIR=/data \
    HF_HUB_OFFLINE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5185 5190

# docs answers immediately; discovery needs a moment to load the model, so the
# start period covers that rather than flapping the container
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,os,sys;\
urllib.request.urlopen('http://127.0.0.1:'+os.environ['DOCS_PORT']+'/api/health',timeout=4);\
urllib.request.urlopen('http://127.0.0.1:'+os.environ['DISCOVERY_PORT']+'/health',timeout=4)"

CMD ["python", "ui/serve_all.py"]
