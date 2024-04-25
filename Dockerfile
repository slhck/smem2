FROM python:3.11-slim

WORKDIR /
COPY ./smem2 /usr/local/bin/smem2
COPY ./test.sh /test.sh

ENTRYPOINT [ "/usr/local/bin/smem2" ]
