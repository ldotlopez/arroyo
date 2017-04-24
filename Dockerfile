FROM debian:stable

LABEL description="arroyo container"
LABEL maintainer="ldotlopez@gmail.com"
LABEL version="0"

COPY . /app/arroyo
RUN apt-get update
RUN apt-get install -y python3 python3-dev virtualenv git build-essential zlib1g-dev libyaml-dev libxml2-dev libxslt1-dev
RUN /usr/bin/virtualenv -p python3 /app/env
RUN /app/env/bin/pip install -r /app/arroyo/requirements.txt 
RUN adduser --home /app/data --disabled-password --gecos '' arroyo
RUN apt-get autoremove --purge -y python3-dev git build-essential zlib1g-dev libyaml-dev libxml2-dev libxslt1-dev
RUN rm /var/cache/apt/*.deb

USER arroyo
ENV LANG C.UTF-8
ENTRYPOINT ["/app/arroyo/entrypoint.sh"]
CMD ["--help"]
