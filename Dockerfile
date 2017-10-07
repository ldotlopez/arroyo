FROM alpine:latest

LABEL description="arroyo container"
LABEL maintainer="ldotlopez@gmail.com"
LABEL version="0"

# Point entrypoint to our script
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["--help"]

# Setup app and data dirs
RUN \
    adduser -h "/app" -D -g '' arroyo && \
    mkdir /data                       && \
    chown -R arroyo:arroyo /app /data

# Install required packages
RUN \
    apk add --no-cache  --update                \
        ca-certificates                         \
        libffi                                  \
        libxml2                                 \
        libxslt                                 \
        openssl                                 \
        python3                                 \
        sudo                                    \
    && apk add --no-cache --virtual .build-deps \
        build-base                              \
        git                                     \
        libffi-dev                              \
        libxml2-dev                             \
        libxslt-dev                             \
        openssl-dev                             \
        python3-dev

# Install requirements
COPY requirements.txt /tmp/requirements.txt
RUN \
    pip3 install --upgrade -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Remove leftovers
RUN apk del --no-cache .build-deps

# Copy and clean arroyo code
COPY . /app
RUN \
    cd /app               && \
    rm .gitignore         && \
    git reset HEAD --hard && \
    git clean -f -d       && \
    rm -rf .git

