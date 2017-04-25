# python3 is removable?
# Add certify into requirements.txt

FROM alpine:latest

LABEL description="arroyo container"
LABEL maintainer="ldotlopez@gmail.com"
LABEL version="0"

COPY . /app/arroyo
RUN                                             \
    rm -rf /app/arroyo/.git*                    \
    && apk add --no-cache  --update             \
        ca-certificates                         \
        python3                                 \
        openssl                                 \
        libxml2                                 \
        libxslt                                 \
        libffi                                  \
    && apk add --no-cache --virtual .build-deps \
        python3-dev                             \
        py-pip                                  \
        git                                     \
        build-base                              \
        openssl-dev                             \
        libxml2-dev                             \
        libxslt-dev                             \
        libffi-dev                              \
    && pip3 install virtualenv                  \
    && /usr/bin/virtualenv -p python3 /app/env  \
    && /app/env/bin/pip install                 \
        --upgrade pip                           \
    && /app/env/bin/pip install                 \
        -r /app/arroyo/requirements.txt         \
        certify                                 \
    && apk del --no-cache .build-deps           \
    && adduser -h /app/data -D -g '' arroyo

USER arroyo
ENTRYPOINT ["/app/arroyo/entrypoint.sh"]
CMD ["--help"]
