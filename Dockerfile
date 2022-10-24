# EOL: April 2027
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y curl python3 python3-pip tini && rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH=/root/.local/bin:$PATH
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /src

COPY pyproject.toml poetry.lock /src/
RUN poetry install

COPY cron.py tidier.py /src/

# Logs, logs, logs...
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["./cron.py"]
