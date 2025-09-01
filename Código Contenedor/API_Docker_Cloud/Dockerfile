FROM python:3.12

WORKDIR /app
COPY app/ /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod -R a+rx /usr/local/bin

RUN mkdir -p /workdir

EXPOSE 8080

RUN apt-get update && apt-get install -y xvfb imagemagick openbox wmctrl git
ENV DISPLAY=:99

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev && rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash nimbus

RUN chown -R nimbus:nimbus /usr/local/lib/python3.12/site-packages

RUN chown -R nimbus:nimbus /workdir

RUN chown -R nimbus:nimbus /usr/local/bin

RUN chown -R nimbus:nimbus /usr/local/share/man/man1 && chmod -R a+rwX /usr/local/share/man/man1



USER nimbus

CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x24 & openbox & python api.py"]