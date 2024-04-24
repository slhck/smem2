FROM python:3.11-slim

COPY ./smem /usr/local/bin/smem

ENTRYPOINT [ "/usr/local/bin/smem" ]
