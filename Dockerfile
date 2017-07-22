FROM alpine:latest

LABEL description="arroyo container"
LABEL maintainer="ldotlopez@gmail.com"
LABEL version="0"

# Install required packages
RUN \
    apk add --no-cache  --update                \
        ca-certificates                         \
        python3                                 \
        openssl                                 \
        libxml2                                 \
        libxslt                                 \
        libffi                                  \
        sudo                                    \
    && apk add --no-cache --virtual .build-deps \
        python3-dev                             \
        git                                     \
        build-base                              \
        openssl-dev                             \
        libxml2-dev                             \
        libxslt-dev                             \
        libffi-dev

# Copy and clean arroyo code
COPY . /app
RUN \
    cd /app               && \
    rm .gitignore         && \
    git reset HEAD --hard && \
    git clean -f -d       && \
    rm -rf .git

# Install requirements
RUN pip3 install --upgrade -r /app/requirements.txt

# Remove leftovers
RUN apk del --no-cache .build-deps

RUN adduser -h "/app" -D -g '' arroyo
RUN mkdir /data
RUN chown -R arroyo:arroyo /app /data

# Point entrypoint to our script
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["--help"]
