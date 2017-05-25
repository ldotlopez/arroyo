# python3 is removable?
# Add certify into requirements.txt

FROM alpine:latest

LABEL description="arroyo container"
LABEL maintainer="ldotlopez@gmail.com"
LABEL version="0"

ENTRYPOINT ["/app/arroyo/entrypoint.sh"]
CMD ["--help"]

RUN mkdir -p /app/{data,arroyo} && \
    adduser -h /app/data -D -g '' arroyo

RUN apk add --no-cache  --update \
        ca-certificates \
        python3 \
        openssl \
        libxml2 \
        libxslt \
        libffi && \
    apk add --no-cache --virtual .build-deps \
        python3-dev \
        py-pip \
        git \
        build-base \
        openssl-dev \
        libxml2-dev \
        libxslt-dev \
        libffi-dev

COPY requirements.txt /tmp/requirements.txt

RUN pip3 install \
        -r /tmp/requirements.txt \
        certify

RUN apk del --no-cache .build-deps

COPY . /app/arroyo

USER arroyo
