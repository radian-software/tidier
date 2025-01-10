# EOL: April 2027
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y curl python3-pip python3-venv tini && rm -rf /var/lib/apt/lists/*
RUN pip3 install "poetry>=1.7,<1.8"

RUN python3 -m venv /venv
ENV VIRTUAL_ENV=/venv
ENV PATH=/venv/bin:$PATH

COPY pyproject.toml poetry.lock /src/
WORKDIR /src
RUN poetry install --no-root

COPY cron.py tidier.py /src/

# Logs, logs, logs...
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["./cron.py"]
